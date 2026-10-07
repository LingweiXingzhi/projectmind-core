"""Explicit legacy local-draft import (A data root -> this round's data root).

Reads old workspaces in the previous workbench format, shows what differs from
the target root, and copies them into an explicitly named independent data root
under a NEW workspace id. The source root is only ever read. Demo origin marks
(`dev_sample` lineage) are carried over verbatim: an import can never turn
sample content into reviewable project content.

CLI (dry-run by default):

    python -m archloop.legacy_import --old-data OLD --new-data NEW [--workspace ws_...] [--apply]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .contract import ContractError, validate_graph, validate_workspace_identity
from .store import DraftStore

COPY_FIELDS = ("title", "context", "description", "goals", "constraints")
IDENTITY_FIELDS = ("codeRepoId", "mapId", "codeRevision", "repoPath", "workspaceId")


def scan(old_root: Path) -> list[dict]:
    store = DraftStore(Path(old_root))
    out = []
    for summary in store.list_workspaces():
        record = store.load_workspace(summary["workspaceId"])
        draft = record.get("draft")
        out.append({
            "workspaceId": summary["workspaceId"],
            "title": record.get("title"),
            "context": record.get("context"),
            "hasDraft": bool(draft),
            "draftOrigin": (draft or {}).get("origin"),
            "lineage": (draft or {}).get("lineage"),
            "nodes": len((draft or {}).get("graph", {}).get("nodes", [])),
            "edges": len((draft or {}).get("graph", {}).get("edges", [])),
            "mapRevision": (draft or {}).get("graph", {}).get("mapRevision"),
            "lastPublish": record.get("lastPublish"),
        })
    return out


def diff_summary(old_graph: dict, new_graph: dict | None) -> dict:
    old_nodes = {node["id"]: node for node in old_graph.get("nodes", [])}
    new_nodes = {node["id"]: node for node in (new_graph or {}).get("nodes", [])}
    added = sorted(set(new_nodes) - set(old_nodes))
    removed = sorted(set(old_nodes) - set(new_nodes))
    updated = sorted(node_id for node_id in set(old_nodes) & set(new_nodes)
                     if old_nodes[node_id] != new_nodes[node_id])
    old_edges = {(e["from"], e["to"], e["type"], e["label"]) for e in old_graph.get("edges", [])}
    new_edges = {(e["from"], e["to"], e["type"], e["label"]) for e in (new_graph or {}).get("edges", [])}
    return {"nodes": {"added": added, "removed": removed, "updated": updated},
            "edges": {"added": sorted(new_edges - old_edges), "removed": sorted(old_edges - new_edges)}}


def plan_import(old_root: Path, new_root: Path, workspace_id: str | None = None,
                new_workspace_id: str | None = None) -> dict:
    """Build the import plan: source content, target identity and the diff."""
    old_store = DraftStore(Path(old_root))
    new_store = DraftStore(Path(new_root))
    old_root = Path(old_root).resolve()
    new_root = Path(new_root).resolve()
    if old_root == new_root:
        raise ContractError("VALIDATION_FAILED", "源数据根与目标数据根不能相同")
    if new_store.root.exists() and new_store.root.resolve() == old_root:
        raise ContractError("VALIDATION_FAILED", "目标数据根不能是源数据根")
    candidates = scan(old_root)
    if workspace_id is None:
        if len(candidates) != 1:
            return {"action": "list", "candidates": candidates,
                    "note": "源数据根有多个工作区；请用 --workspace 指定要导入的一个"}
        workspace_id = candidates[0]["workspaceId"]
    if workspace_id not in {item["workspaceId"] for item in candidates}:
        raise ContractError("NOT_FOUND", f"源工作区不存在: {workspace_id}")
    record = old_store.load_workspace(workspace_id)
    draft = record.get("draft")
    if draft:
        validate_graph(draft["graph"])
    target_id = new_workspace_id or _fresh_workspace_id(workspace_id)
    existing = new_store.load_workspace(target_id) if (new_store.workspaces_dir / target_id).exists() else None
    plan = {
        "action": "import",
        "source": {"root": str(old_root), "workspaceId": workspace_id},
        "target": {"root": str(new_root), "workspaceId": target_id},
        "title": record.get("title"),
        "context": record.get("context"),
        "draftOrigin": (draft or {}).get("origin"),
        "lineage": (draft or {}).get("lineage"),
        "sampleMarked": bool(draft and (draft.get("origin") == "dev_sample"
                                        or "dev_sample" in (draft.get("lineage") or []))),
        "fields": {key: record.get(key) for key in COPY_FIELDS},
        "identityFrom": {key: record.get("identity", {}).get(key) for key in IDENTITY_FIELDS},
        "diffAgainstTargetExistingDraft": diff_summary(draft.get("graph", {}),
                                                       (existing or {}).get("draft", {}).get("graph"))
        if (existing and existing.get("draft")) else None,
        "note": ("演示来源保持标记：导入后仍不可提交人审" if draft and
                 (draft.get("origin") == "dev_sample" or "dev_sample" in (draft.get("lineage") or []))
                 else "导入只复制草稿内容；不产生正式版本，也不改变源数据根"),
    }
    return plan


def _fresh_workspace_id(old_id: str) -> str:
    import secrets
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"ws_{stamp}_{secrets.token_hex(3)}"


def apply_import(old_root: Path, new_root: Path, workspace_id: str | None = None,
                 new_workspace_id: str | None = None) -> dict:
    plan = plan_import(old_root, new_root, workspace_id, new_workspace_id)
    if plan.get("action") != "import":
        return plan
    old_store = DraftStore(Path(old_root))
    new_store = DraftStore(Path(new_root))
    record = old_store.load_workspace(plan["source"]["workspaceId"])
    draft = record.get("draft")
    new_record = {
        "workspaceId": plan["target"]["workspaceId"],
        "title": record.get("title"),
        "context": record.get("context"),
        "identity": dict(record.get("identity", {})),
        "description": record.get("description", ""),
        "goals": record.get("goals", ""),
        "constraints": record.get("constraints", ""),
        "createdAt": record.get("createdAt"),
        "updatedAt": record.get("updatedAt"),
        "draft": json.loads(json.dumps(draft)) if draft else None,
        "importedFrom": {"root": plan["source"]["root"],
                         "workspaceId": plan["source"]["workspaceId"]},
        "lastPublish": None,  # an import makes no version claim
    }
    new_record["identity"]["workspaceId"] = new_record["workspaceId"]
    validate_workspace_identity(new_record["identity"], new_record["context"])
    new_store.create_workspace(new_record)
    new_store.append_history(new_record["workspaceId"], {
        "type": "legacy_import", "at": plan.get("_at") or _now(),
        "fromRoot": plan["source"]["root"],
        "fromWorkspaceId": plan["source"]["workspaceId"],
        "sourceOrigin": plan.get("draftOrigin"),
        "sourceLineage": plan.get("lineage"),
        "note": "旧本地草稿显式导入；源数据根保持原样；未产生正式版本",
    })
    plan["applied"] = True
    plan["oldRootUntouched"] = True
    return plan


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description="显式导入旧工作台草稿到本轮独立数据根")
    parser.add_argument("--old-data", type=Path, required=True)
    parser.add_argument("--new-data", type=Path, required=True)
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--apply", action="store_true", help="真正写入；缺省只显示计划")
    parser.add_argument("--list", action="store_true", help="只列出源工作区")
    args = parser.parse_args()
    try:
        if args.list:
            print(json.dumps({"candidates": scan(args.old_data)}, ensure_ascii=False, indent=2))
            return 0
        if args.apply:
            result = apply_import(args.old_data, args.new_data, args.workspace)
        else:
            result = plan_import(args.old_data, args.new_data, args.workspace)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except ContractError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["scan", "plan_import", "apply_import", "diff_summary"]