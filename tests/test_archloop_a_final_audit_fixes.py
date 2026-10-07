"""Regression tests for the final audit findings (BATCH-FINAL, 2026-10-08).

One class per finding, reproducing the auditor's counterexample:
- FINAL-C-01: a partial/reversed/unidentified trace is never ALIGNED.
- FINAL-D-01: a cross-workspace task update is refused *before* any write.
- FINAL-D-02: an observation that names another repository/revision is refused,
  never rewritten into the published identity.
- FINAL-D-03: state changes must carry the caller's expected revisions.
- FINAL-D-04: a recorded deviation id cannot lend its evidence to other content.
- FINAL-BC-01/02: the frozen C→B adapter refuses identity-mismatched
  candidates and non-bootstrap contexts.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import app as app_module
from archloop.backend_d import BackendD, _normalize_evidence
from archloop.contract import ContractError


class PartialTraceIsNeverAlignedTests(unittest.TestCase):
    """FINAL-C-01: only a complete, ordered, identified trace can be ALIGNED."""

    GRAPH = {"codeRepoId": "repo-abc", "codeRevision": "a" * 40,
             "nodes": [{"nodeId": "n", "expectedProcesses": ["A", "B", "C"]}]}

    def _detect(self, traces):
        from extensions.map_proposal.candidates import detect_process_deviations
        return detect_process_deviations(json.loads(json.dumps(self.GRAPH)), traces)

    def _trace(self, steps, repo="repo-abc", revision="a" * 40):
        return {"called_steps": steps, "codeRepoId": repo, "codeRevision": revision}

    def test_only_full_ordered_identified_trace_is_aligned(self) -> None:
        self.assertEqual(self._detect([self._trace(["A", "B", "C"])])["verdict"], "ALIGNED")
        self.assertEqual(self._detect([self._trace(["A", "B", "C", "D"])])["verdict"], "ALIGNED")

    def test_partial_reversed_and_unidentified_are_not_aligned(self) -> None:
        cases = {
            "only the last step ran": self._trace(["C"]),
            "only the first step ran": self._trace(["A"]),
            "reversed order": self._trace(["C", "B", "A"]),
            "middle skipped": self._trace(["A", "C"]),
            "no identity claimed": {"called_steps": ["A", "B", "C"]},
            "wrong repository": self._trace(["A", "B", "C"], repo="other-repo"),
            "wrong revision": self._trace(["A", "B", "C"], revision="b" * 40),
            "unrelated steps": self._trace(["X"]),
        }
        for name, trace in cases.items():
            with self.subTest(name):
                result = self._detect([trace])
                self.assertNotEqual(result["verdict"], "ALIGNED", name)
        self.assertEqual(self._detect([self._trace(["C"])])["verdict"], "DEVIATION_DETECTED")
        self.assertEqual(self._detect([self._trace(["C", "B", "A"])])["deviations"][0]["type"],
                         "out_of_order")


class CrossWorkspaceUpdateIsRefusedBeforeWriteTests(unittest.TestCase):
    """FINAL-D-01: ownership is validated before any state change."""

    class RecordingBackend:
        available = True

        def __init__(self, workspace_id):
            self.workspace_id = workspace_id
            self.writes = []

        def get_task(self, task_id):
            return {"id": task_id, "workspaceId": self.workspace_id, "revision": 3,
                    "mapRevision": "sha256:map", "status": "queued"}

        def update(self, task_id, request, server_context):
            self.writes.append((task_id, dict(request)))
            return self.get_task(task_id)

        def descriptor(self):
            return {"kind": "test_recording_handoff", "call": lambda action, payload: {}}

        def list_tasks(self, workspace_id):
            return {"tasks": []}

    def test_foreign_task_is_not_written(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        service = app_module.WorkbenchService(tmp / "data", app_module.AdapterRegistry())
        backend = self.RecordingBackend("pending")
        service.bind_backend_d(backend)
        created = service.create_workspace({"context": "planning", "title": "持有者", "goals": "g"})
        owner = created["workspace"]["workspaceId"]
        other = service.create_workspace({"context": "planning", "title": "旁观者", "goals": "g"})
        other_id = other["workspace"]["workspaceId"]
        backend.workspace_id = owner
        with self.assertRaises(ContractError) as refused:
            service.update_fix_task(other_id, "fix-x", {"status": "received", "note": "n"})
        self.assertEqual(refused.exception.code, "STALE_CONTEXT")
        self.assertEqual(backend.writes, [], "被拒的跨工作区请求不允许先写入")
        # the owner's own workspace still works
        service.update_fix_task(owner, "fix-x", {"status": "received", "note": "n"})
        self.assertEqual(len(backend.writes), 1)


class ObservationIdentityTests(unittest.TestCase):
    """FINAL-D-02: declared observation identity is checked, never rewritten."""

    VERSION = {"codeRepoId": "repo-" + "a" * 64, "codeRevision": "c" * 40}

    def test_mismatched_observation_identity_is_refused(self) -> None:
        with self.assertRaises(ContractError) as refused:
            _normalize_evidence([{"kind": "trace_observation", "detail": "观察",
                                  "codeRepoId": "repo-WRONG", "codeRevision": "b" * 40}],
                                version=self.VERSION)
        self.assertEqual(refused.exception.code, "EVIDENCE_MISMATCH")

    def test_matching_or_absent_identity_is_kept_and_filled(self) -> None:
        kept = _normalize_evidence([{"kind": "trace_observation", "detail": "观察",
                                     "codeRepoId": self.VERSION["codeRepoId"],
                                     "codeRevision": self.VERSION["codeRevision"]}],
                                   version=self.VERSION)
        self.assertEqual(kept[0]["codeRepoId"], self.VERSION["codeRepoId"])
        filled = _normalize_evidence([{"kind": "test_observation", "detail": "观察"}],
                                     version=self.VERSION)
        self.assertEqual(filled[0]["codeRevision"], self.VERSION["codeRevision"])


class ExpectedRevisionRequirementTests(unittest.TestCase):
    """FINAL-D-03: the caller states the revision it saw; D validates it."""

    def _backend(self):
        tmp = Path(tempfile.mkdtemp())
        from archloop.backend_d import BackendD
        from extensions.continuity.fix_tasks import FixTaskService
        from extensions.continuity.store import Store
        service = app_module.WorkbenchService(tmp / "data", app_module.AdapterRegistry())
        fix_service = FixTaskService(Store(tmp / "continuity" / "records.sqlite3"),
                                     architecture_repo=tmp / "arch",
                                     code_repositories=[REPO_ROOT])
        return BackendD(service, fix_service, architecture_repo=tmp / "arch",
                        code_repositories={str(REPO_ROOT): str(REPO_ROOT)})

    def test_missing_expected_revision_is_refused(self) -> None:
        backend = self._backend()
        backend.get_task = lambda task_id: {"id": task_id, "workspaceId": "ws", "revision": 2,
                                            "mapRevision": "sha256:map", "status": "queued"}
        with self.assertRaises(ContractError) as refused:
            backend.update("fix-1", {"status": "received", "note": "n"}, {"actor": "op"})
        self.assertEqual(refused.exception.code, "VALIDATION_FAILED")

    def test_stale_expected_revision_is_a_conflict(self) -> None:
        backend = self._backend()
        backend.get_task = lambda task_id: {"id": task_id, "workspaceId": "ws", "revision": 4,
                                            "mapRevision": "sha256:map", "status": "queued"}
        with self.assertRaises(ContractError) as refused:
            backend.update("fix-1", {"status": "received", "note": "n",
                                     "expectedRevision": 1, "expectedMapRevision": "sha256:map"},
                           {"actor": "op"})
        self.assertEqual(refused.exception.code, "REVISION_CONFLICT")


class RecordedDeviationBindingTests(unittest.TestCase):
    """FINAL-D-04: a recorded id is reused only for the same observation."""

    def _backend(self, record):
        tmp = Path(tempfile.mkdtemp())
        from archloop.backend_d import BackendD
        from extensions.continuity.fix_tasks import FixTaskService
        from extensions.continuity.store import Store
        service = app_module.WorkbenchService(tmp / "data", app_module.AdapterRegistry())
        service.store.load_workspace = lambda workspace_id: record
        service.store.save_workspace_record = lambda value: None
        fix_service = FixTaskService(Store(tmp / "continuity" / "records.sqlite3"),
                                     architecture_repo=tmp / "arch",
                                     code_repositories=[REPO_ROOT])
        return BackendD(service, fix_service, architecture_repo=tmp / "arch",
                        code_repositories={str(REPO_ROOT): str(REPO_ROOT)})

    def test_same_id_other_content_is_refused(self) -> None:
        record = {"workspaceId": "ws", "identity": {},
                  "deviations": [{"id": "dev-1", "observation": "步骤 A 被绕过", "status": "open"}]}
        backend = self._backend(record)
        with self.assertRaises(ContractError) as refused:
            backend._deviation_id(record, {"deviationId": "dev-1"}, "完全不同的偏差描述")
        self.assertEqual(refused.exception.code, "EVIDENCE_MISMATCH")

    def test_unknown_id_is_not_adopted(self) -> None:
        record = {"workspaceId": "ws", "identity": {}, "deviations": []}
        backend = self._backend(record)
        new_id = backend._deviation_id(record, {"deviationId": "attacker-chosen"}, "新的偏差")
        self.assertNotEqual(new_id, "attacker-chosen")
        self.assertTrue(new_id.startswith("dev_"))

    def test_matching_content_reuses_the_recorded_id(self) -> None:
        record = {"workspaceId": "ws", "identity": {},
                  "deviations": [{"id": "dev-1", "observation": "步骤 A 被绕过", "status": "open"}]}
        backend = self._backend(record)
        self.assertEqual(backend._deviation_id(record, {"deviationId": "dev-1"}, " 步骤 A 被绕过 "), "dev-1")


class FrozenExchangeBoundaryTests(unittest.TestCase):
    """FINAL-BC-01/02: identity mismatch and non-bootstrap contexts are refused."""

    BASIS = {"workspaceId": "ws", "mapId": "map", "mode": "planning", "codeRepoId": None,
             "codeRevision": None, "baseMapRevision": None, "draftId": None, "draftRevision": None}

    def _candidate(self):
        from extensions.map_proposal.candidates import generate_bootstrap_proposal
        return generate_bootstrap_proposal({"mode": "planning", "workspaceId": "ws",
                                            "goals": [{"id": "r", "title": "T", "description": "D"}]})

    def test_identity_mismatch_is_refused(self) -> None:
        from archloop.backend_c import to_b_proposal
        candidate = self._candidate()
        candidate["codeRepoId"] = "repo-other"
        with self.assertRaises(ContractError) as refused:
            to_b_proposal(candidate, context=self.BASIS)
        self.assertEqual(refused.exception.code, "STALE_CONTEXT")

    def test_patch_context_is_refused(self) -> None:
        from archloop.backend_c import to_b_proposal
        context = dict(self.BASIS, draftId="draft-1", mode="existing_project")
        with self.assertRaises(ContractError) as refused:
            to_b_proposal(self._candidate(), context=context)
        self.assertEqual(refused.exception.code, "VALIDATION_FAILED")

    def test_matching_bootstrap_is_accepted_by_b(self) -> None:
        from archloop.backend_c import to_b_proposal
        from extensions.architecture_workspace.proposals import validate_proposal
        candidate = self._candidate()
        accepted = validate_proposal(to_b_proposal(candidate, context=self.BASIS), self.BASIS)
        self.assertEqual(accepted["proposalId"], candidate["proposalId"])


if __name__ == "__main__":
    unittest.main()