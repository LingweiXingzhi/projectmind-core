"""B -> pinned D component rehearsal on newly created test-only Git repositories.

Install the verified D runtime in an isolated assembly before running. This
does not register A HTTP routes, create real-human approval, or deploy a site.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

from .errors import WorkspaceError, require
from .surface_smoke import run as run_surfaces, _assert_public, FIXTURE_ORIGIN
from .smoke import git
from .surfaces import version_reference

D_SOURCE_REF = "c8b942a8d724b1bd0509f61b2db6ec642a117181"
D_BLOBS = {
    "extensions/handoff/architecture.py": "cb967fde8d43e505faea790208aab78d98230e92",
    "extensions/continuity/inspection.py": "0b419f3e7c9e71c3ac04dfe3ecda83f49606a255",
    "extensions/continuity/model.py": "d6365b0a2d7bb3cbf9b97a72dc0d555116639031",
}
ARCHITECTURE_ORIGIN = "https://example.invalid/projectmind-b-architecture-fixture.git"


def run(output, *, test_fixture_only=False):
    require(test_fixture_only is True, detail="仅允许显式新建的合成夹具")
    try:
        from extensions.handoff import architecture as d
        from extensions.continuity import inspection as inspection_module, model as model_module
    except ImportError as exc:
        raise WorkspaceError("INVALID_INPUT", "D 运行组件未安装；请使用校验过的独立共装目录") from exc
    consumer_files = {
        "extensions/handoff/architecture.py": Path(d.__file__),
        "extensions/continuity/inspection.py": Path(inspection_module.__file__),
        "extensions/continuity/model.py": Path(model_module.__file__),
    }
    for rel, path in consumer_files.items():
        data = path.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(actual == D_BLOBS[rel], "VERSION_CONFLICT",
                "D 消费组件不是本轮固定版本；先重新核验来源")
    # The surface smoke allocates a fresh root and approves only synthetic data.
    surface = run_surfaces(output, test_fixture_only=True)
    root = Path(output).resolve()
    code, architecture = root / "code", root / "architecture"
    receiver_code, receiver_arch = root / "receiver-code", root / "receiver-architecture"
    for repo in (architecture, receiver_arch):
        operation = "set-url" if "origin" in git(repo, "remote").splitlines() else "add"
        git(repo, "remote", operation, "origin", ARCHITECTURE_ORIGIN)
    before_code = {str(repo.name): {"head": git(repo, "rev-parse", "HEAD"),
                  "status": git(repo, "status", "--porcelain", "--untracked-files=all")}
                  for repo in (code, receiver_code)}
    envelope = surface["exchange"]
    original = copy.deepcopy(envelope)
    packet = d.build_version_handoff(envelope, workspace_id="workspace-b-d-fixture",
        sources={"code": FIXTURE_ORIGIN, "architecture": ARCHITECTURE_ORIGIN})
    checked = d.inspect_version_handoff(packet, architecture_repo=receiver_arch, code_repo=receiver_code)
    expected = version_reference(envelope)
    assert {key: checked[key] for key in expected} == expected
    assert checked["versionEnvelope"] == envelope == original
    assert checked["formalMapWritten"] is False
    assert checked["status"] == "same_version_git_checked"

    # Planning was published after the first clone. Fetch committed objects
    # locally, without changing the receiver branch/worktree or origin identity.
    receiver_head = git(receiver_arch, "rev-parse", "HEAD")
    git(receiver_arch, "fetch", str(architecture), "architecture/candidates/test-fixture")
    assert git(receiver_arch, "rev-parse", "HEAD") == receiver_head
    plan_envelope = surface["planningExchange"]
    plan_packet = d.build_version_handoff(plan_envelope, workspace_id="workspace-b-d-planning",
        sources={"code": None, "architecture": ARCHITECTURE_ORIGIN})
    plan_checked = d.inspect_version_handoff(plan_packet, architecture_repo=receiver_arch, code_repo=None)
    assert all(plan_checked[key] is None for key in ("codeRepoId", "codeRevision", "verifiedCodeRevision"))
    assert plan_checked["graphStatus"] == "confirmed_design"
    assert plan_checked["versionEnvelope"] == plan_envelope

    denials = {}
    wrong_code = root / "different-source-code"
    subprocess.run(["git", "clone", str(code), str(wrong_code)], check=True, capture_output=True)
    git(wrong_code, "remote", "set-url", "origin", "https://example.invalid/other-project.git")
    try:
        d.inspect_version_handoff(packet, architecture_repo=receiver_arch, code_repo=wrong_code)
    except d.ArchitectureError as exc:
        assert exc.code == "STALE_CONTEXT"
        denials["differentSource"] = exc.code
    else:
        raise AssertionError("D accepted another repository")

    unsaved = receiver_arch / "unsaved-fixture.txt"
    unsaved.write_text("TEST fixture data must be preserved.\n")
    try:
        d.inspect_version_handoff(packet, architecture_repo=receiver_arch, code_repo=receiver_code)
    except d.ArchitectureError as exc:
        assert exc.code == "DIRTY_WORKSPACE"
        assert unsaved.read_text() == "TEST fixture data must be preserved.\n"
        denials["dirtyArchitecture"] = exc.code
    else:
        raise AssertionError("D accepted a dirty worktree")
    finally:
        unsaved.unlink()

    changed = copy.deepcopy(packet)
    changed["versionEnvelope"]["provenance"]["mapSourceRevision"] = "0" * 40
    changed["transportDigest"] = d.digest({key: value for key, value in changed.items()
                                         if key != "transportDigest"})
    try:
        d.inspect_version_handoff(changed, architecture_repo=receiver_arch, code_repo=receiver_code)
    except d.ArchitectureError as exc:
        denials["unavailableFixedSource"] = exc.code
    else:
        raise AssertionError("D accepted an unavailable Git source")

    after_code = {str(repo.name): {"head": git(repo, "rev-parse", "HEAD"),
                 "status": git(repo, "status", "--porcelain", "--untracked-files=all")}
                 for repo in (code, receiver_code)}
    assert before_code == after_code
    assert git(receiver_arch, "status", "--porcelain", "--untracked-files=all") == ""
    result = {"fixtureOnly": True, "result": "PASS_COMPONENT_REHEARSAL",
              "dSourceRef": D_SOURCE_REF, "verifiedConsumerBlobs": D_BLOBS,
              "realAUi": "NOT_RUN_BY_THIS_SMOKE", "realCInference": "NOT_RUN",
              "realDHandoff": "PASS_COMPONENT_ONLY", "realDFixTask": "NOT_RUN_BY_THIS_SMOKE",
              "publicDeployment": "NOT_RUN", "humanActor": "TEST_ONLY_SIMULATED_HUMAN",
              "checks": {"actualBPublishedEnvelope": True, "actualDConsumerFunctions": True,
                  "sixFieldVersionRefEqual": True, "originalEnvelopeUnchanged": True,
                  "secondCloneGitBytesEqual": True, "planningNullBindings": True,
                  "planningSourceFetchedLocally": True, "foreignRepoRejected": True,
                  "dirtyWorktreePreserved": True, "missingSourceRejected": True,
                  "codeWorktreesUnchanged": True, "noFormalMapWriteByD": True},
              "handoff": packet, "receiverCheck": checked, "planningHandoff": plan_packet,
              "planningReceiverCheck": plan_checked, "denials": denials,
              "limits": ["Component fixture evidence is not product T01–T28 acceptance.",
                         "A routes, login, real AI and real owner approval are not proved here."]}
    _assert_public(result, [])
    (root / "B_D_HANDOFF_SMOKE.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    print(json.dumps({"result": result["result"], "fixtureOnly": True,
                      "checks": len(result["checks"]), "publicDeployment": "NOT_RUN"}))


if __name__ == "__main__":
    main()
