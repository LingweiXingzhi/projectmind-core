"""A → D adapter: D's real fix-task/handover store is the authoritative seam.

D's `FixTaskService` (extensions/continuity/fix_tasks.py, PR #54) keeps task
state with CAS, Git checks and verification receipts. When it is configured,
*it* owns every fix task: A's simple workbench request (free-text deviation,
evidence paths, expected process) is adapted here to D's frozen packet
contract, and A's local `fix_tasks.py` seam is not used — one authoritative
store, no split task state (CONTRACT_V1 §7).

The adapter follows B's integration guide for D: the version handoff packet is
built from B's real exported version, the actor comes from the server-side
write session (never from request JSON), and the deviation/scope bindings are
registered server-side before the delegation runs.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .adapters import call_backend
from .contract import ContractError, is_full_sha

KIND = "d_architecture_handoff_v1"
REF = "D PR #54 — c8b942a8d724b1bd0509f61b2db6ec642a117181"
D_EVIDENCE_KINDS = ("test_observation", "trace_observation", "code")
SAFE_NOTE_LIMIT = 4000
VERIFICATION_TIMEOUT_SECONDS = 120


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _looks_like_repo_path(value: str) -> bool:
    return ("/" in value or value.endswith((".py", ".md", ".json", ".txt", ".js", ".html"))
            and "\\" not in value and not value.startswith("/") and ":" not in value)


def _normalize_evidence(items, *, version: dict) -> list[dict]:
    """Adapt A's evidence into D's frozen observation shape.

    D accepts only observed evidence (`test_observation`, `trace_observation`,
    `code`) bound to the published code revision; a bare path becomes a `code`
    observation, anything else is refused instead of being guessed.
    """
    if items is None:
        items = []
    if not isinstance(items, list) or not items:
        raise ContractError("VALIDATION_FAILED",
                            "修正实现需要观察证据（至少一项：路径或结构化观察）")
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, dict) and item.get("kind") in D_EVIDENCE_KINDS:
            entry = {"kind": item["kind"],
                     "detail": str(item.get("detail") or item.get("reason") or "").strip()}
            if not entry["detail"]:
                raise ContractError("VALIDATION_FAILED", "每条证据都需要说明（detail/reason）")
            if item["kind"] == "code":
                path = str(item.get("path") or "").strip()
                if not _looks_like_repo_path(path):
                    raise ContractError("VALIDATION_FAILED", f"代码证据需要安全的仓库相对路径: {path!r}")
                entry.update({"path": path, "codeRevision": version.get("codeRevision"),
                              "codeRepoId": version.get("codeRepoId")})
            else:
                entry.update({"codeRevision": version.get("codeRevision"),
                              "codeRepoId": version.get("codeRepoId")})
            normalized.append(entry)
        elif isinstance(item, dict) and item.get("path"):
            path = str(item["path"]).strip()
            if not _looks_like_repo_path(path):
                raise ContractError("VALIDATION_FAILED", f"证据路径不安全: {path!r}")
            normalized.append({"kind": "code", "path": path,
                               "detail": str(item.get("reason") or item.get("detail") or "任务依据的代码位置").strip(),
                               "codeRevision": version.get("codeRevision"),
                               "codeRepoId": version.get("codeRepoId")})
        elif isinstance(item, str) and _looks_like_repo_path(item.strip()):
            normalized.append({"kind": "code", "path": item.strip(),
                               "detail": "任务依据的代码位置",
                               "codeRevision": version.get("codeRevision"),
                               "codeRepoId": version.get("codeRepoId")})
        else:
            raise ContractError(
                "VALIDATION_FAILED",
                "证据必须是仓库相对路径或结构化观察（kind: test_observation/trace_observation/code）；"
                "自由文本与静态推断不能作为修正实现的观察证据")
    return normalized


def _normalize_expected_process_ref(value, *, graph: dict) -> dict:
    """Accept A's `<nodeId>/<stepId>` shorthand or D's frozen dict shape."""
    processes = {process.get("id"): process for process in graph.get("processes", []) or []}
    # A page graphs carry each node's expected process in `process` (B-shaped
    # graphs use `steps`); both shapes are read so the same reference works on
    # either side of the projection
    steps_by_node = {}
    for node in graph.get("nodes", []) or []:
        steps = node.get("process") if isinstance(node.get("process"), list) else node.get("steps", [])
        steps_by_node[node.get("id")] = {step.get("stepId") or step.get("id")
                                         for step in (steps or []) if isinstance(step, dict)}
    if isinstance(value, dict):
        process_id = str(value.get("processId") or "").strip()
        step_ids = value.get("stepIds")
        if not process_id or not isinstance(step_ids, list) or not step_ids:
            raise ContractError("VALIDATION_FAILED", "expectedProcessRef 需要 processId 与 stepIds")
        step_ids = [str(step_id) for step_id in step_ids]
    elif isinstance(value, str) and "/" in value:
        node_id, step_id = value.rsplit("/", 1)
        if "/" in node_id:
            raise ContractError("VALIDATION_FAILED", f"expectedProcessRef 形式不受支持: {value!r}")
        process_id = "process-" + node_id
        step_ids = [step_id]
    else:
        raise ContractError(
            "VALIDATION_FAILED",
            "请指明要修正的期望过程与步骤（如 expectedProcessRef: \"<nodeId>/<stepId>\"，"
            "或 {processId, stepIds}）")
    # the reference must exist in the published graph (D re-checks coverage)
    if processes:
        if process_id not in processes:
            raise ContractError("NOT_FOUND", f"期望过程不存在: {process_id}")
        known = {step.get("id") for step in processes[process_id].get("steps", []) or []}
    else:
        # A page graphs keep steps per node; the B process id is process-<nodeId>
        node_id = process_id[len("process-"):] if process_id.startswith("process-") else None
        known = steps_by_node.get(node_id, set())
    missing = [step_id for step_id in step_ids if step_id not in known]
    if missing:
        raise ContractError("NOT_FOUND", f"期望步骤不存在于该过程: {', '.join(missing)}")
    return {"processId": process_id, "stepIds": step_ids}


def _derive_scope(request: dict, evidence: list[dict]) -> list[str]:
    explicit = request.get("scope")
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ContractError("VALIDATION_FAILED", "scope 必须是非空路径列表（允许改动的范围）")
        paths = [str(item).strip() for item in explicit]
    else:
        paths = [item["path"] for item in evidence if item.get("kind") == "code"]
    paths = sorted({path for path in paths if path})
    if not paths:
        raise ContractError("VALIDATION_FAILED",
                            "请给出允许改动的路径范围（scope 或至少一条代码证据路径）")
    for path in paths:
        if not _looks_like_repo_path(path):
            raise ContractError("VALIDATION_FAILED", f"范围路径不安全: {path!r}")
    return paths


def _normalize_scope(paths) -> list[str]:
    """Same normalization D applies, so A cannot claim an unsafe scope path.

    Paths are POSIX-relative on the wire: on Windows `Path()` would inject
    backslashes and D's evidence_path guard rightly refuses them.
    """
    from pathlib import PurePosixPath
    cleaned = []
    for path in paths:
        raw = str(path).strip().replace("\\", "/")
        if raw.startswith("/") or ":" in raw or ".." in raw.split("/"):
            raise ContractError("VALIDATION_FAILED", f"范围路径不安全: {path!r}")
        normalized = str(PurePosixPath(raw))
        if normalized in ("", "."):
            raise ContractError("VALIDATION_FAILED", f"范围路径不安全: {path!r}")
        cleaned.append(normalized)
    return sorted(set(cleaned))


class BackendD:
    """Registered `handoff` backend: D's real FixTaskService behind A's seam."""

    KIND = KIND
    REF = REF

    def __init__(self, workbench, fix_service, *, architecture_repo, code_repositories,
                 verification_command=None) -> None:
        self.workbench = workbench
        self.fix_service = fix_service
        self.architecture_repo = Path(architecture_repo).resolve() if architecture_repo else None
        self.code_repositories = {str(key): Path(value).resolve()
                                  for key, value in (code_repositories or {}).items()}
        self.verification_command = tuple(verification_command) if verification_command else None
        self._pending: dict[str, dict] = {}
        self._contract = None
        self.available = False
        self.reason = "未绑定 D 的修正任务服务"
        try:
            from extensions.handoff.archloop_backend import create_archloop_backend
        except Exception as exc:  # pragma: no cover - import guard
            self.reason = f"D 模块不可用：{type(exc).__name__}"
            return
        self._contract = create_archloop_backend(fix_service, self._provider)
        self.available = True
        self.reason = None

    # ---------- registration / adapter surface ----------

    def descriptor(self) -> dict:
        return {"kind": KIND, "call": self.call, "ref": REF,
                "labeled": "D 的真实修正任务与交接服务（PR #54）"}

    def call(self, action: str, payload: dict) -> dict:
        if not self.available:
            raise ContractError("BACKEND_UNAVAILABLE", self.reason or "D 后端不可用")
        return call_backend(self._contract, action, payload)

    def status(self) -> dict:
        return {"available": self.available, "kind": KIND if self.available else "unavailable",
                "ref": REF, "reason": self.reason,
                "architectureRepo": str(self.architecture_repo) if self.architecture_repo else None,
                "codeRepositories": sorted(self.code_repositories),
                "verificationCommand": list(self.verification_command) if self.verification_command else None}

    # ---------- create (server-bound context) ----------

    def _provider(self, workspace_id: str) -> dict:
        """D's trusted binding: version handoff + actor + scope + deviationId."""
        context = self._pending.get(workspace_id)
        if context is None:
            raise ContractError(
                "STALE_CONTEXT",
                "没有服务端登记的修正上下文：修正任务必须由工作台在真实版本上发起（A 未登记该工作区）")
        return context

    def create(self, record: dict, draft: dict, request: dict, server_context: dict | None) -> dict:
        """Build the frozen packet, register the binding, then delegate to D."""
        binding = record.get("backendB") or {}
        last_publish = record.get("lastPublish") or {}
        if not binding.get("workspaceId") or not last_publish.get("mapRevision"):
            raise ContractError("VALIDATION_FAILED",
                                "修正任务必须绑定已发布版本：请先完成人审并发布当前图")
        actor = str((server_context or {}).get("actor") or "").strip()
        if not actor:
            raise ContractError(
                "VALIDATION_FAILED",
                "修正任务需要先声明本机操作者：建立写会话时带上 operator（actor 由服务端会话登记，"
                "不接受请求体自填）")
        deviation = (request.get("deviation") or "").strip()
        if not deviation:
            raise ContractError("VALIDATION_FAILED", "请描述偏差内容（观察到的实现与期望过程的差异）")
        acceptance = (request.get("acceptance") or "").strip()
        if not acceptance:
            raise ContractError("VALIDATION_FAILED", "请写明验收条件；没有验收条件的任务不能派发")

        backend_b = self.workbench._backend_b()
        envelope = backend_b.export_version(binding["workspaceId"], last_publish["mapRevision"])
        version = envelope["version"]
        graph = draft.get("graph") or {}
        expected_ref = _normalize_expected_process_ref(request.get("expectedProcessRef"), graph=graph)
        evidence = _normalize_evidence(request.get("evidence"), version=version)
        scope = _normalize_scope(_derive_scope(request, evidence))

        deviation_id = self._deviation_id(record, request, deviation)
        packet = self._handoff_packet(record, envelope, request)
        self._pending[record["workspaceId"]] = {
            "versionHandoff": packet, "actor": actor, "scope": scope, "deviationId": deviation_id,
        }
        try:
            task = self.call("create_fix_task", {
                "workspaceId": record["workspaceId"],
                "mapRevision": version["mapRevision"],
                "deviation": deviation,
                "expectedProcessRef": expected_ref,
                "evidence": evidence,
                "acceptance": acceptance,
            })
        finally:
            self._pending.pop(record["workspaceId"], None)
        task["envelope"] = {"identity": record.get("identity"), "backend": {"kind": KIND, "ref": REF}}
        return task

    def _deviation_id(self, record: dict, request: dict, deviation: str) -> str:
        """Bind the deviation server-side: reuse a recorded one or record a new one."""
        import secrets as _secrets
        recorded = record.get("deviations") or []
        candidate = str(request.get("deviationId") or "").strip()
        for item in recorded:
            if isinstance(item, dict) and item.get("id") == candidate:
                return candidate
        new_id = candidate if candidate else f"dev_{_secrets.token_hex(6)}"
        entry = {"id": new_id, "observation": deviation,
                 "evidence": [item for item in (request.get("evidence") or [])
                              if not isinstance(item, dict) or "path" not in item][:20],
                 "source": "operator_declared", "recordedAt": _utcnow(),
                 "status": "open", "labeled": "本机操作者声明（非身份认证）"}
        record.setdefault("deviations", []).append(entry)
        self.workbench.store.save_workspace_record(record)
        return new_id

    def _handoff_packet(self, record: dict, envelope: dict, request: dict) -> dict:
        from extensions.handoff.architecture import build_version_handoff
        identity = record.get("identity") or {}
        # D re-reads both clones and compares their real locators: the packet
        # must name the architecture and code sources exactly as Git reports
        # them, or the handoff stays an untrusted draft (SOURCE_REQUIRED).
        sources = {"code": self._code_source(identity),
                   "architecture": self._architecture_source()}
        references = {"candidates": [], "reviews": list(record.get("history", [])[-20:]),
                      "deviations": [{"id": item.get("id"), "status": item.get("status", "open")}
                                     for item in (record.get("deviations") or []) if isinstance(item, dict)],
                      "logs": []}
        return build_version_handoff(envelope, workspace_id=record["workspaceId"], sources=sources,
                                     task={"state": "pending", "nextAction": "接手并实施修正，回挂提交后再核验"},
                                     references=references)

    def _architecture_source(self) -> str | None:
        if not self.architecture_repo:
            return None
        try:
            from extensions.handoff.architecture import source_locator
            return source_locator(self.architecture_repo)
        except Exception:
            return None

    def _code_source(self, identity: dict) -> str | None:
        repo_path = identity.get("repoPath")
        if not repo_path:
            return None
        repo = Path(repo_path)
        git = self.workbench.git
        try:
            names = git(repo, "remote").decode().splitlines()
            if "origin" in names:
                value = git(repo, "remote", "get-url", "origin").decode().strip()
            else:
                value = "local:" + str(Path(repo).resolve())
        except Exception:
            value = "local:" + str(Path(repo).resolve())
        return value.rstrip("/")

    # ---------- reads / updates ----------

    def list_tasks(self, workspace_id: str) -> dict:
        tasks = [task for task in self.fix_service.listing()
                 if task.get("workspaceId") == workspace_id]
        return {"tasks": tasks, "backend": {"kind": KIND, "ref": REF},
                "source": "D FixTaskService（唯一权威任务状态）"}

    def get_task(self, task_id: str) -> dict:
        return self.fix_service.get(task_id)

    def markdown(self, task_id: str) -> dict:
        from extensions.continuity.fix_tasks import render_fix_task
        return {"markdown": render_fix_task(self.get_task(task_id))}

    def update(self, task_id: str, request: dict, server_context: dict | None) -> dict:
        actor = str((server_context or {}).get("actor") or "").strip()
        if not actor:
            raise ContractError("VALIDATION_FAILED",
                                "状态变更需要先声明本机操作者（写会话 operator）")
        task = self.get_task(task_id)
        expected_revision = task["revision"]
        expected_map = task["mapRevision"]
        status = request.get("status")
        if status in ("received", "in_progress", "rejected"):
            description = str(request.get("note") or request.get("description") or "").strip()
            if not description:
                raise ContractError("VALIDATION_FAILED", "状态变更需要实际反馈说明（note）")
            return self.fix_service.transition(task_id, expected_revision=expected_revision,
                                               expected_map_revision=expected_map, status=status,
                                               actor=actor, description=description[:SAFE_NOTE_LIMIT])
        if status == "submitted":
            commit = request.get("commitSha")
            if not is_full_sha(commit):
                raise ContractError("VALIDATION_FAILED", "submitted 需要完整的实施提交 SHA")
            evidence = str(request.get("summary") or request.get("note") or "").strip()
            if not evidence:
                raise ContractError("VALIDATION_FAILED", "提交回挂需要说明（summary）")
            return self.fix_service.submit(task_id, expected_revision=expected_revision,
                                           expected_map_revision=expected_map, revision=commit,
                                           actor=actor, evidence=evidence[:SAFE_NOTE_LIMIT])
        if status == "verified":
            if not self.verification_command:
                raise ContractError(
                    "BACKEND_UNAVAILABLE",
                    "尚未配置真实验证命令提供者：D 的 verified 需要本机实测凭据（退出码与输出摘要），"
                    "不能凭声明关闭偏差")
            token, _ = self.fix_service.run_verification(task_id)
            return self.fix_service.confirm_verification(
                task_id, token=token, expected_revision=expected_revision,
                expected_map_revision=expected_map, actor=actor,
                reason=str(request.get("reason") or "人确认本轮实测核查结论")[:SAFE_NOTE_LIMIT],
                human_confirmed=True)
        raise ContractError("VALIDATION_FAILED",
                            f"该状态不受支持（D 权威任务）：{status!r}；"
                            "可用 received/in_progress/rejected/submitted/verified")


