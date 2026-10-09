"""Executable A/C/D example. Approval is simulated ONLY in isolated Git fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from .service import WorkspaceService
from .review import HumanReviewGateway
from .errors import WorkspaceError
from .git_publication import code_identity


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def init(repo, branch):
    repo.mkdir()
    git(repo, "init", "-b", branch)
    git(repo, "config", "user.name", "TEST ONLY operator fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "README.md").write_text("Test fixture, never a real project approval.\n")
    git(repo, "add", "."); git(repo, "commit", "-m", "fixture")


def graph(repo_id=None, revision=None):
    evidence = [{"id": "goal-demo", "kind": "user_goal", "content": "Demonstrate B version lifecycle",
                 "reason": "Synthetic test requirement"}]
    refs = ["goal-demo"]
    if repo_id:
        refs.append("code-demo")
        evidence.append({"id": "code-demo", "kind": "code", "path": "demo.py",
                         "codeRepoId": repo_id, "codeRevision": revision,
                         "lineStart": 1, "lineEnd": 2, "reason": "Actual fixture Git bytes"})
    return {"schemaVersion": "architecture_graph_v1", "nodes": [
        {"id": "node-demo", "title": "Fixture function", "responsibility": "Test demonstration",
         "interfaces": [{"id": "interface-demo", "name": "demo", "kind": "code_entry" if repo_id else "team_contract",
                         "description": "Test contract", "evidenceIds": refs}],
         "implementationStatus": "unknown" if repo_id else "planned", "evidenceIds": refs}],
         "edges": [], "evidence": evidence, "processes": [
             {"id": "process-demo", "title": "Expected process", "kind": "expected", "evidenceIds": [],
              "steps": [{"id": "step-demo", "nodeId": "node-demo", "title": "Demonstrate",
                         "inputs": [], "outputs": ["result"], "condition": "", "branches": [],
                         "nextStepIds": [], "allowedFailures": ["invalid input"], "evidenceIds": refs}]}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--test-fixture-only", action="store_true", required=True)
    parser.add_argument("--legacy-code-repo", type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    code, architecture = root / "code", root / "architecture"
    init(code, "main"); init(architecture, "architecture/candidates/test-fixture")
    git(code, "remote", "add", "origin", "https://example.invalid/projectmind-b-fixture.git")
    (code / "demo.py").write_text("def demo():\n    return 1\n")
    git(code, "add", "."); git(code, "commit", "-m", "actual code fixture")
    revision, repo_id = git(code, "rev-parse", "HEAD"), code_identity(code)
    service = WorkspaceService(root / "state", code_repositories=[code],
                architecture_repo=architecture, architecture_branch="architecture/candidates/test-fixture")
    ws = service.open_workspace(mode="existing_project", code_repo_id=repo_id, code_revision=revision)
    draft = service.create_draft(ws["workspaceId"], graph=graph(repo_id, revision), origin="ai_generated")
    edited = service.apply_draft_operations(draft["draftId"], operations=[
        {"op": "node.update", "id": "node-demo", "changes": {"responsibility": "Human correction in fixture"}}],
        expected_draft_revision=1, base_map_revision=None, proposal_id=draft["proposalId"])
    reopened = WorkspaceService(root / "state", code_repositories=[code]).get_draft(draft["draftId"])
    assert reopened == edited
    conflicts = {}
    try:
        service.apply_draft_operations(draft["draftId"], operations=[{"op": "node.remove", "id": "node-demo"}],
            expected_draft_revision=1, base_map_revision=None, proposal_id=draft["proposalId"])
    except WorkspaceError as exc:
        conflicts["REVISION_CONFLICT"] = exc.as_dict()
    gateway = HumanReviewGateway(service, "http://127.0.0.1:18832")
    boundary = {"peer": "127.0.0.1", "host": "127.0.0.1:18832", "origin": "http://127.0.0.1:18832"}
    session = gateway.create_session("TEST_ONLY_SIMULATED_HUMAN", **boundary)
    auth = {**boundary, "session_id": session["sessionId"], "csrf_token": session["csrfToken"]}

    def approve(candidate, verify):
        coverage = {"scope": "all", **{key: [o["id"] for o in candidate["graph"][key]]
                    for key in ("nodes", "edges", "evidence", "processes")}}
        params = {"expected_draft_revision": candidate["draftRevision"], "expected_map_revision": None,
                  "proposal_id": candidate["proposalId"], "code_repo_id": candidate["codeRepoId"],
                  "code_revision": candidate["codeRevision"]}
        preview = gateway.preview_review(candidate["draftId"], auth=auth, **params,
                    coverage=coverage, limits=["SIMULATED HUMAN IN TEST FIXTURE ONLY"],
                    verify_code=verify, reason="Test fixture approval, not owner approval",
                    rejected_candidates=[])
        if verify:
            try:
                gateway.confirm_review(candidate["draftId"], auth=auth, **{
                    **params, "code_repo_id": "repo-wrong"}, confirmation_token=preview["confirmationToken"],
                    preview_digest=preview["previewDigest"], decision="accept")
            except WorkspaceError as exc:
                conflicts["STALE_CONTEXT"] = exc.as_dict()
        return gateway.confirm_review(candidate["draftId"], auth=auth, **params,
                    confirmation_token=preview["confirmationToken"],
                    preview_digest=preview["previewDigest"], decision="accept")
    invalid = graph(repo_id, revision); invalid["evidence"][1]["path"] = "../private"
    try:
        service.create_draft(ws["workspaceId"], graph=invalid)
    except WorkspaceError as exc:
        conflicts["EVIDENCE_MISMATCH"] = exc.as_dict()
    approval = approve(edited, True)
    version = service.publish_reviewed_graph(draft["draftId"],
                publication_token=approval["publicationToken"], expected_map_revision=None)
    assert version == service.get_version(ws["workspaceId"], version["version"]["mapRevision"])
    assert version == service.export_version(ws["workspaceId"], version["version"]["mapRevision"])
    receiver_repo = root / "receiver-architecture"
    subprocess.run(["git", "clone", str(architecture), str(receiver_repo)], check=True, capture_output=True)
    receiver_code = root / "receiver-code"
    subprocess.run(["git", "clone", str(code), str(receiver_code)], check=True, capture_output=True)
    git(receiver_code, "remote", "set-url", "origin", "https://example.invalid/projectmind-b-fixture.git")
    assert code_identity(receiver_code) == repo_id
    receiver = WorkspaceService(root / "receiver-state", code_repositories=[receiver_code],
                architecture_repo=receiver_repo, architecture_branch="architecture/candidates/test-fixture")
    receiver_ws = receiver.open_workspace(mode="existing_project", map_id=ws["mapId"],
                                          code_repo_id=repo_id, code_revision=revision)
    imported = receiver.import_git_version(receiver_ws["workspaceId"],
                map_revision=version["version"]["mapRevision"],
                map_source_revision=version["provenance"]["mapSourceRevision"], expected_map_revision=None)
    assert imported["version"] == version["version"]
    planning = service.open_workspace(mode="planning")
    design = service.create_draft(planning["workspaceId"], graph=graph(), origin="ai_generated")
    approval = approve(design, False)
    planned_version = service.publish_reviewed_graph(design["draftId"],
                publication_token=approval["publicationToken"], expected_map_revision=None)
    legacy_result = None
    if args.legacy_code_repo:
        legacy_repo = args.legacy_code_repo.resolve()
        legacy_service = WorkspaceService(root / "legacy-state", code_repositories=[legacy_repo])
        legacy_ws = legacy_service.open_workspace(mode="existing_project",
            code_repo_id=code_identity(legacy_repo), code_revision=git(legacy_repo, "rev-parse", "HEAD"))
        legacy_draft = legacy_service.create_draft(legacy_ws["workspaceId"],
            legacy=json.loads((legacy_repo / "data/project-map.json").read_text()))
        legacy_result = {"status": legacy_draft["status"], "nodeCount": len(legacy_draft["graph"]["nodes"]),
                         "codeRevision": legacy_ws["codeRevision"], "published": False}
    result = {"fixtureOnly": True, "realModelApi": "NOT_RUN", "normalExchange": version,
              "planningExchange": planned_version, "conflictExamples": conflicts,
              "cSnapshot": service.graph_snapshot(ws["workspaceId"]),
              "secondCloneEqual": imported["version"] == version["version"],
              "legacyImport": legacy_result}
    # Import lazily: the consumer example reuses this module's fixture graph.
    from .consumer_contract import exercise_consumers
    consumers = exercise_consumers(service, output=root / "consumer-contract",
                 code_repo=code, architecture_repo=architecture, code_repo_id=repo_id,
                 code_revision=revision, test_fixture_only=True)
    (root / "CONSUMER_CONTRACT.json").write_text(
        json.dumps(consumers, ensure_ascii=False, indent=2) + "\n")
    assert set(conflicts) == {"REVISION_CONFLICT", "STALE_CONTEXT", "EVIDENCE_MISMATCH"}
    (root / "FUNCTION_SMOKE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": "PASS", "secondCloneEqual": True, "conflicts": list(conflicts),
                      "legacyImport": legacy_result, "consumerCalls": len(consumers["calls"]),
                      "consumerContract": "A_REVIEW_PENDING"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
