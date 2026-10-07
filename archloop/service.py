"""Workbench service facade (A role) — one place the HTTP layer talks to.

Machine-readable failures via ContractError; every response carries backend
labels so 演示数据 can never pass as production data. Publishing (human
review) and fix-task handoff go through the adapter and refuse both the
missing-backend case (BACKEND_UNAVAILABLE) and any dev-sample origin.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from . import generate as generate_module
from . import ops as ops_module
from .adapters import AdapterRegistry, DEV_SAMPLE_MODE, reject_sample_review
from .contract import (ContractError, identity_view, is_full_sha, semantic_revision,
                       validate_workspace_identity)
from .store import DraftStore


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_repo_id(repo_path: str, remote: str | None) -> str:
    digest = hashlib.sha256(f"{repo_path}|{remote or ''}".encode("utf-8")).hexdigest()
    return f"repo-{digest[:16]}"


class WorkbenchService:
    def __init__(self, data_root, adapter: AdapterRegistry | None = None) -> None:
        self.store = DraftStore(data_root)
        self.adapter = adapter or AdapterRegistry()
        # Git access is injected by app.py so this module reuses the host's
        # hardened git runner (env stripping, no prompts) instead of copying
        # repository rules; code facts always come from explicit revisions.
        self.git = None

    # ---------- injected git access ----------

    def bind_git(self, git_callable) -> None:
        self.git = git_callable

    def _require_git(self):
        if self.git is None:
            raise ContractError("BACKEND_UNAVAILABLE", "本实例未绑定 Git 访问")
        return self.git

    def probe_repo(self, repo_path: str) -> dict:
        git = self._require_git()
        from pathlib import Path as _Path
        repo = _Path(repo_path)
        root = git(repo, "rev-parse", "--show-toplevel").decode("utf-8", errors="replace").strip()
        head = git(repo, "rev-parse", "HEAD").decode().strip()
        try:
            remote = git(repo, "remote", "get-url", "origin").decode("utf-8", errors="replace").strip()
        except Exception:
            remote = None
        raw = git(repo, "ls-tree", "-r", "-z", "--name-only", head)
        tracked = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
        return {"root": root, "head": head, "remote": remote, "trackedFiles": tracked}

    def diff_repo(self, repo_path: str, base: str, target: str) -> list[dict]:
        git = self._require_git()
        from pathlib import Path as _Path
        raw = git(_Path(repo_path), "diff", "--name-status", "-z", "-M", base, target, "--")
        parts = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
        changes = []
        index = 0
        while index < len(parts):
            code = parts[index]
            index += 1
            if code.startswith(("R", "C")):
                old_path, path = parts[index:index + 2]
                index += 2
                changes.append({"code": code, "oldPath": old_path, "path": path})
            else:
                changes.append({"code": code, "path": parts[index]})
                index += 1
        return changes

    # ---------- workspace lifecycle ----------

    def create_workspace(self, request: dict) -> dict:
        context = request.get("context")
        title = (request.get("title") or "").strip()
        if not title:
            raise ContractError("VALIDATION_FAILED", "请为工作区命名")
        identity = {
            "workspaceId": None,
            "codeRepoId": None,
            "mapId": None,
            "codeRevision": None,
            "mapSourceRevision": None,
            "verifiedCodeRevision": None,
        }
        repo_path = request.get("repoPath")
        if context in ("existing_project", "mixed"):
            if not isinstance(repo_path, str) or not repo_path.strip():
                raise ContractError("VALIDATION_FAILED", "已有项目需要仓库路径")
            probe = self.probe_repo(repo_path.strip())
            identity["codeRepoId"] = stable_repo_id(probe["root"], probe.get("remote"))
            identity["codeRevision"] = probe["head"]
            identity["repoPath"] = probe["root"]
            if context == "existing_project":
                identity["mapId"] = f"map-{identity['codeRepoId'][5:]}"
        workspace_id = f"ws_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(3)}"
        identity["workspaceId"] = workspace_id
        validate_workspace_identity(identity, context)
        record = {
            "workspaceId": workspace_id,
            "title": title,
            "context": context,
            "identity": identity,
            "description": request.get("description", ""),
            "goals": request.get("goals", ""),
            "constraints": request.get("constraints", ""),
            "createdAt": _utcnow(),
            "updatedAt": _utcnow(),
            "draft": None,
        }
        self.store.create_workspace(record)
        return self._envelope(record, mode=request.get("mode", "production"))

    def open_workspace(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        return self._envelope(record)

    def list_workspaces(self) -> dict:
        return {"workspaces": self.store.list_workspaces(), "backend": self._backend_label()}

    def _backend_label(self) -> dict:
        persistence = self.adapter._backends.get("persistence")
        if persistence:
            return {"kind": persistence["kind"], "labeled": "已接入真实后端", "origin": persistence["kind"]}
        return {"kind": "dev_sample_draft_store", "labeled": "演示数据 · 草稿保存在本实例，等待 B 后端接入",
                "origin": "dev_sample"}

    def _envelope(self, record: dict, mode: str = "production") -> dict:
        draft = record.get("draft")
        draft_revision = draft.get("draftRevision") if draft else None
        map_revision = draft.get("graph", {}).get("mapRevision") if draft else None
        return {
            "workspace": {key: record.get(key) for key in
                          ("workspaceId", "title", "context", "description", "goals", "constraints",
                           "createdAt", "updatedAt")},
            "identity": identity_view(record["identity"], map_revision, draft_revision),
            "draft": draft,
            "backend": self._backend_label(),
            "generation": generate_module.generate_status(),
            "mode": mode,
        }

    # ---------- generation ----------

    def generate(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        identity = record["identity"]
        mode = request.get("mode", "production")
        repo_facts = {}
        if identity.get("repoPath"):
            probe = self.probe_repo(identity["repoPath"])
            repo_facts = {
                "codeRepoId": identity.get("codeRepoId"),
                "codeRevision": probe["head"],
                "trackedFiles": probe.get("trackedFiles", [])[:400],
            }
        if mode == DEV_SAMPLE_MODE:
            sample = request.get("sampleGraph")
            if not isinstance(sample, dict):
                raise ContractError("DEV_SAMPLE_DISABLED", "演示模式需要明确提供样例图；不会用样例顶替真实 AI 生成")
            result = generate_module.sample_candidate(sample, record["context"])
        else:
            result = generate_module.generate_candidate({
                "context": record["context"],
                "description": record.get("description", ""),
                "goals": record.get("goals", ""),
                "constraints": record.get("constraints", ""),
            }, repo_facts=repo_facts)
        if result.get("status") in ("ai_generated", "dev_sample"):
            record["generation"] = {"status": result["status"], "at": _utcnow(),
                                    "mapRevision": result["graph"]["mapRevision"]}
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "generation", "origin": result["origin"],
                                                     "at": _utcnow(),
                                                     "mapRevision": result["graph"]["mapRevision"]})
        return result

    def apply_candidate(self, workspace_id: str, request: dict) -> dict:
        """User accepted a generated candidate: it becomes the working draft.

        A generation result is never applied silently; this call is the
        user's explicit confirmation of the candidate shown in the UI.
        """
        record = self.store.load_workspace(workspace_id)
        graph = request.get("graph")
        if not isinstance(graph, dict):
            raise ContractError("VALIDATION_FAILED", "缺少候选图")
        ops_module.validate_graph(graph)
        graph["mapRevision"] = semantic_revision(graph)
        draft = self._new_draft(record, graph, origin=request.get("origin", "ai_candidate"))
        record["draft"] = draft
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(workspace_id, {"type": "apply_candidate", "origin": draft["origin"],
                                                 "at": _utcnow(), "draftRevision": draft["draftRevision"]})
        return self._envelope(record)

    def _new_draft(self, record: dict, graph: dict, origin: str) -> dict:
        return {
            "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
            "baseMapRevision": None,
            "graph": graph,
            "baseGraph": graph,
            "origin": origin,
            "updatedAt": _utcnow(),
        }

    # ---------- drafts ----------

    def load_draft(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        return self._envelope(record)

    def apply_ops(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        expected = request.get("expectedDraftRevision")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿；先生成或导入候选图")
        if not isinstance(expected, str) or expected != draft["draftRevision"]:
            raise ContractError("REVISION_CONFLICT", "草稿已被他人修改；请刷新差异后重试",
                                {"expected": expected, "current": draft["draftRevision"]})
        operations = request.get("operations")
        if not isinstance(operations, list) or not operations:
            raise ContractError("VALIDATION_FAILED", "operations 必须是非空列表")
        graph = draft["graph"]
        applied = []
        for op in operations:
            graph = ops_module.apply_operation(graph, op)
            applied.append(op.get("type"))
        new_draft = {
            "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
            "baseMapRevision": draft.get("baseMapRevision"),
            "graph": graph,
            "baseGraph": draft.get("baseGraph") or draft["graph"],
            "origin": draft.get("origin") if draft.get("origin") != "ai_candidate" else "edited_candidate",
            "updatedAt": _utcnow(),
        }
        record["draft"] = new_draft
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(workspace_id, {"type": "apply_ops", "at": _utcnow(),
                                                 "operations": applied,
                                                 "actor": request.get("actor", "local_user"),
                                                 "draftRevision": new_draft["draftRevision"]})
        return self._envelope(record)

    def node_impact(self, workspace_id: str, node_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        return ops_module.node_impact(draft["graph"], node_id)

    def draft_diff(self, workspace_id: str) -> dict:
        """Diff between the accepted candidate (baseGraph) and the current draft."""
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        base = draft.get("baseGraph") or {"nodes": [], "edges": []}
        return ops_module.diff_graphs(base, draft["graph"])

    # ---------- natural-language correction ----------

    def correction_preview(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        expected = request.get("expectedDraftRevision")
        if expected != draft["draftRevision"]:
            raise ContractError("REVISION_CONFLICT", "草稿已变化，请刷新后再发起纠正",
                                {"expected": expected, "current": draft["draftRevision"]})
        instruction = (request.get("instruction") or "").strip()
        if not instruction:
            raise ContractError("VALIDATION_FAILED", "请描述要纠正的内容")
        selected = request.get("selectedNodeIds", [])
        if not isinstance(selected, list) or not selected:
            raise ContractError("VALIDATION_FAILED", "请选择要纠正的节点或区域")
        mode = request.get("mode", "production")
        backend = self.adapter.backend("correction", mode)
        if backend.get("kind") == "dev_sample":
            preview = self._sample_correction(record, draft, instruction, selected)
        else:
            # real C backend: fixed CONTRACT_V1 exchange (registered at integration)
            raise ContractError("BACKEND_UNAVAILABLE", "C 纠正后端尚未接入")
        proposal_id = f"prop_{secrets.token_hex(6)}"
        self.store.append_history(workspace_id, {"type": "correction_preview", "at": _utcnow(),
                                                 "proposalId": proposal_id,
                                                 "instruction": instruction,
                                                 "selected": selected, "origin": backend.get("kind")})
        return {
            "proposalId": proposal_id,
            "origin": backend.get("kind"),
            "labeled": backend.get("labeled"),
            "operations": preview["operations"],
            "diff": ops_module.diff_graphs(draft["graph"], preview["graph"]),
            "note": preview["note"],
        }

    def _sample_correction(self, record: dict, draft: dict, instruction: str, selected: list[str]) -> dict:
        """Labeled dev-sample preview: deterministic heuristic, no model call.

        Only callable in explicit dev-sample mode; operations show the UI
        shape a real C backend must return.
        """
        graph = draft["graph"]
        target_id = selected[0]
        node = next((n for n in graph["nodes"] if n["id"] == target_id), None)
        if node is None:
            raise ContractError("NOT_FOUND", f"节点不存在: {target_id}")
        operations = [{"type": "update_node", "nodeId": target_id,
                       "fields": {"summary": node.get("summary", "") + "（演示纠正：请以真实后端替换此预览）"}}]
        preview_graph = ops_module.apply_operation(graph, operations[0])
        return {"operations": operations, "graph": preview_graph,
                "note": "演示纠正预览：由本地确定性规则生成，仅验证交互；不代表 AI 输出。"}

    # ---------- review & publish (B seam) ----------

    def submit_review(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        if request.get("origin") == "dev_sample" or draft.get("origin") == "dev_sample":
            reject_sample_review({"origin": "dev_sample"})
        decision = request.get("decision")
        if decision not in ("accept", "partial", "reject"):
            raise ContractError("VALIDATION_FAILED", "decision 必须是 accept/partial/reject")
        actor = (request.get("actor") or "").strip()
        if not actor:
            raise ContractError("VALIDATION_FAILED", "复核需要 actor（本机操作者声明）")
        expected_map = request.get("expectedMapRevision")
        if not isinstance(expected_map, str) or expected_map != draft["graph"].get("mapRevision"):
            raise ContractError("REVISION_CONFLICT", "图版本已变化；请按最新预览重试",
                                {"expected": expected_map, "current": draft["graph"].get("mapRevision")})
        # Record the human decision first: the review happened even when the
        # version backend is missing; what must never happen is a version.
        self.store.append_history(workspace_id, {
            "type": "review_decision", "at": _utcnow(), "decision": decision,
            "actor": actor, "reason": request.get("reason", ""),
            "proposalId": request.get("proposalId"),
            "mapRevision": draft["graph"].get("mapRevision"),
            "delivery": "recorded_locally_pending_b_backend",
        })
        backend = self.adapter.backend("persistence", "production")
        # With B's service registered this delegates to publish_reviewed_graph;
        # until then the adapter raises BACKEND_UNAVAILABLE and nothing is
        # published.
        raise ContractError(
            "BACKEND_UNAVAILABLE",
            "B 的版本服务尚未接入：本次人审决定已记录在草稿历史，但没有产生任何正式认知版本。",
            {"decision": decision, "mapRevision": draft["graph"].get("mapRevision")},
        )

    # ---------- change recheck (P4) ----------

    def recheck(self, workspace_id: str) -> dict:
        record = self.store.load_workspace(workspace_id)
        identity = record["identity"]
        if not identity.get("repoPath") or not identity.get("codeRevision"):
            raise ContractError("VALIDATION_FAILED", "该工作区没有关联代码，无法做代码变化复核")
        probe = self.probe_repo(identity["repoPath"])
        new_head = probe["head"]
        result = {
            "oldCodeRevision": identity["codeRevision"],
            "newCodeRevision": new_head,
            "changed": new_head != identity["codeRevision"],
        }
        if result["changed"]:
            changes = self.diff_repo(identity["repoPath"], identity["codeRevision"], new_head)
            result["comparison"] = {"baseRevision": identity["codeRevision"], "targetRevision": new_head,
                                    "changes": changes}
            changed_paths = {c["path"] for c in changes}
            draft = record.get("draft")
            stale_nodes = []
            if draft:
                for node in draft["graph"]["nodes"]:
                    hit = sorted({item["path"] for item in node.get("evidence", [])
                                  if item.get("kind", "code_fact") == "code_fact" and item["path"] in changed_paths})
                    if hit:
                        stale_nodes.append({"nodeId": node["id"], "title": node["title"], "paths": hit})
            result["staleNodes"] = stale_nodes
            result["note"] = "代码已前进；列出的节点声明的代码证据出现在差异中，需要人复核。不代表架构已变化。"
        else:
            result["staleNodes"] = []
        identity["latestObservedCodeRevision"] = new_head
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(record["workspaceId"], {"type": "recheck", "at": _utcnow(),
                                                          "old": result["oldCodeRevision"],
                                                          "new": new_head})
        return result

    # ---------- fix task (D seam) ----------

    def create_fix_task(self, workspace_id: str, request: dict) -> dict:
        record = self.store.load_workspace(workspace_id)
        draft = record.get("draft")
        if draft is None:
            raise ContractError("VALIDATION_FAILED", "工作区还没有草稿")
        deviation = (request.get("deviation") or "").strip()
        if not deviation:
            raise ContractError("VALIDATION_FAILED", "请描述偏差内容")
        backend = self.adapter.backend("handoff", request.get("mode", "production"))
        if backend.get("kind") == "dev_sample":
            task = {
                "taskType": "implementation_fix",
                "labeled": "演示数据 · 修正实现任务样例",
                "origin": "dev_sample",
                "deviationId": f"dev_{secrets.token_hex(4)}",
                "workspaceId": record["workspaceId"],
                "mapRevision": draft["graph"].get("mapRevision"),
                "expectedProcessRef": request.get("expectedProcessRef"),
                "observation": deviation,
                "evidence": request.get("evidence", []),
                "acceptance": request.get("acceptance", ""),
                "status": "queued",
                "note": "改图不会自动修改程序；实施者在独立分支交付后回挂 SHA 再验证。",
            }
            self.store.append_history(workspace_id, {"type": "fixtask_sample", "at": _utcnow(),
                                                     "deviationId": task["deviationId"]})
            return task
        raise ContractError("BACKEND_UNAVAILABLE", "D 的交接后端尚未接入")