def make_command_verification_provider(command, *, workbench, timeout=VERIFICATION_TIMEOUT_SECONDS):
    """Trusted in-process verifier: run the configured command at the submitted revision.

    The command comes from server configuration only — never from task JSON —
    and the receipt records the observed exit code and a digest of the raw
    output, so a human confirmation can decide on real evidence.
    """
    from extensions.continuity.fix_tasks import VerificationReceipt

    command = tuple(command)

    def provider(task: dict) -> "VerificationReceipt":
        # the repository is resolved from this instance's registered roots by
        # identity — a path inside task JSON is never trusted to spawn a process
        from extensions.handoff.architecture import code_identity
        code_repo_id = task.get("codeRepoId")
        repo = None
        for root in getattr(workbench, "code_repo_roots", []) or []:
            try:
                if code_identity(root) == code_repo_id:
                    repo = Path(root).resolve()
                    break
            except Exception:
                continue
        if repo is None:
            raise ContractError("STALE_CONTEXT", "任务绑定的代码仓库未登记到本实例")
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60).stdout.strip()
        if head != task["submittedRevision"]:
            raise ContractError("STALE_CONTEXT", "验证工作区不是回挂版本")
        result = subprocess.run(list(command), cwd=str(repo), capture_output=True,
                                timeout=timeout, stdin=subprocess.DEVNULL,
                                env={"PATH": os.environ.get("PATH", ""),
                                     "PYTHONIOENCODING": "utf-8"})
        digest = "sha256:" + hashlib.sha256(result.stdout + b"\0" + result.stderr).hexdigest()
        return VerificationReceipt(
            task["id"], task["revision"], task["submittedRevision"], tuple(command),
            result.returncode, digest, _utcnow(),
            f"实测命令退出码 {result.returncode}；输出摘要 {digest[:24]}",
            "C 复核：本次验证依据为实测命令输出；无追踪证据的运行偏差仍为 UNKNOWN",
            task["mapRevision"], False)

    return provider


__all__ = ["BackendD", "make_command_verification_provider", "KIND", "REF"]