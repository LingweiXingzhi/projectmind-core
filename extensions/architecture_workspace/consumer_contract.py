"""Executable consumer examples, ONLY for smoke-created isolated Git fixtures.

This does not implement A HTTP/UI, C inference, or D handoff. It exercises their
calls to B, captures actual responses, and removes session/publication secrets.
"""
from __future__ import annotations

import copy
from pathlib import Path
import subprocess

from .errors import WorkspaceError, require
from .git_publication import code_identity, read_git
from .review import HumanReviewGateway
from .service import WorkspaceService, overlaps
from .smoke import graph


PRIVATE_FIELDS = frozenset({"sessionId", "session_id", "csrfToken", "csrf_token",
                            "confirmationToken", "confirmation_token",
                            "publicationToken", "publication_token"})


def public_copy(value):
    if isinstance(value, dict):
        return {key: "<PRIVATE_RUNTIME_VALUE>" if key in PRIVATE_FIELDS and item is not None
                else public_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [public_copy(item) for item in value]
    return value


def exercise_consumers(service, *, output, code_repo, architecture_repo,
                       code_repo_id, code_revision, test_fixture_only=False):
    require(test_fixture_only is True, detail="接入样例只能在显式测试夹具运行")
    code_repo, architecture_repo = Path(code_repo).resolve(), Path(architecture_repo).resolve()
    root = Path(output).resolve()
    require(not any(overlaps(root, path) for path in (code_repo, architecture_repo, service.store.root)))
    require(service.publisher is not None and service.publisher.repo == architecture_repo
            and service.publisher.branch == "architecture/candidates/test-fixture",
            detail="必须使用 smoke 创建的独立测试架构分支")
    require(read_git(code_repo, "config", "--get", "remote.origin.url").decode().strip()
            == "https://example.invalid/projectmind-b-fixture.git",
            detail="不允许对真实项目模拟审核")
    root.mkdir(parents=True, exist_ok=False)
    trace = []
    code_head = read_git(code_repo, "rev-parse", "HEAD")
    code_status = read_git(code_repo, "status", "--porcelain", "--untracked-files=all")

    def call(consumer, function, *args, **kwargs):
        result = function(*args, **kwargs)
        trace.append({"consumer": consumer, "function": function.__name__,
                      "args": public_copy(list(args)), "kwargs": public_copy(kwargs),
                      "result": public_copy(result)})
        return result

    def conflict(code, consumer, function, *args, **kwargs):
        try:
            function(*args, **kwargs)
        except WorkspaceError as exc:
            if exc.code != code:
                raise
            entry = {"consumer": consumer, "function": function.__name__,
                     "args": public_copy(list(args)), "kwargs": public_copy(kwargs),
                     "result": exc.as_dict()}
            trace.append(entry)
            return entry
        raise AssertionError("Expected " + code)

    ws = call("A", service.open_workspace, mode="existing_project",
              code_repo_id=code_repo_id, code_revision=code_revision)
    draft = call("C via A", service.create_draft, ws["workspaceId"],
                 graph=graph(code_repo_id, code_revision), origin="rule_based")
    proposal_id = draft["proposalId"]
    candidates = [
        {"proposalId": proposal_id, "candidateId": "candidate-add-helper",
         "operations": [
             {"op": "node.add", "value": {"id": "node-helper", "title": "Helper",
              "responsibility": "Candidate fixture collaboration", "implementationStatus": "planned",
              "interfaces": [], "evidenceIds": ["goal-demo"]}},
             {"op": "edge.add", "value": {"id": "edge-helper", "from": "node-demo",
              "to": "node-helper", "type": "functional_collaboration", "label": "Delegates",
              "evidenceIds": ["goal-demo"]}}]},
        {"proposalId": proposal_id, "candidateId": "candidate-step-title",
         "operations": [{"op": "step.update", "processId": "process-demo", "id": "step-demo",
                         "changes": {"title": "Suggested fixture step"}}]},
        {"proposalId": proposal_id, "candidateId": "candidate-unproven-title",
         "operations": [{"op": "node.update", "id": "node-demo",
                         "changes": {"title": "Unproven replacement"}}]},
    ]
    selected = copy.deepcopy(candidates[0]["operations"])
    for i, operation in enumerate(selected):
        operation.update(source="rule_based", operationId="operation-accept-" + str(i))
    corrected = copy.deepcopy(candidates[1]["operations"][0])
    corrected.update(changes={"title": "Human corrected fixture step"},
                     source="human", operationId="operation-modified")
    selected.append(corrected)
    rejected = [{"proposalId": proposal_id, "candidateId": candidates[2]["candidateId"],
                 "reason": "TEST ONLY: missing support for replacing this title"}]
    context = {"expected_draft_revision": draft["draftRevision"],
               "base_map_revision": draft["baseMapRevision"], "proposal_id": proposal_id}
    edited = call("A selected C fixture operations", service.apply_draft_operations,
                  draft["draftId"], operations=selected, **context)
    conflicts = {
        "REVISION_CONFLICT": conflict("REVISION_CONFLICT", "A stale client",
             service.apply_draft_operations, draft["draftId"], operations=selected, **context),
        "STALE_CONTEXT": conflict("STALE_CONTEXT", "C wrong proposal", service.apply_draft_operations,
             draft["draftId"], operations=selected, **{**context,
             "expected_draft_revision": edited["draftRevision"], "proposal_id": "proposal-other"}),
    }
    invalid = graph(code_repo_id, code_revision)
    invalid["evidence"][1]["path"] = "../private"
    conflicts["EVIDENCE_MISMATCH"] = conflict("EVIDENCE_MISMATCH", "C invalid evidence",
             service.create_draft, ws["workspaceId"], graph=invalid)
    conflicts["HUMAN_REVIEW_REQUIRED"] = conflict("HUMAN_REVIEW_REQUIRED", "C no approval",
             service.publish_reviewed_graph, draft["draftId"],
             publication_token="not-an-approval-" * 3, expected_map_revision=None)
    reopened = call("A refresh", service.get_draft, draft["draftId"])
    assert reopened == edited and service.graph_snapshot(ws["workspaceId"])["versionEnvelope"] is None
    gateway = HumanReviewGateway(service, "http://127.0.0.1:18832")
    boundary = {"peer": "127.0.0.1", "host": "127.0.0.1:18832", "origin": "http://127.0.0.1:18832"}
    session = call("A synthetic trusted request", gateway.create_session,
                   "TEST_ONLY_SIMULATED_HUMAN", **boundary)
    auth = {**boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}
    review_context = {"expected_draft_revision": edited["draftRevision"],
                      "expected_map_revision": edited["baseMapRevision"], "proposal_id": proposal_id,
                      "code_repo_id": code_repo_id, "code_revision": code_revision}
    coverage = {"scope": "all", **{key: [item["id"] for item in edited["graph"][key]]
                for key in ("nodes", "edges", "processes", "evidence")}}
    preview = call("A preview", gateway.preview_review, draft["draftId"], auth=auth,
                   **review_context, reason="TEST ONLY: simulated consumer selection",
                   coverage=coverage, limits=["C fixture, not real C inference or owner approval"],
                   verify_code=False, rejected_candidates=rejected)
    approval = call("A simulated confirmation", gateway.confirm_review, draft["draftId"], auth=auth,
                    **review_context, confirmation_token=preview["confirmationToken"],
                    preview_digest=preview["previewDigest"], decision="accept")
    version = call("A publish", service.publish_reviewed_graph, draft["draftId"],
                   publication_token=approval["publicationToken"], expected_map_revision=None)
    map_revision = version["version"]["mapRevision"]
    assert version == call("A history", service.get_version, ws["workspaceId"], map_revision)
    snapshot = call("C read-only", service.graph_snapshot, ws["workspaceId"])
    exported = call("D export", service.export_version, ws["workspaceId"], map_revision)
    assert exported == version and exported["version"]["verifiedCodeRevision"] is None
    node = next(n for n in exported["version"]["graph"]["nodes"] if n["id"] == "node-demo")
    assert node["title"] == "Fixture function"
    assert exported["version"]["review"]["rejectedCandidates"] == rejected
    code_clone, arch_clone = root / "code-clone", root / "architecture-clone"
    for source, destination in ((code_repo, code_clone), (architecture_repo, arch_clone)):
        subprocess.run(["git", "clone", str(source), str(destination)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(code_clone), "remote", "set-url", "origin",
                    "https://example.invalid/projectmind-b-fixture.git"], check=True, capture_output=True)
    receiver = WorkspaceService(root / "receiver-state", code_repositories=[code_clone],
                    architecture_repo=arch_clone, architecture_branch="architecture/candidates/test-fixture")
    assert code_identity(code_clone) == code_repo_id
    receiver_ws = call("D second client", receiver.open_workspace, mode="existing_project",
                       map_id=ws["mapId"], code_repo_id=code_repo_id, code_revision=code_revision)
    imported = call("D actual Git import", receiver.import_git_version, receiver_ws["workspaceId"],
                    map_revision=map_revision, map_source_revision=version["provenance"]["mapSourceRevision"],
                    expected_map_revision=None)
    assert imported["version"] == exported["version"]
    assert read_git(code_repo, "rev-parse", "HEAD") == code_head
    assert read_git(code_repo, "status", "--porcelain", "--untracked-files=all") == code_status
    return {"fixtureOnly": True, "contractStatus": "A_REVIEW_PENDING",
            "realHttpUi": "NOT_RUN", "realCInference": "NOT_RUN", "realDHandoff": "NOT_RUN",
            "candidateProducer": "C_TEST_DOUBLE", "calls": trace,
            "candidateFixture": candidates,
            "selectionFixture": {"accepted": [candidates[0]["candidateId"]],
                                 "modified": [candidates[1]["candidateId"]], "rejected": rejected},
            "conflictExamples": conflicts, "exchange": exported, "cSnapshot": snapshot,
            "secondCloneEqual": imported["version"] == exported["version"], "codeRepoUnchanged": True}
