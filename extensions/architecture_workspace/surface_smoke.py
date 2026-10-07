"""Executable B surfaces, only with newly created and isolated Git fixtures.

The C producer, local transport metadata and human decisions are test doubles.
No HTTP server, A UI, real C inference or D handoff is exercised here. Review
session/reference bindings stay in memory and are never included in the callable
trace; the V1 private SQLite intent store retains internal retry responses.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from .errors import WorkspaceError, require
from .git_publication import code_identity
from .proposals import API_VERSION
from .review import HumanReviewGateway
from .schema import canonical, digest
from .service import WorkspaceService
from .smoke import git, graph, init
from .surfaces import CollaborationAPI, UserWorkspaceAPI, workspace_context


FIXTURE_ORIGIN = "https://example.invalid/projectmind-b-fixture.git"
FIXTURE_BRANCH = "architecture/candidates/test-fixture"
PRIVATE_FIELDS = frozenset({"auth", "sessionId", "session_id", "csrfToken", "csrf_token",
    "confirmationToken", "confirmation_token", "publicationToken", "publication_token",
    "tokenHash", "sessionBinding"})


def _new_root(output, fixture_only):
    require(fixture_only is True, detail="只允许显式的新建测试夹具运行")
    raw = Path(output)
    require(raw.is_absolute(), detail="输出必须是新的绝对路径")
    require(not raw.is_symlink(), detail="输出不能是符号链接")
    root = raw.resolve()
    require(not root.exists(), detail="输出目录已存在；保留旧证据并选择新目录")
    require(not any((ancestor / ".git").exists() for ancestor in (root, *root.parents)),
            detail="输出必须位于真实 Git 工作副本之外")
    root.mkdir(parents=True, exist_ok=False)
    return root


def _documents(service):
    with service.store.transaction() as db:
        return list(db.execute("SELECT kind,id,body FROM documents ORDER BY kind,id"))


def _proposal(context, candidates, proposal_id, kind):
    packet = {"apiVersion": API_VERSION, "proposalId": proposal_id, "kind": kind,
        "basis": copy.deepcopy(context), "generation": {"source": "rule_based",
            "runId": "surface-smoke-c-test-double", "fixtureOnly": True},
        "candidates": copy.deepcopy(candidates), "unknowns": [
            "C_TEST_DOUBLE: fixture suggestions do not demonstrate real C inference"]}
    packet["proposalDigest"] = digest(packet)
    return packet


def _assert_public(value, secrets_in_memory):
    def walk(item):
        if isinstance(item, dict):
            assert not (set(item) & PRIVATE_FIELDS), "Private field in public trace"
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, str):
            assert not item.startswith(("/Users/", "/private/", "/var/", "file://")), \
                "Absolute local source in public trace"

    walk(value)
    encoded = canonical(value)
    assert all(secret not in encoded for secret in secrets_in_memory), "Private value in trace"


def run(output, *, test_fixture_only=False):
    root = _new_root(output, test_fixture_only)
    code, architecture = root / "code", root / "architecture"
    init(code, "main")
    init(architecture, FIXTURE_BRANCH)
    git(code, "remote", "add", "origin", FIXTURE_ORIGIN)
    (code / "demo.py").write_text("def demo():\n    return 1\n", encoding="utf-8")
    git(code, "add", ".")
    git(code, "commit", "-m", "isolated actual code fixture")
    code_revision, repo_id = git(code, "rev-parse", "HEAD"), code_identity(code)
    original_code_status = git(code, "status", "--porcelain", "--untracked-files=all")
    assert original_code_status == ""
    service = WorkspaceService(root / "state", code_repositories=[code],
        architecture_repo=architecture, architecture_branch=FIXTURE_BRANCH)
    require(git(code, "remote", "get-url", "origin") == FIXTURE_ORIGIN
            and git(architecture, "branch", "--show-current") == FIXTURE_BRANCH,
            detail="模拟人审只能针对本程序新建的独立测试仓库")
    ws = service.open_workspace(mode="existing_project", code_repo_id=repo_id,
                                code_revision=code_revision)
    boundary = {"peer": "127.0.0.1", "host": "127.0.0.1:18832",
                "origin": "http://127.0.0.1:18832"}
    secrets_in_memory, trace = [], []

    def trusted_user(instance, workspace, *, source_id=None):
        gateway = HumanReviewGateway(instance, boundary["origin"])
        session = gateway.create_session("TEST_ONLY_SIMULATED_HUMAN", **boundary)
        # Session creation and real handler metadata have no trace entry.
        secrets_in_memory.extend(session.values())
        auth = {**boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}
        return UserWorkspaceAPI(instance, gateway, workspace["workspaceId"],
                                source_registration_id=source_id), auth

    user, auth = trusted_user(service, ws)

    def call(consumer, surface, action, values=None, *, user_auth=None, error=None):
        request = {"apiVersion": API_VERSION, "requestId": f"surface-call-{len(trace) + 1}",
                   **copy.deepcopy(values or {})}
        response = (surface.call(action, request, auth=user_auth) if user_auth is not None
                    else surface.call(action, request))
        if error is None:
            assert "error" not in response, response
        else:
            assert response.get("error", {}).get("code") == error, response
        entry = {"consumer": consumer, "surface": type(surface).__name__, "action": action,
                 "request": request, "response": response}
        _assert_public(entry, secrets_in_memory)
        trace.append(copy.deepcopy(entry))
        return response

    def user_call(action, values=None, *, error=None, api=user, session_auth=auth):
        return call("A_UI_TEST_DOUBLE", api, action, values, user_auth=session_auth, error=error)

    def approve(api, session_auth, prepared):
        context = prepared["context"]
        candidate_graph = prepared["data"]["draft"]["graph"]
        coverage = {"scope": "all", **{key: [item["id"] for item in candidate_graph[key]]
                    for key in ("nodes", "edges", "processes", "evidence")}}
        preview = user_call("previewReview", {"context": context,
            "reason": "TEST ONLY: simulated local operator decision", "coverage": coverage,
            "limits": ["Isolated fixture, not real ProjectMind owner approval"], "verifyCode": False},
            api=api, session_auth=session_auth)
        confirmed = user_call("confirmReview", {"context": context,
            "previewId": preview["data"]["previewId"], "previewDigest": preview["data"]["previewDigest"],
            "decision": "accept"}, api=api, session_auth=session_auth)
        # Capture private values only for leak assertions; never serialize them.
        secrets_in_memory.append(api._previews[preview["data"]["previewId"]]["result"]["confirmationToken"])
        secrets_in_memory.append(api._reviews[confirmed["data"]["reviewId"]]["result"]["publicationToken"])
        published = user_call("publishVersion", {"context": context,
            "reviewId": confirmed["data"]["reviewId"]}, api=api, session_auth=session_auth)
        assert published["context"] == context
        return preview, published

    initial = user_call("openWorkspace", {"context": workspace_context(ws)})
    worker = CollaborationAPI(service, ws["workspaceId"], role="C")
    initial_graph = graph(repo_id, code_revision)
    alternative = copy.deepcopy(initial_graph)
    alternative["nodes"][0]["title"] = "Alternate C_TEST_DOUBLE candidate"
    bootstrap = _proposal(initial["context"], [
        {"candidateId": "bootstrap-selected", "graph": initial_graph},
        {"candidateId": "bootstrap-alternate", "graph": alternative}], "fixture-bootstrap", "bootstrap")
    before = _documents(service)
    call("C_TEST_DOUBLE", worker, "validateProposal", {"context": initial["context"], "proposal": bootstrap})
    assert _documents(service) == before
    prepared = user_call("prepareDraft", {"context": initial["context"], "graph": initial_graph,
        "origin": "rule_based", "proposal": bootstrap, "selectedCandidateId": "bootstrap-selected"})
    assert prepared["data"]["draft"]["bootstrapSelection"]["candidateId"] == "bootstrap-selected"
    context = prepared["context"]
    candidates = [
        {"candidateId": "candidate-helper", "operations": [
            {"operationId": "op-helper", "op": "node.add", "source": "rule_based", "value": {
                "id": "node-helper", "title": "Fixture helper", "responsibility": "Planned collaboration",
                "implementationStatus": "planned", "interfaces": [], "evidenceIds": ["goal-demo"]}},
            {"operationId": "op-collaboration", "op": "edge.add", "source": "rule_based", "value": {
                "id": "edge-helper", "from": "node-demo", "to": "node-helper",
                "type": "functional_collaboration", "label": "Delegates", "evidenceIds": ["goal-demo"]}}]},
        {"candidateId": "candidate-step", "operations": [
            {"operationId": "op-step", "op": "step.update", "id": "step-demo",
                "processId": "process-demo", "source": "rule_based", "changes": {"title": "Suggested step"}}]},
        {"candidateId": "candidate-title", "operations": [
            {"operationId": "op-title", "op": "node.update", "id": "node-demo",
                "source": "rule_based", "changes": {"title": "Unproven replacement"}}]},
    ]
    proposal = _proposal(context, candidates, "fixture-distinct-patch", "patch")
    assert proposal["proposalId"] != prepared["data"]["draft"]["proposalId"]
    before = _documents(service)
    before_arch_head = git(architecture, "rev-parse", "HEAD")
    call("C_TEST_DOUBLE", worker, "validateProposal", {"context": context, "proposal": proposal})
    assert _documents(service) == before and git(architecture, "rev-parse", "HEAD") == before_arch_head
    operations = copy.deepcopy(candidates[0]["operations"] + candidates[1]["operations"])
    operations[-1].update(source="human", changes={"title": "Human corrected fixture step"})
    rejected_reason = "TEST ONLY: no evidence supports replacing the existing fixture title"
    selection = [
        {"candidateId": "candidate-helper", "decision": "accept", "operationIds": ["op-helper", "op-collaboration"]},
        {"candidateId": "candidate-step", "decision": "modify", "operationIds": ["op-step"]},
        {"candidateId": "candidate-title", "decision": "reject", "operationIds": [], "reason": rejected_reason},
    ]
    save_request = {"context": context, "proposal": proposal, "selection": selection, "operations": operations}
    saved = user_call("saveDraft", save_request)
    assert saved["context"]["draftRevision"] == context["draftRevision"] + 1
    assert saved["data"]["draft"]["operations"] == operations
    assert next(node for node in saved["data"]["draft"]["graph"]["nodes"]
                if node["id"] == "node-demo")["title"] == "Fixture function"
    stale = user_call("saveDraft", save_request, error="REVISION_CONFLICT")
    assert stale["currentContext"] == saved["context"]
    denied = user_call("publishVersion", {"context": saved["context"], "reviewId": "not-a-review"},
                       error="REQUEST_FORBIDDEN")
    call("C_TEST_DOUBLE", worker, "publishVersion", {"context": saved["context"]}, error="REQUEST_FORBIDDEN")
    assert service.graph_snapshot(ws["workspaceId"])["versionEnvelope"] is None
    preview, published = approve(user, auth, saved)
    rejected = preview["data"]["preview"]["rejectedCandidates"]
    assert rejected == [{"proposalId": proposal["proposalId"], "candidateId": "candidate-title",
                         "reason": rejected_reason}]
    envelope, reference = published["data"]["versionEnvelope"], published["data"]["currentVersionRef"]
    assert envelope["version"]["review"]["rejectedCandidates"] == rejected
    assert envelope["version"]["review"]["appliedOperations"] == operations
    assert envelope["version"]["verifiedCodeRevision"] is None
    d = CollaborationAPI(service, ws["workspaceId"], role="D", allowed_map_revisions=(reference["mapRevision"],))
    exported = call("D_TEST_DOUBLE", d, "exportExactVersion", {"versionRef": reference})
    assert exported["data"]["versionEnvelope"] == envelope

    code_clone, arch_clone = root / "receiver-code", root / "receiver-architecture"
    for source, target in ((code, code_clone), (architecture, arch_clone)):
        subprocess.run(["git", "clone", str(source), str(target)], check=True, capture_output=True)
    git(code_clone, "remote", "set-url", "origin", FIXTURE_ORIGIN)
    assert code_identity(code_clone) == repo_id
    receiver = WorkspaceService(root / "receiver-state", code_repositories=[code_clone],
        architecture_repo=arch_clone, architecture_branch=FIXTURE_BRANCH)
    receiver_ws = receiver.open_workspace(mode="existing_project", map_id=ws["mapId"],
        code_repo_id=repo_id, code_revision=code_revision)
    receiver_api, receiver_auth = trusted_user(receiver, receiver_ws, source_id="fixture-architecture-source")
    imported = call("D_SECOND_CLIENT_TEST_DOUBLE", receiver_api, "importExactVersion", {
        "context": workspace_context(receiver_ws), "sourceRegistrationId": "fixture-architecture-source",
        "versionRef": reference}, user_auth=receiver_auth)
    assert imported["data"]["versionEnvelope"]["version"] == envelope["version"]
    assert imported["data"]["currentVersionRef"] == reference
    assert git(arch_clone, "rev-parse", "HEAD") == reference["mapSourceRevision"]

    planning = service.open_workspace(mode="planning")
    planning_api, planning_auth = trusted_user(service, planning)
    plan_graph = graph()
    plan_proposal = _proposal(workspace_context(planning), [
        {"candidateId": "planning-selected", "graph": plan_graph}], "fixture-planning-bootstrap", "bootstrap")
    plan_worker = CollaborationAPI(service, planning["workspaceId"], role="C")
    call("C_PLANNING_TEST_DOUBLE", plan_worker, "validateProposal", {
        "context": workspace_context(planning), "proposal": plan_proposal})
    planned = user_call("prepareDraft", {"context": workspace_context(planning), "graph": plan_graph,
        "origin": "rule_based", "proposal": plan_proposal, "selectedCandidateId": "planning-selected"},
        api=planning_api, session_auth=planning_auth)
    _, design = approve(planning_api, planning_auth, planned)
    design_packet = design["data"]["versionEnvelope"]["version"]
    assert design_packet["status"] == "confirmed_design"
    assert all(design_packet[key] is None for key in ("codeRepoId", "codeRevision", "verifiedCodeRevision"))
    planning_view = user_call("readView", api=planning_api, session_auth=planning_auth)
    associated = user_call("associateCode", {"context": planning_view["context"],
        "codeRepoId": repo_id, "codeRevision": code_revision}, api=planning_api, session_auth=planning_auth)
    mixed = user_call("prepareDraft", {"context": associated["context"], "graph": graph(repo_id, code_revision),
        "origin": "manual"}, api=planning_api, session_auth=planning_auth)
    assert mixed["context"]["mode"] == "mixed" and mixed["status"] == "unconfirmed"
    assert mixed["data"]["reviewRequired"] is True
    linked_ws = service.open_workspace(workspace_id=planning["workspaceId"])
    assert linked_ws["designHistory"] == [design_packet["mapRevision"]]
    assert service.get_version(planning["workspaceId"], design_packet["mapRevision"])["version"] == design_packet
    assert git(code, "rev-parse", "HEAD") == code_revision
    assert git(code, "status", "--porcelain", "--untracked-files=all") == original_code_status
    assert git(code_clone, "rev-parse", "HEAD") == code_revision
    assert git(code_clone, "status", "--porcelain", "--untracked-files=all") == ""

    source_root = Path(__file__).resolve().parents[2]
    candidate_paths = ("surface_smoke.py", "surfaces.py", "proposals.py", "service.py")
    file_hashes = {"extensions/architecture_workspace/" + name:
        hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in candidate_paths}
    result = {"fixtureOnly": True, "apiVersion": API_VERSION, "contractStatus": "A_REVIEW_PENDING",
        "candidateProducer": "C_TEST_DOUBLE", "humanActor": "TEST_ONLY_SIMULATED_HUMAN",
        "realAUi": "NOT_RUN", "realCInference": "NOT_RUN", "realDHandoff": "NOT_RUN", "realHttp": "NOT_RUN",
        "implementation": {"head": git(source_root, "rev-parse", "HEAD"),
            "worktreeClean": git(source_root, "status", "--porcelain", "--untracked-files=all") == "",
            "candidateFileSha256": file_hashes},
        "fixtureIdentity": {"codeRepoId": repo_id, "codeRevision": code_revision,
            "mapId": ws["mapId"], "architectureBranch": FIXTURE_BRANCH,
            "publishedVersionRef": reference, "architectureFinalHead": git(architecture, "rev-parse", "HEAD")},
        "checks": {"bootstrapSelected": True, "validationReadOnly": True, "selectionApplied": True,
            "rejectReasonPreserved": True, "staleCASRejected": True, "noReviewPublishDenied": True,
            "workerWriteDenied": True, "publicSecretsAbsent": True, "sameSessionPublication": True,
            "dExactExportEqual": True, "secondClonePacketEqual": True, "secondCloneVersionRefEqual": True,
            "planningNullBindings": True, "designHistoryPreserved": True, "mixedDraftRequiresReview": True,
            "sourceCodeUnchanged": True, "receiverCodeUnchanged": True},
        "calls": trace, "exchange": envelope, "receiverExchange": imported["data"]["versionEnvelope"],
        "planningExchange": design["data"]["versionEnvelope"], "mixedDraftContext": mixed["context"],
        "conflictExamples": {"staleCAS": stale, "noReview": denied}}
    _assert_public(result, secrets_in_memory)
    (root / "SURFACE_SMOKE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-fixture-only", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.output, test_fixture_only=args.test_fixture_only)
    except WorkspaceError as exc:
        print(json.dumps({"result": "FAIL", **exc.as_dict()}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps({"result": "PASS", "fixtureOnly": True, "calls": len(result["calls"]),
        "checks": len(result["checks"]), "realAUi": "NOT_RUN", "realCInference": "NOT_RUN",
        "realDHandoff": "NOT_RUN", "realHttp": "NOT_RUN"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
