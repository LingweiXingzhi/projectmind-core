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
from .adapters import AdapterRegistry, DEV_SAMPLE_MODE, call_backend, reject_sample_review
from .contract import (ContractError, identity_view, is_full_sha, semantic_revision,
                       validate_workspace_identity)
from .store import DraftStore, workspace_lock


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
        delegating = bool(persistence and callable(persistence.get("call")))
        # Draft storage and the version service are distinct capabilities:
        # drafts stay in A's labeled local store until B's service actually
        # takes them over; a bare registration without a callable is not an
        # integration (FINAL-1 finding 8).
        return {
            "kind": "dev_sample_draft_store" if not delegating else "extension:persistence",
            "labeled": ("草稿保存在本实例数据目录，等待 B 版本服务接入；不产生正式认知版本"
                        if not delegating else
                        "版本服务已委托注册后端；草稿暂存本实例，正式版本以后端发布结果为准"),
            "origin": "dev_sample" if not delegating else "extension:persistence",
            "versionService": delegating,
        }

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

    def tracked_at(self, repo_path: str, sha: str) -> set[str]:
        """Files present at one specific full SHA — never the worktree, never
        a fresher HEAD (FINAL-1 finding 3: evidence must be checked against
        the revision it claims to describe)."""
        git = self._require_git()
        from pathlib import Path as _Path
        raw = git(_Path(repo_path), "ls-tree", "-r", "-z", "--name-only", sha)
        return {part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part}

    def _evidence_guard(self, graph: dict, record: dict, basis_sha: str | None,
                        tracked: set[str] | None = None) -> dict:
        """Enforce evidence honesty before a graph may enter a draft.

        Every draft write path (generation, direct ops, legacy import) goes
        through here (FINAL-1 finding 2). The check runs against the exact
        revision the graph claims to describe (basis_sha), never a fresher
        HEAD. existing_project/mixed: code_fact paths missing from that
        revision downgrade to kind=unknown with a recorded downgrade.
        planning: code_fact evidence is rejected outright — there is no
        repository to check against.
        """
        context = record["context"]
        if context == "planning":
            for node in graph.get("nodes", []):
                for item in node.get("evidence", []):
                    # missing kind means code_fact by contract: normalize
                    # before the check so it cannot slip through (FINAL-1 #2)
                    if item.get("kind", "code_fact") == "code_fact":
                        raise ContractError("VALIDATION_FAILED",
                                            f"规划工作区不允许代码事实证据（节点 {node.get('id')}）；请改为需求依据")
            return graph
        if tracked is None:
            if not basis_sha:
                raise ContractError("VALIDATION_FAILED", "缺少证据核查基准 SHA")
            tracked = self.tracked_at(record["identity"]["repoPath"], basis_sha)
        downgraded = []
        for node in graph.get("nodes", []):
            for item in node.get("evidence", []):
                if item.get("kind", "code_fact") == "code_fact" and item.get("path") not in tracked:
                    item["kind"] = "unknown"
                    item["reason"] = f"{item.get('reason', '')}（该路径未在提交 {basis_sha[:12]} 中核实，降级为未知）"
                    downgraded.append({"nodeId": node.get("id"), "path": item.get("path")})
        if downgraded:
            graph = dict(graph)
            graph["evidenceDowngrades"] = downgraded
        return graph

    def generate(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            identity = record["identity"]
            mode = request.get("mode", "production")
            repo_facts = {}
            source_revision = identity.get("codeRevision")
            if identity.get("repoPath"):
                probe = self.probe_repo(identity["repoPath"])
                source_revision = probe["head"]
                repo_facts = {
                    "codeRepoId": identity.get("codeRepoId"),
                    "codeRevision": source_revision,
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
                # The candidate is stored server-side with its origin and the
                # exact code revision it was generated from; applying later can
                # only pick this stored candidate (no origin laundering).
                tracked = self.tracked_at(identity["repoPath"], source_revision) \
                    if identity.get("repoPath") and source_revision else None
                graph = self._evidence_guard(result["graph"], record, source_revision, tracked)
                graph["mapRevision"] = semantic_revision(graph)  # evidence downgrades change semantics
                candidate_id = f"cand_{secrets.token_hex(5)}"
                record["lastCandidate"] = {
                    "candidateId": candidate_id,
                    "graph": graph,
                    "origin": result["origin"],
                    "status": result["status"],
                    "sourceCodeRevision": source_revision,
                    "unknowns": result.get("unknowns", []),
                    "openQuestions": result.get("openQuestions", []),
                    "labeled": result.get("labeled"),
                    "storedAt": _utcnow(),
                }
                record["generation"] = {"status": result["status"], "at": _utcnow(),
                                        "mapRevision": graph["mapRevision"],
                                        "candidateId": candidate_id}
                record["updatedAt"] = _utcnow()
                self.store.save_workspace_record(record)
                self.store.append_history(workspace_id, {"type": "generation", "origin": result["origin"],
                                                         "at": _utcnow(),
                                                         "candidateId": candidate_id,
                                                         "sourceCodeRevision": source_revision})
                result = dict(result)
                result["graph"] = graph
                result["candidateId"] = candidate_id
                result["sourceCodeRevision"] = source_revision
            return result

    def apply_candidate(self, workspace_id: str, request: dict) -> dict:
        """User accepted a stored candidate: it becomes the working draft.

        Only the server-stored candidate can be applied (origin is not
        client-chosen), any existing draft is CAS-guarded, and the candidate's
        generation basis must match the workspace's bound revision.
        """
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            candidate = record.get("lastCandidate")
            if not candidate:
                raise ContractError("VALIDATION_FAILED", "没有已存储的候选；请先生成")
            candidate_id = request.get("candidateId")
            if candidate_id != candidate["candidateId"]:
                raise ContractError("STALE_CONTEXT", "候选已过期或不存在；请重新生成",
                                    {"expected": candidate["candidateId"]})
            if record["identity"].get("codeRevision") is not None \
                    and candidate.get("sourceCodeRevision") \
                    and record["identity"]["codeRevision"] != candidate["sourceCodeRevision"]:
                raise ContractError("STALE_CONTEXT",
                                    "候选的生成依据与工作区绑定提交不一致；请先复核并回挂",
                                    {"candidateBasis": candidate["sourceCodeRevision"],
                                     "boundRevision": record["identity"]["codeRevision"]})
            existing_draft = record.get("draft")
            if existing_draft is not None:
                expected = request.get("expectedDraftRevision")
                if not isinstance(expected, str) or expected != existing_draft["draftRevision"]:
                    raise ContractError("REVISION_CONFLICT", "已有草稿被修改过；请先查看差异再决定替换",
                                        {"expected": expected, "current": existing_draft["draftRevision"]})
            graph = ops_module.validate_graph(candidate["graph"])
            graph["mapRevision"] = semantic_revision(graph)
            draft = self._new_draft(record, graph, origin=candidate["origin"])
            draft["generationMeta"] = {
                "origin": candidate["origin"],
                "generatedFromCodeRevision": candidate.get("sourceCodeRevision"),
                "unknowns": candidate.get("unknowns", []),
                "openQuestions": candidate.get("openQuestions", []),
            }
            record["draft"] = draft
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "apply_candidate", "origin": draft["origin"],
                                                     "at": _utcnow(), "draftRevision": draft["draftRevision"],
                                                     "candidateId": candidate["candidateId"]})
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
        with workspace_lock(workspace_id):
            return self._apply_ops_locked(workspace_id, request)

    def _apply_ops_locked(self, workspace_id: str, request: dict) -> dict:
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
        # direct edits go through the same evidence honesty guard as
        # generation (FINAL-1 finding 2)
        bound = record["identity"].get("codeRevision")
        graph = self._evidence_guard(graph, record, bound)
        new_draft = {
            "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
            "baseMapRevision": draft.get("baseMapRevision"),
            "graph": graph,
            "baseGraph": draft.get("baseGraph") or draft["graph"],
            "origin": draft.get("origin") if draft.get("origin") != "ai_candidate" else "edited_candidate",
            "generationMeta": draft.get("generationMeta"),
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
        with workspace_lock(workspace_id):
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
                origin = "dev_sample"
                labeled = "演示纠正预览（本地规则生成，非 AI）"
                note = preview["note"]
            else:
                # Real C backend: fixed CONTRACT_V1 exchange; the reply's
                # operations are validated by the op engine before previewing.
                reply = call_backend(backend, "correction_preview", {
                    "baseMapRevision": draft["graph"].get("mapRevision"),
                    "expectedDraftRevision": draft["draftRevision"],
                    "graph": draft["graph"],
                    "instruction": instruction,
                    "selectedNodeIds": selected,
                })
                operations = reply.get("operations")
                if not isinstance(operations, list) or not operations:
                    raise ContractError("BACKEND_UNAVAILABLE", "纠正后端没有返回可用操作")
                probe_graph = draft["graph"]
                for op in operations:
                    probe_graph = ops_module.apply_operation(probe_graph, op)
                preview = {"operations": operations, "graph": probe_graph}
                origin = backend.get("kind")
                labeled = "真实纠正后端预览"
                note = reply.get("note", "真实纠正后端返回的预览。")
            # The preview (operations + the draft revision it was based on) is
            # stored server-side; applying later must name the proposal and
            # pass an expiry check, so a stale preview cannot overwrite newer
            # edits (MID-1 finding 9).
            proposal_id = f"prop_{secrets.token_hex(6)}"
            record["lastCorrectionPreview"] = {
                "proposalId": proposal_id,
                "baseDraftRevision": draft["draftRevision"],
                "baseMapRevision": draft["graph"].get("mapRevision"),
                "operations": preview["operations"],
                "graph": preview["graph"],
                "origin": origin,
                "labeled": labeled,
                "instruction": instruction,
                "storedAt": _utcnow(),
            }
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "correction_preview", "at": _utcnow(),
                                                     "proposalId": proposal_id,
                                                     "instruction": instruction,
                                                     "selected": selected, "origin": origin})
            return {
                "proposalId": proposal_id,
                "origin": origin,
                "labeled": labeled,
                "operations": preview["operations"],
                "baseDraftRevision": draft["draftRevision"],
                "diff": ops_module.diff_graphs(draft["graph"], preview["graph"]),
                "note": note,
            }

    def apply_correction(self, workspace_id: str, request: dict) -> dict:
        """Apply a stored correction preview by proposalId (expiry-checked)."""
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            draft = record.get("draft")
            preview = record.get("lastCorrectionPreview")
            if draft is None or not preview:
                raise ContractError("NOT_FOUND", "没有已存储的纠正预览")
            proposal_id = request.get("proposalId")
            if not isinstance(proposal_id, str) or proposal_id != preview["proposalId"]:
                raise ContractError("NOT_FOUND", "纠正预览不存在或已过期；请重新生成",
                                    {"expected": preview["proposalId"]})
            expected = request.get("expectedDraftRevision")
            if not isinstance(expected, str) or expected != preview["baseDraftRevision"]:
                raise ContractError("STALE_CONTEXT", "请求与预览基准不一致；请使用预览返回的 baseDraftRevision",
                                    {"previewBasis": preview["baseDraftRevision"], "expected": expected})
            if preview["baseDraftRevision"] != draft["draftRevision"]:
                # the draft moved on after the preview was taken: the preview
                # is void and must be regenerated (MID-1 finding 9)
                raise ContractError("STALE_CONTEXT", "纠正预览基于旧草稿；草稿已变化，预览作废",
                                    {"previewBasis": preview["baseDraftRevision"],
                                     "current": draft["draftRevision"]})
            graph = draft["graph"]
            applied = []
            for op in preview["operations"]:
                graph = ops_module.apply_operation(graph, op)
                applied.append(op.get("type"))
            bound = record["identity"].get("codeRevision")
            graph = self._evidence_guard(graph, record, bound)
            new_draft = {
                "draftRevision": semantic_revision(graph) + f"-{secrets.token_hex(4)}",
                "baseMapRevision": draft.get("baseMapRevision"),
                "graph": graph,
                "baseGraph": draft.get("baseGraph") or draft["graph"],
                # sample-derived content keeps the sample marking: it can never
                # pass review as if it were clean (MID-1 finding 3)
                "origin": "dev_sample" if preview["origin"] == "dev_sample" else draft.get("origin"),
                "generationMeta": draft.get("generationMeta"),
                "updatedAt": _utcnow(),
            }
            record["draft"] = new_draft
            record["lastCorrectionPreview"] = None
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {"type": "apply_correction", "at": _utcnow(),
                                                     "proposalId": proposal_id,
                                                     "origin": preview["origin"],
                                                     "operations": applied,
                                                     "draftRevision": new_draft["draftRevision"]})
            return self._envelope(record)

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
        with workspace_lock(workspace_id):
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
            # Record the human decision first: the review happened even when
            # the version backend is missing; what must never happen is a
            # version. Everything up to the publish write-back stays inside
            # the workspace lock (FINAL-1 finding 4).
            self.store.append_history(workspace_id, {
                "type": "review_decision", "at": _utcnow(), "decision": decision,
                "actor": actor, "reason": request.get("reason", ""),
                "proposalId": request.get("proposalId"),
                "mapRevision": draft["graph"].get("mapRevision"),
                "delivery": "recorded_locally_pending_b_backend",
            })
            backend = self.adapter.backend("persistence", "production")
            if backend.get("kind") == "dev_sample":
                raise ContractError(
                    "BACKEND_UNAVAILABLE",
                    "B 的版本服务尚未接入：本次人审决定已记录在草稿历史，但没有产生任何正式认知版本。",
                    {"decision": decision, "mapRevision": draft["graph"].get("mapRevision")},
                )
            # A real backend is registered: delegate the publish transaction
            # with the reviewed content and the recorded decision.
            reply = call_backend(backend, "publish_reviewed_graph", {
                "workspaceId": record["workspaceId"],
                "mapRevision": draft["graph"].get("mapRevision"),
                "graph": draft["graph"],
                "decision": decision,
                "actor": actor,
                "reason": request.get("reason", ""),
                "proposalId": request.get("proposalId"),
            })
            if reply.get("status") == "published":
                published_revision = reply.get("mapRevision") or draft["graph"].get("mapRevision")
                # atomic re-check: the draft must still be the one that was
                # reviewed before the publish result is written back
                current = self.store.load_workspace(workspace_id)
                if current["draft"]["draftRevision"] != draft["draftRevision"]:
                    raise ContractError("REVISION_CONFLICT",
                                        "发布期间草稿又被修改；发布结果未写入，请重新复核",
                                        {"publishedMapRevision": published_revision})
                current["draft"]["publishedMapRevision"] = published_revision
                current["draft"]["mapSourceRevision"] = reply.get("mapSourceRevision")
                current["identity"]["mapSourceRevision"] = reply.get("mapSourceRevision")
                current["identity"]["verifiedCodeRevision"] = reply.get("verifiedCodeRevision")
                current["updatedAt"] = _utcnow()
                self.store.save_workspace_record(current)
                self.store.append_history(workspace_id, {"type": "publish", "at": _utcnow(),
                                                         "mapRevision": published_revision,
                                                         "mapSourceRevision": reply.get("mapSourceRevision")})
                return self._envelope(current)
            raise ContractError("BACKEND_UNAVAILABLE",
                                "版本后端未确认发布结果；不显示成功。",
                                {"reply": reply.get("status")})

    # ---------- change recheck (P4) ----------

    def recheck(self, workspace_id: str) -> dict:
        with workspace_lock(workspace_id):
            return self._recheck_locked(workspace_id)

    def _recheck_locked(self, workspace_id: str) -> dict:
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
            # renames must flag nodes still citing the old path too
            # (FINAL-1 finding 6)
            changed_paths = {c["path"] for c in changes}
            changed_paths |= {c["oldPath"] for c in changes if c.get("oldPath")}
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

    def rebind_code_revision(self, workspace_id: str, request: dict) -> dict:
        """Re-bind the workspace to a newly reviewed code revision (P4 回挂).

        This is a local record: until D's verification lands the rebind never
        sets verifiedCodeRevision, so nothing here claims the new code was
        human-verified.
        """
        with workspace_lock(workspace_id):
            record = self.store.load_workspace(workspace_id)
            identity = record["identity"]
            if not identity.get("repoPath"):
                raise ContractError("VALIDATION_FAILED", "该工作区没有关联代码")
            actor = (request.get("actor") or "").strip()
            if not actor:
                raise ContractError("VALIDATION_FAILED", "回挂需要 actor（本机操作者声明）")
            expected = request.get("expectedNewCodeRevision")
            probe = self.probe_repo(identity["repoPath"])
            if not is_full_sha(expected) or expected != probe["head"]:
                raise ContractError("STALE_CONTEXT", "回挂目标与仓库当前 HEAD 不一致；请先刷新复核",
                                    {"expected": expected, "head": probe["head"]})
            old = identity.get("codeRevision")
            identity["codeRevision"] = expected
            record["updatedAt"] = _utcnow()
            self.store.save_workspace_record(record)
            self.store.append_history(workspace_id, {
                "type": "rebind", "at": _utcnow(), "actor": actor,
                "from": old, "to": expected,
                "note": request.get("note", ""),
                "delivery": "local_rebind_pending_d_verification",
            })
            return self._envelope(record)

    # ---------- fix task (D seam) ----------

    def import_legacy_map(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
            return self._import_legacy_locked(workspace_id, request)

    def _import_legacy_locked(self, workspace_id: str, request: dict) -> dict:
        """Import the legacy curated demo map as an unconfirmed draft.

        Compatibility seam (A instruction: legacy map gets a clear read-only
        compatible path into the new workspace). The import never claims the
        old demo graph was confirmed: every node becomes candidate/human_input
        with an explicit import note, and legacy relations become
        functional_collaboration — never expected_sequence, so imports cannot
        disguise themselves as runtime chains.
        """
        record = self.store.load_workspace(workspace_id)
        legacy = request.get("legacyMap")
        if not isinstance(legacy, dict) or not isinstance(legacy.get("nodes"), list):
            raise ContractError("VALIDATION_FAILED", "需要 legacyMap{note, nodes[], edges[]}")
        # replacing an existing draft is CAS-guarded like any other write
        # (FINAL-1 finding 1)
        existing_draft = record.get("draft")
        if existing_draft is not None:
            expected = request.get("expectedDraftRevision")
            if not isinstance(expected, str) or expected != existing_draft["draftRevision"]:
                raise ContractError("REVISION_CONFLICT", "已有草稿被修改过；请先查看差异再决定导入",
                                    {"expected": expected, "current": existing_draft["draftRevision"]})
        note = legacy.get("note", "")
        nodes = []
        for node in legacy["nodes"]:
            if not isinstance(node, dict) or not node.get("id"):
                raise ContractError("VALIDATION_FAILED", "legacy 节点缺少 id")
            evidence = [{"path": item.get("path", ""), "reason": item.get("reason", ""), "kind": "code_fact"}
                        for item in node.get("evidence", []) if isinstance(item, dict) and item.get("path")]
            nodes.append({
                "id": node["id"], "title": node.get("title", node["id"]),
                "summary": node.get("summary", ""), "status": "candidate",
                "provenance": "human_input",
                "entryPoints": [node["entryPoint"]] if node.get("entryPoint") else [],
                "interfaces": [], "evidence": evidence, "process": [],
                "importNote": f"来自 legacy 人工演示图：{note}",
            })
        edges = [{"from": edge.get("from"), "to": edge.get("to"),
                  "type": "functional_collaboration",
                  "label": f"{edge.get('label', '')}（legacy 导入，非运行链）"}
                 for edge in legacy.get("edges", []) if isinstance(edge, dict)]
        graph = {"nodes": nodes, "edges": edges}
        # structural validation before anything is stored: bad IDs or dangling
        # edges fail loudly instead of entering the workspace
        ops_module.validate_graph(graph)
        bound = record["identity"].get("codeRevision")
        graph = self._evidence_guard(graph, record, bound)
        graph["mapRevision"] = semantic_revision(graph)
        draft = self._new_draft(record, graph, origin="legacy_import")
        record["draft"] = draft
        record["updatedAt"] = _utcnow()
        self.store.save_workspace_record(record)
        self.store.append_history(workspace_id, {"type": "import_legacy", "at": _utcnow(),
                                                 "nodes": len(nodes), "edges": len(edges),
                                                 "draftRevision": draft["draftRevision"]})
        return self._envelope(record)

    def create_fix_task(self, workspace_id: str, request: dict) -> dict:
        with workspace_lock(workspace_id):
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
        # a registered real handoff backend receives the delegation
        # (FINAL-1 finding 9: do not refuse when a backend exists)
        return call_backend(backend, "create_fix_task", {
            "workspaceId": record["workspaceId"],
            "mapRevision": draft["graph"].get("mapRevision"),
            "expectedProcessRef": request.get("expectedProcessRef"),
            "deviation": deviation,
            "evidence": request.get("evidence", []),
            "acceptance": request.get("acceptance", ""),
        })
