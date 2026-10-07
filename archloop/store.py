"""Workspace and draft persistence for the architecture workbench.

Storage stays small and testable (contract: no graph database). Roots are
explicit; writes are atomic with unique temp names; every mutating workspace
operation runs under a per-workspace in-process lock so a CAS check and its
save cannot interleave with another writer (audit MID-1 finding 1).

IMPORTANT (CONTRACT_V1 seam): this local store is the workbench's own draft
workspace and the `dev_sample` backend's backing store. It never claims to be
B's architecture_workspace service: every response that comes from here is
labeled `backend.kind = "dev_sample_draft_store"` so the UI shows 演示数据.
When B's service is registered in the adapter, persistence switches to it and
this store remains for A-owned fixtures/tests.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

from .contract import ContractError, ID_PATTERN

WORKSPACE_DIR = re.compile(r"^ws_[0-9]{14}_[a-z0-9]{6}$")

_locks_guard = threading.Lock()
_locks_by_workspace: dict[str, threading.Lock] = {}


def workspace_lock(workspace_id: str) -> threading.Lock:
    """One lock per workspace id for the process lifetime."""
    with _locks_guard:
        lock = _locks_by_workspace.get(workspace_id)
        if lock is None:
            lock = threading.Lock()
            _locks_by_workspace[workspace_id] = lock
        return lock


class DraftStore:
    """Atomic JSON store under an explicit data root."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.workspaces_dir = self.root / "workspaces"

    def _workspace_dir(self, workspace_id: str) -> Path:
        if not isinstance(workspace_id, str) or not WORKSPACE_DIR.fullmatch(workspace_id):
            raise ContractError("VALIDATION_FAILED", "workspaceId 形状不合法")
        return self.workspaces_dir / workspace_id

    def create_workspace(self, record: dict) -> dict:
        target = self._workspace_dir(record["workspaceId"])
        try:
            target.mkdir(parents=True)
        except FileExistsError as exc:
            raise ContractError("VALIDATION_FAILED", "workspaceId 已存在") from exc
        self.save_workspace_record(record)
        return record

    def save_workspace_record(self, record: dict) -> dict:
        target = self._workspace_dir(record["workspaceId"]) / "workspace.json"
        self._write_json(target, record)
        return record

    def load_workspace(self, workspace_id: str) -> dict:
        path = self._workspace_dir(workspace_id) / "workspace.json"
        record = self._read_json(path)
        if record is None:
            raise ContractError("NOT_FOUND", f"工作区不存在: {workspace_id}")
        return record

    def list_workspaces(self) -> list[dict]:
        if not self.workspaces_dir.exists():
            return []
        records = []
        for folder in sorted(self.workspaces_dir.iterdir()):
            if not folder.is_dir() or not WORKSPACE_DIR.fullmatch(folder.name):
                continue
            record = self._read_json(folder / "workspace.json")
            if record:
                records.append({
                    "workspaceId": record.get("workspaceId"),
                    "title": record.get("title"),
                    "context": record.get("context"),
                    "updatedAt": record.get("updatedAt"),
                })
        return records

    def save_draft(self, workspace_id: str, draft: dict) -> dict:
        target = self._workspace_dir(workspace_id) / "draft.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(target, draft)
        return draft

    def load_draft(self, workspace_id: str) -> dict | None:
        return self._read_json(self._workspace_dir(workspace_id) / "draft.json")

    def append_history(self, workspace_id: str, entry: dict) -> None:
        path = self._workspace_dir(workspace_id) / "history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def load_history(self, workspace_id: str) -> list[dict]:
        path = self._workspace_dir(workspace_id) / "history.jsonl"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        return entries

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # unique temp name: two writers on one workspace must never share a
        # tmp file (audit MID-1 finding 1)
        tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex[:8]}.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return None


def new_workspace_id(token: str) -> str:
    if not re.fullmatch(r"[a-z0-9]{6}", token):
        raise ValueError("workspace token must be 6 lowercase alphanumerics")
    return f"ws_{token}"


__all__ = ["DraftStore", "new_workspace_id"]
