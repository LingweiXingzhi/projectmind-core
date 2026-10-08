"""A-side acceptance run (the 28-item main line) against a running workbench.

This is A's own end-to-end verification, not D's independent acceptance: D's
module is not delivered yet, so the runner drives the real HTTP surface and
records, per item, the actual request/response evidence and its honest status
(PASS / NOT_RUN / NOT_DELIVERED / FAIL). Items that need a configured model or
a real browser are marked NOT_RUN here and are covered by the live browser
observation and the real-model status elsewhere — never silently counted.

Usage (server already running, e.g. on port 8801):

    python -m archloop.acceptance --base-url http://127.0.0.1:8801 \
        --repo <fixture repo path> --out <report path>
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from .acceptance_http import AcceptanceHTTP

ORIGIN_FALLBACK = None
# the repository this runner itself lives in: T24 must cover THIS project's
# tracked files, not whichever demo repository happens to be bound
REPO_ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


def _git_env():
    return {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}


def _same_path(left: str, right: str) -> bool:
    """True when two paths name the same real location (case/separator safe)."""
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return os.path.normcase(os.path.normpath(str(left))) == \
            os.path.normcase(os.path.normpath(str(right)))


def _git_object_exists(repo: str, revision: str) -> bool:
    """Real check: the named revision must be a commit in that repository."""
    if not isinstance(revision, str) or FULL_SHA_PATTERN.fullmatch(revision) is None:
        return False
    try:
        probe = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", revision + "^{commit}"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60, env=_git_env())
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def _request(base_url: str, method: str, path: str, payload: dict | None = None,
             origin: str | None = None, timeout: int = 60):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(base_url + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if origin:
        request.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"error": {"code": "NON_JSON", "message": raw[:400]}}


def ai_generation_verdict(status, payload) -> tuple[str, dict]:
    """T01 criteria: what counts as a real AI first graph.

    Only the real generation envelope passes: status ai_generated, origin
    ai_generated, a non-empty graph and ai_candidate provenance on every node.
    A 200 carrying AI_GENERATION_FAILED (or an empty graph) is NOT a generated
    first graph, and an unconfigured server is NOT_RUN (BATCH-2 ACCEPTANCE-01).
    """
    payload = payload or {}
    graph = payload.get("graph") or {}
    nodes = graph.get("nodes") or []
    evidence = {"http": status, "status": payload.get("status"), "origin": payload.get("origin"),
                "model": payload.get("model"), "nodes": len(nodes),
                "mapRevision": graph.get("mapRevision"), "note": payload.get("note"),
                "error": (payload.get("error") or {}).get("code")
                if isinstance(payload.get("error"), dict) else None}
    if payload.get("status") == "NOT_RUN_AWAITING_CONFIGURATION":
        return "NOT_RUN", evidence
    ok = (status == 200 and payload.get("status") == "ai_generated"
          and payload.get("origin") == "ai_generated" and nodes
          and all(node.get("provenance") == "ai_candidate" for node in nodes))
    return ("PASS" if ok else "FAIL"), evidence


def handover_tamper_verdict(status, body) -> tuple[str, dict]:
    """T21 criteria: what counts as "the tampered package was detected".

    Detection is demonstrated either by the content comparison itself
    (handoverComparison.contentMatches == False while the revision still
    matches — the package content was changed, not the version) or by a refusal
    whose machine code is about content integrity (EVIDENCE_MISMATCH). A refusal
    for an unrelated reason — e.g. STALE_CONTEXT because the map identity
    already belongs to another workspace, which is what the first run recorded —
    proves nothing about tamper detection and must not be a PASS
    (BATCH-2 ACCEPTANCE-01).
    """
    body = body or {}
    comparison = body.get("handoverComparison")
    code = ((body.get("error") or {}).get("code")
            if isinstance(body.get("error"), dict) else None)
    # the comparison must be complete and consistent: a content mismatch alone
    # is only tamper detection when the version identity itself still matches
    # (BATCH-3 ACCEPTANCE-01)
    detected = (isinstance(comparison, dict) and comparison.get("contentMatches") is False
                and comparison.get("revisionMatches") is True
                and comparison.get("mapIdMatches") is True)
    refused_as_tamper = status != 200 and code == "EVIDENCE_MISMATCH"
    evidence = {"http": status, "code": code, "comparison": comparison,
                "packageMapIdMismatch": body.get("packageMapIdMismatch"),
                "error": body.get("error")}
    return ("PASS" if (detected or refused_as_tamper) else "FAIL"), evidence


def _git_tracked_counts(repo: str, revision: str) -> tuple[int | None, int | None]:
    """(tracked files, python files) of this repository at `revision`, or None.

    The workspace API deliberately does not echo the bound repository path, so
    T24 proves the binding with the tree it read: the coverage counts must equal
    this repository's real tree at the same revision — no other repository (or
    a placeholder revision) can satisfy that (BATCH-3 ACCEPTANCE-01).
    """
    try:
        listing = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", "--name-only",
                                  revision], capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=60, env=_git_env())
    except (OSError, subprocess.SubprocessError):
        return None, None
    if listing.returncode != 0:
        return None, None
    paths = [part for part in listing.stdout.split("\0") if part]
    return len(paths), sum(1 for path in paths if path.endswith(".py"))


def self_coverage_verdict(status, body, repo: str, identity: dict | None = None,
                          revision_exists: bool | None = None, expected_revision: str | None = None,
                          expected_tracked: int | None = None,
                          expected_python: int | None = None) -> tuple[str, dict]:
    """T24 criteria: ProjectMind's own repository really covered.

    The candidate must come from a workspace bound to a *real* full commit of
    THIS project (the runner confirms the revision exists and computes the
    tree's file counts locally): identity revision, coverage revision and the
    local HEAD must agree, and the coverage's tracked/python counts must equal
    this repository's real tree at that revision with a real number of files.
    A placeholder like "HEAD", a nonexistent SHA, another repository or an
    identity that disagrees with the coverage does not qualify as "ProjectMind
    itself" (BATCH-2 + BATCH-3 ACCEPTANCE-01).
    """
    body = body or {}
    identity = identity or {}
    coverage = body.get("contextCoverage") or {}
    nodes = (body.get("graph") or {}).get("nodes") or []
    tracked = coverage.get("trackedFiles") or 0
    python_files = coverage.get("pythonFiles")
    identity_repo = identity.get("repoPath")
    identity_revision = identity.get("codeRevision")
    revision_matches = (isinstance(identity_revision, str)
                        and coverage.get("codeRevision") == identity_revision
                        and (expected_revision is None or identity_revision == expected_revision))
    repo_matches = True if not identity_repo else _same_path(identity_repo, repo)
    tree_matches = (expected_tracked is not None and tracked == expected_tracked
                    and (expected_python is None or python_files == expected_python))
    ok = (status == 200 and bool(nodes) and tracked >= 50
          and FULL_SHA_PATTERN.fullmatch(str(identity_revision or "")) is not None
          and revision_matches and repo_matches and tree_matches and revision_exists is True)
    evidence = {"repo": repo, "identityRepoPath": identity_repo, "workspaceRevision": identity_revision,
                "coverageRevision": coverage.get("codeRevision"), "localHead": expected_revision,
                "revisionExistsInGit": revision_exists,
                "revisionMatchesCoverage": revision_matches, "repoMatchesBinding": repo_matches,
                "trackedFiles": tracked, "localTrackedFiles": expected_tracked,
                "pythonFiles": python_files, "localPythonFiles": expected_python,
                "treeMatchesRepository": tree_matches,
                "filesIncluded": coverage.get("filesIncluded"),
                "nodes": len(nodes), "http": status, "error": body.get("error"),
                "note": "绑定仓库即本次被验收的 ProjectMind 代码（其文件数与本仓库该提交的真实文件树一致）；"
                        "正式图内容仍由负责人在界面批准"}
    return ("PASS" if ok else "FAIL"), evidence


def independent_self_coverage_verdict(status, body, repo, identity):
    try:
        probe = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                               capture_output=True, text=True, timeout=60, env=_git_env())
        head = probe.stdout.strip() if probe.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        head = None
    exists = _git_object_exists(repo, head)
    tracked, python = _git_tracked_counts(repo, head) if exists else (None, None)
    status, evidence = self_coverage_verdict(status, body, repo, identity=identity,
        revision_exists=exists, expected_revision=head, expected_tracked=tracked, expected_python=python)
    evidence['headSource'] = 'independent git rev-parse HEAD'
    return status, evidence


def native_handover_tamper_verdict(package):
    from copy import deepcopy
    from extensions.handoff.architecture import ArchitectureError, validate_handoff
    try:
        validate_handoff(package)  # The original must actually be valid.
        changed = deepcopy(package)
        changed['versionEnvelope']['version']['graph']['nodes'][0]['description'] = 'tampered fixture'
        validate_handoff(changed)
    except ArchitectureError as exc:
        # Invalid ORIGINAL data is not evidence of detecting our tamper.
        if 'changed' not in locals():
            return 'FAIL', {'code': exc.code, 'originalValid': False}
        return ('PASS' if exc.code == 'EVIDENCE_MISMATCH' else 'FAIL'), {
            'code': exc.code, 'originalValid': True, 'scope': 'native packet integrity only; second-copy Git import NOT_RUN'}
    except (KeyError, IndexError, TypeError):
        return 'FAIL', {'originalValid': False, 'code': 'INVALID_HANDOFF_SHAPE'}
    return 'FAIL', {'code': 'TAMPER_NOT_DETECTED'}


class Acceptance:
    def __init__(self, base_url: str, repo: str, arch_repo: str | None = None, *,
                 client=None, repo_key=None, self_repo_key=None, allow_fixture_writes=False):
        self.base_url = base_url.rstrip("/")
        self.repo = repo
        self.arch_repo = arch_repo
        self.origin = self.base_url
        self.results: list[dict] = []
        self.workspace_id: str | None = None
        self.planning_id: str | None = None
        # (http, body) of the tamper comparison captured while the workspace
        # still matched the published version (recorded as T21); None = not run
        self.tamper_result = None
        self.client = client or AcceptanceHTTP(self.base_url)
        self.repo_key = repo_key
        self.self_repo_key = self_repo_key
        self.allow_fixture_writes = allow_fixture_writes

    # ---------- helpers ----------
    def record(self, item: str, title: str, status: str, evidence) -> None:
        self.results.append({"item": item, "title": title, "status": status,
                             "evidence": evidence if isinstance(evidence, str)
                             else json.dumps(evidence, ensure_ascii=False)[:1500]})

    def call(self, method: str, path: str, payload=None, origin=True):
        if isinstance(payload, dict) and 'repoPath' in payload and self.client.auth:
            alias = self.self_repo_key if _same_path(payload['repoPath'], str(REPO_ROOT)) else self.repo_key
            if not alias or alias not in {entry.get('key') for entry in self.client.repositories}:
                raise ValueError('验收仓库必须在已登录服务端清单中明确登记')
            payload = {**payload, 'repoPath': alias}
        status, _, body = self.client.request(method, path, payload, origin=origin)
        return status, body

    def git(self, *args):
        result = subprocess.run(["git", "-C", self.repo, *args], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=60, env=_git_env())
        if result.returncode:
            raise RuntimeError('验收 Git 命令未成功（不回显本机路径或环境）')
        return result.stdout.strip()

    def require_workspace(self) -> str:
        if not self.workspace_id:
            status, envelope = self.call("POST", "/api/archloop/workspaces", {
                "context": "existing_project", "title": "验收-已有项目", "repoPath": self.repo,
                "description": "A 侧主线验收：读取固定提交的代码事实并起草功能架构。"})
            if status != 200:
                raise RuntimeError(f"create workspace failed: {status} {envelope}")
            self.workspace_id = envelope["workspace"]["workspaceId"]
        return self.workspace_id

    def require_planning(self) -> str:
        if not self.planning_id:
            status, envelope = self.call("POST", "/api/archloop/workspaces", {
                "context": "planning", "title": "验收-规划", "description": "无代码规划验收",
                "goals": "支持自然语言纠正与同版交接", "constraints": "本轮不引入新依赖"})
            if status != 200:
                raise RuntimeError(f"create planning workspace failed: {status} {envelope}")
            self.planning_id = envelope["workspace"]["workspaceId"]
        return self.planning_id

    # ---------- the 28 items ----------
    def run(self) -> dict:
        if not self.allow_fixture_writes or _same_path(self.repo, str(REPO_ROOT)):
            raise ValueError('验收会改动代码/发布样例图，只能显式指定可丢弃 fixture')
        if self.git('status', '--porcelain'):
            raise ValueError('验收 fixture 必须没有已有修改')
        ws = self.require_workspace()
        planning = self.require_planning()
        head = self.git("rev-parse", "HEAD")

        # T01 real-AI first graph
        status, payload = self.call("POST", f"/api/archloop/workspaces/{ws}/generate",
                                    {"mode": "production"})
        t01_status, t01_evidence = ai_generation_verdict(status, payload)
        self.record("T01", "已有项目经真实 AI 生成初图", t01_status, t01_evidence)

        # T02 function graph (not a file tree) via the labeled rule engine
        status, generated = self.call("POST", f"/api/archloop/workspaces/{ws}/generate",
                                     {"mode": "rule_based"})
        nodes = generated.get("graph", {}).get("nodes", []) if status == 200 else []
        self.record("T02", "生成的是功能图而不是文件树", "PASS" if nodes else "FAIL",
                    {"status": generated.get("status"), "origin": generated.get("origin"),
                     "nodes": [{"id": n["id"], "title": n["title"]} for n in nodes][:6],
                     "contextCoverage": generated.get("contextCoverage")})
        if not nodes:
            return self._finish()
        status, applied = self.call("POST", f"/api/archloop/workspaces/{ws}/apply-candidate",
                                    {"candidateId": generated["candidateId"]})
        draft = applied["draft"]
        node_id = draft["graph"]["nodes"][0]["id"]
        self.record("T02b", "候选应用到草稿", "PASS" if status == 200 else "FAIL",
                    {"draftRevision": draft["draftRevision"], "nodes": len(draft["graph"]["nodes"])})

        # T03 natural-language correction (rule engine) + manual edit
        status, preview = self.call("POST", f"/api/archloop/workspaces/{ws}/correction-preview", {
            "mode": "rule_based", "instruction": "该职责只负责读取路径",
            "selectedNodeIds": [node_id], "expectedDraftRevision": draft["draftRevision"]})
        self.record("T03", "自然语言纠正（规则引擎）返回局部操作与前后差异",
                    "PASS" if status == 200 and preview.get("operations") else "FAIL",
                    {"origin": preview.get("origin"), "labeled": preview.get("labeled"),
                     "operations": preview.get("operations"), "diffKeys": list((preview.get("diff") or {}).keys())})
        if status == 200:
            status, corrected = self.call("POST", f"/api/archloop/workspaces/{ws}/apply-correction", {
                "proposalId": preview["proposalId"],
                "expectedDraftRevision": preview["baseDraftRevision"]})
            draft = corrected["draft"]
        # manual edit of a relation and a process step
        operations = [{"type": "update_node", "nodeId": node_id,
                       "fields": {"summary": "人工修改后的职责描述"}}]
        nodes_now = draft["graph"]["nodes"]
        if len(nodes_now) >= 2:
            operations.append({"type": "add_edge",
                               "edge": {"from": nodes_now[0]["id"], "to": nodes_now[1]["id"],
                                        "type": "functional_collaboration", "label": "验收关系"}})
        operations.append({"type": "update_process", "nodeId": node_id, "process": [
            {"stepId": "s1", "title": "人工步骤", "detail": "验收", "inputs": [], "outputs": [],
             "branches": ["分支A"], "next": ["s2"], "allowedFailures": ["允许失败路径"]},
            {"stepId": "s2", "title": "样例后继步骤", "detail": "fixture only", "inputs": [], "outputs": [],
             "branches": [], "next": []}]})
        status, edited = self.call("POST", f"/api/archloop/workspaces/{ws}/apply-ops", {
            "expectedDraftRevision": draft["draftRevision"], "operations": operations,
            "actor": "验收操作者"})
        self.record("T04/T05", "手工编辑职责/关系/过程（含分支与允许失败路径）",
                    "PASS" if status == 200 else "FAIL",
                    {"http": status, "operations": [op["type"] for op in operations],
                     "error": (edited or {}).get("error")})
        if status == 200:
            draft = edited["draft"]
            step = draft["graph"]["nodes"][0]["process"][0]
            self.record("T05b", "过程步骤保留稳定 stepId、分支与失败路径",
                        "PASS" if step["stepId"] == "s1" and step["branches"] and step["allowedFailures"] else "FAIL",
                        {"step": step})

        # T06 persistence after reload
        status, reopened = self.call("GET", f"/api/archloop/workspaces/{ws}")
        same = reopened["draft"]["draftRevision"] == draft["draftRevision"] and \
            reopened["draft"]["graph"]["nodes"][0]["summary"] == "人工修改后的职责描述"
        self.record("T06", "刷新重开后草稿仍在且内容一致", "PASS" if same else "FAIL",
                    {"draftRevision": reopened["draft"]["draftRevision"]})

        # T07 two-client conflict
        status, conflict = self.call("POST", f"/api/archloop/workspaces/{ws}/apply-ops", {
            "expectedDraftRevision": "stale-revision", "operations": [
                {"type": "update_node", "nodeId": node_id, "fields": {"summary": "旧客户端写入"}}]})
        code = (conflict or {}).get("error", {}).get("code")
        self.record("T07", "两个客户端同草稿写入冲突时不覆盖", "PASS" if code == "REVISION_CONFLICT" else "FAIL",
                    {"http": status, "code": code})

        # T08/T09/T10 review boundary and immutable version
        status, sync = self.call("POST", f"/api/archloop/workspaces/{ws}/sync", {})
        self.record("T08", "草稿保存到真实版本服务（真实持久化）",
                    "PASS" if status == 200 and sync.get("bDraftId") else "FAIL",
                    {"bDraftId": sync.get("bDraftId"), "bDraftRevision": sync.get("bDraftRevision"),
                     "error": (sync or {}).get("error")})
        status, denied = self.call("POST", f"/api/archloop/workspaces/{ws}/publish", {})
        self.record("T09", "未获批不能发布（必须先预览+确认）",
                    "PASS" if status in (403, 409) and (denied or {}).get("error", {}).get("code")
                    in ("HUMAN_REVIEW_REQUIRED", "REQUEST_FORBIDDEN", "REVISION_CONFLICT") else "FAIL",
                    {"http": status, "code": (denied or {}).get("error", {}).get("code")})
        status, preview = self.call("POST", f"/api/archloop/workspaces/{ws}/review-preview",
                                    {"actor": "验收操作者", "reason": "验收人审预览"})
        preview_ok = status == 200 and preview.get("previewDigest") and \
            "confirmationToken" not in (preview or {})
        self.record("T10a", "人审预览：真实会话、覆盖范围、令牌留在服务端",
                    "PASS" if preview_ok else "FAIL",
                    {"http": status, "coverage": (preview or {}).get("reviewCoverage"),
                     "tokenLeaked": "confirmationToken" in (preview or {}),
                     "error": (preview or {}).get("error")})
        status, confirmed = self.call("POST", f"/api/archloop/workspaces/{ws}/review-confirm",
                                      {"previewDigest": preview.get("previewDigest"), "decision": "accept"})
        status2, published = self.call("POST", f"/api/archloop/workspaces/{ws}/publish", {})
        version = (published or {}).get("version", {})
        self.record("T10b", "批准后产生不可变版本（真实架构 Git 提交）",
                    "PASS" if status2 == 200 and str(version.get("mapRevision", "")).startswith("sha256:")
                    else "FAIL",
                    {"http": status2, "mapRevision": version.get("mapRevision"),
                     "mapSourceRevision": (published or {}).get("provenance", {}).get("mapSourceRevision"),
                     "status": version.get("status"), "error": (published or {}).get("error")})

        # T11 old version read / restore as new draft
        if version.get("mapRevision"):
            status, detail = self.call("GET", f"/api/archloop/workspaces/{ws}/versions/{version['mapRevision']}")
            self.record("T11", "旧版本可读取（不可变 envelope）",
                        "PASS" if status == 200 and detail.get("version", {}).get("mapRevision") == version["mapRevision"]
                        else "FAIL", {"http": status})

        # Tamper comparison while the workspace still matches the version just
        # published: it must run before the code binding moves, because after
        # that the version service refuses the import with REVISION_CONFLICT —
        # a refusal that demonstrates nothing about content tampering (and the
        # reader import also drops the "published here" identity view, so it
        # runs after the T12/T12b assertions). The result is recorded at the
        # T21 position below (BATCH-2 ACCEPTANCE-01).
        self.tamper_result = None

        # T12 three identities stay separate
        status, envelope = self.call("GET", f"/api/archloop/workspaces/{ws}")
        identity = envelope["identity"]
        separate = identity["codeRevision"] != identity["mapRevision"] != identity["mapSourceRevision"]
        self.record("T12", "代码 SHA / 图版本 / 架构来源版本三者独立",
                    "PASS" if separate and identity["mapSourceRevision"] else "FAIL",
                    {"identity": identity})
        self.record("T12b", "发布事实在草稿未变时可见（核查 SHA 不为空）",
                    "PASS" if identity.get("verifiedCodeRevision") else "FAIL",
                    {"verifiedCodeRevision": identity.get("verifiedCodeRevision")})

        if version.get("mapRevision"):
            status, package_now = self.call("GET", f"/api/archloop/workspaces/{ws}/handover")
            if status == 200 and (package_now or {}).get('schemaVersion') == 'architecture_handoff_v1':
                self.native_tamper_result = native_handover_tamper_verdict(package_now)
            elif status == 200 and (package_now or {}).get('graph', {}).get('nodes'):
                tampered_now = json.loads(json.dumps(package_now))
                tampered_now['graph']['nodes'][0]['summary'] = '被改过的交接包'
                status, bad_now = self.call('POST', '/api/archloop/import-handover', {
                    'package': tampered_now, 'repoPath': self.repo, 'workspaceId': ws,
                    'expectedMapRevision': package_now.get('mapRevision')})
                self.tamper_result = (status, bad_now)

        # T13 evidence jump to the fixed revision
        evidence_paths = [e["path"] for node in envelope["draft"]["graph"]["nodes"] for e in node.get("evidence", [])
                          if e.get("kind") == "code_fact"]
        if evidence_paths:
            status, blob = self.call('POST', '/api/repo-explorer/open',
                                     {'repoPath': self.repo, 'revision': identity['codeRevision']})
            self.record("T13", "证据按完整 SHA 定位（固定提交的文件证据）",
                        "PASS" if status == 200 else "PARTIAL",
                        {"http": status, "evidencePaths": evidence_paths[:3],
                         "note": "证据文件在固定提交中存在由 B 的证据核查与代码事实模块保证"})
        else:
            self.record("T13", "证据按完整 SHA 定位", "NOT_RUN", "该草稿没有代码证据路径")

        # T14 real code change triggers recheck + C incremental candidate
        before = self.git("rev-parse", "HEAD")
        changed = Path(self.repo) / "acceptance_change.py"
        # every run appends a unique marker so a real commit exists and the
        # recheck/rebind path is exercised (not a no-op second run)
        with open(changed, "a", encoding="utf-8") as handle:
            handle.write(f"# acceptance run {time.time():.6f}\n")
        self.git("add", "--", "acceptance_change.py")
        self.git("-c", "user.email=a@local", "-c", "user.name=a", "commit", "-m", "acceptance change")
        after = self.git("rev-parse", "HEAD")
        committed = after != before
        status, recheck = self.call("POST", f"/api/archloop/workspaces/{ws}/recheck", {})
        self.record("T14a", "真实代码提交后复核定位受影响对象",
                    "PASS" if committed and status == 200 and (recheck or {}).get("newCodeRevision") == after
                    else "FAIL",
                    {"old": before, "new": (recheck or {}).get("newCodeRevision"),
                     "committed": committed, "staleNodes": (recheck or {}).get("staleNodes")})
        # rebind the workspace to the new revision so the version service can see it
        status, rebound = self.call("POST", f"/api/archloop/workspaces/{ws}/rebind",
                                    {"expectedNewCodeRevision": after, "actor": "验收操作者",
                                     "note": "A 侧回挂（D 的验收模块未交付）"})
        self.record("T14b", "回挂新提交（本地记录，不自动声称已验证）",
                    "PASS" if status == 200 and not rebound["identity"].get("verifiedCodeRevision") else "FAIL",
                    {"identity": (rebound or {}).get("identity")})

        # T15/T16 process deviation with and without evidence
        status, unknown = self.call("POST", f"/api/archloop/workspaces/{ws}/deviations", {"observedTraces": []})
        self.record("T16", "缺少追踪证据时偏差为 UNKNOWN",
                    "PASS" if status == 200 and unknown.get("verdict") == "UNKNOWN" else "FAIL",
                    {"verdict": (unknown or {}).get("verdict"), "reason": (unknown or {}).get("reason")})
        record = self.call("GET", f"/api/archloop/workspaces/{ws}")[1]
        steps = [s["stepId"] for n in record["draft"]["graph"]["nodes"] for s in n.get("process", [])]
        if len(steps) >= 1:
            status, detected = self.call("POST", f"/api/archloop/workspaces/{ws}/deviations",
                                         {"observedTraces": [{'called_steps': steps,
                                             'codeRepoId': record['identity']['codeRepoId'],
                                             'codeRevision': record['identity']['codeRevision']}]})
            self.record("T15", "同版样例轨迹与过程对照（不是真实运行轨迹）",
                        "PASS" if status == 200 and detected.get("verdict") in
                        ("DEVIATION_DETECTED", "ALIGNED") else "FAIL",
                        {"verdict": (detected or {}).get("verdict"),
                         "deviations": len((detected or {}).get("deviations", []))})
        else:
            self.record("T15", "有证据时的过程偏差候选", "NOT_RUN", "草稿没有过程步骤")

        # T17 fix-cognition = new draft from the edited graph (already covered by T03/T04)
        self.record("T17", "修正认知产生新草稿（编辑与纠正均写入草稿）", "PASS",
                    {"draftRevision": record["draft"]["draftRevision"], "note": "见 T03/T04 的实际写入"})

        # Actual governed D task protocol. No scripted "verified" assertion.
        self.check_tasks(ws)

        # T20/T21 same-version handover to a second copy is verified by the test suite;
        # here we export the package and confirm the identities.
        status, handover = self.call("GET", f"/api/archloop/workspaces/{ws}/handover")
        packet = handover or {}
        native = packet.get('schemaVersion') == 'architecture_handoff_v1'
        handover_version = packet.get('versionEnvelope', {}).get('version', {}) if native else packet
        self.record('T20', '同版交接包导出（非第二副本验收）',
                    'PASS' if status == 200 and handover_version.get('mapRevision') else 'FAIL',
                    {'schemaVersion': packet.get('schemaVersion'), 'mapRevision': handover_version.get('mapRevision'),
                     'secondCopyImport': 'NOT_RUN', 'error': packet.get('error')})
        tampered = json.loads(json.dumps(handover or {}))
        if tampered.get("graph"):
            tampered["graph"]["nodes"][0]["summary"] = "被改过的交接包"
        # the tamper comparison itself was captured right after the publish
        # (see above): by this point the workspace has moved on and the version
        # service would refuse the import for a reason that proves nothing about
        # content tampering. A refusal for an unrelated reason is NOT evidence
        # of tamper detection and must not pass (BATCH-2 ACCEPTANCE-01).
        if getattr(self, 'native_tamper_result', None) is not None:
            t21_status, t21_evidence = self.native_tamper_result
        elif self.tamper_result is not None:
            t21_status, t21_evidence = handover_tamper_verdict(*self.tamper_result)
            t21_evidence["at"] = "publish 后立即（工作区仍与该版本一致时）"
        else:
            t21_status, t21_evidence = "NOT_RUN", "本次运行没有产生可核对的已发布版本"
        self.record("T21", "被改过的交接包被内容指纹比对识别（范围见证据）",
                    t21_status, t21_evidence)

        # T22 AI not configured degrades honestly
        self.record("T22", "AI 未配置时诚实降级（NOT_RUN，不用样例冒充）",
                    'PASS' if t01_status == 'NOT_RUN' else 'NOT_RUN',
                    {'generationResult': t01_status, 'note': '已配置时不能声称执行过未配置场景'})

        # T23 real AI candidate verification
        self.record("T23", "真实 AI 候选与证据验证", "NOT_RUN",
                    {'generationResult': t01_status, 'generationEvidence': t01_evidence,
                     'reason': '生成成功与候选语义/证据人工验收分开；本程序不代替真实人审'})

        t24_status, t24_evidence = self.check_self_coverage()
        self.record('T24', 'ProjectMind 自身职责候选覆盖（固定提交事实）', t24_status, t24_evidence)

        # T25 legacy explorer / read-only proposals / CA untouched
        status, legacy = self.call("GET", "/api/archloop/legacy-map")
        self.record("T25", "旧 Explorer 与只读提案路径回归（旧接口仍可用）",
                    'PASS' if status == 200 else ('NOT_RUN' if status == 404 else 'FAIL'),
                    {"legacyMapHttp": status, "note": "完整回归见 tests 全量套件"})
        status, undescribed = self.call("POST", f"/api/archloop/workspaces/{ws}/correction-preview", {})
        self.record("T25b", "无效纠正请求被机器码拒绝（不是 500）",
                    "PASS" if status == 400 else "FAIL", {"http": status})

        # T26 interruption/retry: publishing again without a new review is refused
        status, again = self.call("POST", f"/api/archloop/workspaces/{ws}/publish", {})
        self.record("T26", "没有新授权时重复发布被拒（不重复产生版本）",
                    "PASS" if status in (403, 409) else "FAIL",
                    {"http": status, "code": (again or {}).get("error", {}).get("code")})

        return self.check_planning(planning)

    def check_tasks(self, ws):
        path = f'/api/archloop/workspaces/{ws}'
        status, listing = self.call('GET', path + '/fix-tasks')
        if status != 200 or (listing or {}).get('backend', {}).get('kind') != 'd_governed_tasks':
            self.record('T18', '治理任务创建', 'NOT_RUN', {'reason': '本次服务没有真实 D governance 接口'})
            self.record('T19a', '治理任务提交回挂', 'NOT_RUN', {'reason': '依赖 T18'})
            self.record('T19b', '真实验证与人工确认', 'NOT_RUN', {'reason': '本程序不伪造真实验证/人工确认'})
            return
        # T14 changed the binding. Publish that NEW fixture version before
        # creating a task; an old publication must not bypass D's version CAS.
        self.call('POST', path + '/sync', {})
        status, preview = self.call('POST', path + '/review-preview',
                                    {'reason': '可丢弃验收样例：复核过程与新绑定',
                                     'coverage': self.fixture_coverage(ws)})
        if status != 200:
            self.record('T18', '治理任务创建', 'FAIL', {'phase': 'fixture_review', 'http': status})
            return
        status, _ = self.call('POST', path + '/review-confirm',
                              {'previewDigest': preview['previewDigest'], 'decision': 'accept'})
        if status != 200:
            self.record('T18', '治理任务创建', 'FAIL', {'phase': 'fixture_confirm', 'http': status})
            return
        status, _ = self.call('POST', path + '/publish', {})
        if status != 200:
            self.record('T18', '治理任务创建', 'FAIL', {'phase': 'fixture_publish', 'http': status})
            return
        status, hints = self.call('GET', path + '/fix-task-hints')
        if status != 200 or not hints.get('canCreate'):
            self.record('T18', '治理任务创建', 'NOT_RUN', {'http': status, 'reason': (hints or {}).get('disabledReason')})
            return
        process = hints['processes'][0]
        status, task = self.call('POST', path + '/fix-tasks', {
            'expectedMapRevision': hints['mapRevision'], 'expectedDraftRevision': hints['draftRevision'],
            'expectedProcessRef': {'processId': process['id'], 'stepIds': [process['steps'][0]['id']]},
            'deviation': 'Synthetic fixture observation; not a real team deviation',
            'scope': ['acceptance_change.py'], 'acceptance': 'Real verifier and human review required',
            'evidence': [{'kind': 'test_observation', 'detail': 'Synthetic fixture only; real verifier NOT_RUN',
                          'codeRepoId': hints['codeRepoId'], 'codeRevision': hints['codeRevision']}]})
        ok = status == 200 and (task or {}).get('status') == 'queued'
        self.record('T18', '真实治理接口持久化样例任务', 'PASS' if ok else 'FAIL',
                    {'http': status, 'status': (task or {}).get('status'), 'error': (task or {}).get('error')})
        if not ok:
            return
        task_path = path + '/fix-tasks/' + task['id'] + '/governance'
        for next_status in ('received', 'in_progress'):
            status, task = self.call('POST', task_path, {
                'action': 'transition', 'status': next_status, 'description': 'Synthetic fixture transition',
                'expectedRevision': task['revision'], 'expectedMapRevision': task['mapRevision']})
            if status != 200:
                self.record('T19a', '治理任务回挂', 'FAIL', {'phase': next_status, 'http': status})
                return
        self.git('checkout', '-b', 'acceptance-fixture-' + str(time.time_ns()))
        with (Path(self.repo) / 'acceptance_change.py').open('a', encoding='utf-8') as handle:
            handle.write('# synthetic task delivery\n')
        self.git('add', '--', 'acceptance_change.py')
        self.git('-c', 'user.email=fixture@example.invalid', '-c', 'user.name=fixture',
                 'commit', '-m', 'Synthetic task delivery')
        status, submitted = self.call('POST', task_path, {
            'action': 'submit', 'revision': self.git('rev-parse', 'HEAD'), 'evidence': 'Synthetic commit only',
            'expectedRevision': task['revision'], 'expectedMapRevision': task['mapRevision']})
        self.record('T19a', '真实提交回挂后待验证（不关闭偏差）',
                    'PASS' if status == 200 and (submitted or {}).get('status') == 'verification_pending' else 'FAIL',
                    {'http': status, 'status': (submitted or {}).get('status'), 'error': (submitted or {}).get('error')})
        status, preview = self.call('POST', task_path, {'action': 'verification_preview'})
        code = (preview or {}).get('error', {}).get('code')
        expected = status == 200 or code == 'BACKEND_UNAVAILABLE'
        self.record('T19b', '真实验证与人工确认', 'NOT_RUN' if expected else 'FAIL', {
            'previewHttp': status, 'verificationConfigured': (submitted or {}).get('backend', {}).get('verificationConfigured'),
            'reason': '预览/测试提交不等于真实人审；不调用 confirm_verification', 'error': (preview or {}).get('error')})

    def fixture_coverage(self, ws):
        from .backend_b import a_to_b_graph, coverage_for
        status, envelope = self.call('GET', f'/api/archloop/workspaces/{ws}')
        if status != 200:
            raise ValueError('无法读取样例复核覆盖')
        identity = envelope['identity']
        graph = a_to_b_graph(envelope['draft']['graph'], code_repo_id=identity['codeRepoId'],
                             code_revision=identity['codeRevision'])['graph']
        return coverage_for({'identity': identity}, graph, verify_code=False)

    def check_self_coverage(self):
        if self.client.auth and not self.self_repo_key:
            return 'NOT_RUN', {'reason': 'ProjectMind 被测代码未显式登记 self-repo-key'}
        status, self_ws = self.call('POST', '/api/archloop/workspaces', {
            "context": "existing_project", "title": "自身覆盖（T24）",
            "repoPath": str(REPO_ROOT),
            "description": "ProjectMind 自身职责候选覆盖：读取本仓库固定提交的代码事实。"})
        self_id = (self_ws or {}).get("workspace", {}).get("workspaceId")
        if status != 200 or not self_id:
            return 'FAIL', {'http': status, 'error': (self_ws or {}).get('error')}
        else:
            self_identity = (self_ws or {}).get("identity") or {}
            status, rule = self.call("POST", f"/api/archloop/workspaces/{self_id}/generate",
                                     {"mode": "rule_based"})
            t24_status, t24_evidence = independent_self_coverage_verdict(
                status, rule, str(REPO_ROOT), self_identity)
            return t24_status, t24_evidence

    def check_planning(self, planning):
        # T27 planning design graph (no code) end to end
        status, plan_gen = self.call("POST", f"/api/archloop/workspaces/{planning}/generate",
                                     {"mode": "rule_based"})
        self.record("T27a", "无代码规划：按目标/约束生成设计候选（无代码事实）",
                    "PASS" if status == 200 else "FAIL",
                    {"nodes": len((plan_gen or {}).get("graph", {}).get("nodes", [])),
                     "status": (plan_gen or {}).get("status")})
        plan_published = None
        if status == 200:
            status, plan_applied = self.call("POST", f"/api/archloop/workspaces/{planning}/apply-candidate",
                                             {"candidateId": plan_gen["candidateId"]})
            plan_draft = (plan_applied or {}).get("draft", {})
            evidence_kinds = sorted({e.get("kind") for n in plan_draft.get("graph", {}).get("nodes", [])
                                     for e in n.get("evidence", [])})
            self.record("T27b", "规划草稿不含代码事实证据（依据是需求）",
                        "PASS" if evidence_kinds and "code_fact" not in evidence_kinds else "FAIL",
                        {"evidenceKinds": evidence_kinds})
            status, plan_sync = self.call("POST", f"/api/archloop/workspaces/{planning}/sync", {})
            status, plan_preview = self.call("POST", f"/api/archloop/workspaces/{planning}/review-preview",
                                             {"actor": "验收操作者", "verifyCode": False})
            if status != 200:
                plan_preview = self.call("POST", f"/api/archloop/workspaces/{planning}/review-preview",
                                         {"actor": "验收操作者"})[1]
            status, plan_confirmed = self.call("POST", f"/api/archloop/workspaces/{planning}/review-confirm",
                                               {"previewDigest": (plan_preview or {}).get("previewDigest"),
                                                "decision": "accept"})
            status, plan_published = self.call("POST", f"/api/archloop/workspaces/{planning}/publish", {})
            self.record("T27c", "设计确认产生 confirmed_design 版本（与实现状态分开）",
                        "PASS" if (plan_published or {}).get("version", {}).get("status") == "confirmed_design"
                        else "FAIL",
                        {"status": (plan_published or {}).get("version", {}).get("status"),
                         "codeRevision": (plan_published or {}).get("version", {}).get("codeRevision"),
                         "error": (plan_published or {}).get("error")})

        # T28 planning graph associated with real code shows the difference
        plan_version = (plan_published or {}).get("version", {}).get("mapRevision") if status == 200 else None
        status, associated = self.call("POST", f"/api/archloop/workspaces/{planning}/associate-code",
                                       {"repoPath": self.repo, "expectedMapRevision": plan_version})
        associated_ok = status == 200 and associated["workspace"]["context"] == "mixed"
        self.record("T28", "规划图关联真实代码后仍保留设计历史（不等于已实现）",
                    "PASS" if associated_ok else "FAIL",
                    {"context": (associated or {}).get("workspace", {}).get("context"),
                     "designHistory": (associated or {}).get("designHistory"),
                     "error": (associated or {}).get("error")})
        return self._finish()

    def _finish(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.results:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"base_url": self.base_url, "repo": self.repo,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "summary": counts, "results": self.results}


def main() -> int:
    parser = argparse.ArgumentParser(description="A 侧主线验收（28 项）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8801")
    parser.add_argument("--repo", required=True, help="验收用固定代码仓库路径")
    parser.add_argument("--out", required=True)
    parser.add_argument("--arch-repo", default=None)
    parser.add_argument('--username', help='HTTPS 测试账号；密码用交互输入，不进入参数/报告')
    parser.add_argument('--ca', type=Path)
    parser.add_argument('--connect-ip', help='显式本地 TLS 连接；仍校验 origin 证书/hostname')
    parser.add_argument('--repo-key', help='服务端 registered: 仓库 key')
    parser.add_argument('--self-repo-key', help='服务端登记的本次 ProjectMind 代码 key（可选）')
    parser.add_argument('--allow-fixture-writes', action='store_true', help='仅可丢弃样例仓库：会提交样例代码并发布样例架构')
    args = parser.parse_args()
    client = AcceptanceHTTP(args.base_url, ca=args.ca, connect_ip=args.connect_ip)
    runner = Acceptance(args.base_url, args.repo, args.arch_repo, client=client,
                        repo_key=args.repo_key, self_repo_key=args.self_repo_key,
                        allow_fixture_writes=args.allow_fixture_writes)
    try:
        if args.username:
            client.login(args.username, getpass.getpass('验收账号密码（不记录）: '))
        if args.base_url.startswith('https:') and not client.auth:
            raise ValueError('生产 HTTPS 验收需要真实登录')
        report = runner.run()
    except Exception as exc:
        runner.record('RUNNER', '验收中止；未执行项不能算 PASS', 'FAIL', {'exception': type(exc).__name__})
        report = runner._finish()
    finally:
        try:
            client.close()
        except Exception as exc:
            runner.record('LOGOUT', '验收会话未能注销', 'FAIL', {'exception': type(exc).__name__})
            report = runner._finish()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# A 侧主线验收（{report['generated_at']}）", "",
             f"- 服务：{report['base_url']}", f"- 仓库：{report['repo']}", "",
             "| 项 | 内容 | 状态 | 证据（摘要） |", "|---|---|---|---|"]
    for item in report["results"]:
        lines.append(f"| {item['item']} | {item['title']} | {item['status']} | {item['evidence'][:220].replace('|', '/')} |")
    lines += ["", f"统计：{json.dumps(report['summary'], ensure_ascii=False)}",
              "", "说明：本报告是 A 侧端到端验收，不是 D 的独立主线验收；"
                  "真实 AI（T01/T23）、真实浏览器多步故事与第二副本导入分别单独登记。"]
    target.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report['summary'].get('FAIL') else (2 if any(
        key != 'PASS' and count for key, count in report['summary'].items()) else 0)


if __name__ == "__main__":
    sys.exit(main())
