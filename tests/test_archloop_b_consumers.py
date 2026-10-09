"""Consumer examples exercise real B calls; other owners remain test doubles."""
import json
from pathlib import Path
import tempfile
import unittest

from extensions.architecture_workspace.consumer_contract import exercise_consumers, PRIVATE_FIELDS
from extensions.architecture_workspace import WorkspaceService, WorkspaceError
from extensions.architecture_workspace.git_publication import code_identity
from extensions.architecture_workspace.smoke import init, git


class ConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="archloop-b-consumers-")
        self.root = Path(self.temp.name).resolve()
        self.code, self.arch = self.root / "code", self.root / "architecture"
        init(self.code, "main"); init(self.arch, "architecture/candidates/test-fixture")
        git(self.code, "remote", "add", "origin", "https://example.invalid/projectmind-b-fixture.git")
        (self.code / "demo.py").write_text("def demo():\n    return 1\n")
        git(self.code, "add", "."); git(self.code, "commit", "-m", "fixture code")
        self.service = WorkspaceService(self.root / "state", code_repositories=[self.code],
                architecture_repo=self.arch, architecture_branch="architecture/candidates/test-fixture")
        self.args = {"output": self.root / "consumer-example", "code_repo": self.code,
                     "architecture_repo": self.arch, "code_repo_id": code_identity(self.code),
                     "code_revision": git(self.code, "rev-parse", "HEAD"), "test_fixture_only": True}

    def tearDown(self):
        self.temp.cleanup()

    def test_consumer_selection_review_and_clone_use_real_service(self):
        result = exercise_consumers(self.service, **self.args)
        self.assertTrue(result["secondCloneEqual"] and result["codeRepoUnchanged"])
        self.assertEqual(result["contractStatus"], "A_REVIEW_PENDING")
        self.assertEqual(result["realCInference"], "NOT_RUN")
        self.assertEqual(set(result["conflictExamples"]), {"REVISION_CONFLICT", "STALE_CONTEXT",
                                                          "EVIDENCE_MISMATCH", "HUMAN_REVIEW_REQUIRED"})
        packet = result["exchange"]["version"]
        self.assertIsNone(packet["verifiedCodeRevision"])
        self.assertEqual(len(packet["graph"]["nodes"]), 2)
        self.assertEqual(packet["graph"]["processes"][0]["steps"][0]["title"], "Human corrected fixture step")
        self.assertEqual(packet["review"]["rejectedCandidates"], result["selectionFixture"]["rejected"])
        self.assertEqual(result["cSnapshot"]["versionEnvelope"], result["exchange"])
        self.assertEqual([o["source"] for o in packet["review"]["appliedOperations"]],
                         ["rule_based", "rule_based", "human"])

    def test_trace_never_exports_private_values_or_local_paths(self):
        result = exercise_consumers(self.service, **self.args)
        found = []
        def check(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in PRIVATE_FIELDS:
                        self.assertIn(item, (None, "<PRIVATE_RUNTIME_VALUE>"))
                        found.append(key)
                    check(item)
            elif isinstance(value, list):
                for item in value: check(item)
        check(result)
        self.assertTrue({"confirmation_token", "publicationToken", "csrfToken"} <= set(found))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(result["realHttpUi"], "NOT_RUN")
        self.assertEqual(result["realDHandoff"], "NOT_RUN")

    def test_guard_refuses_real_source_and_unmarked_run_before_writing(self):
        head = git(self.arch, "rev-parse", "HEAD")
        with self.assertRaises(WorkspaceError):
            exercise_consumers(self.service, **{**self.args, "test_fixture_only": False})
        git(self.code, "remote", "set-url", "origin", "https://github.com/example/real-project.git")
        with self.assertRaises(WorkspaceError):
            exercise_consumers(self.service, **self.args)
        self.assertFalse(self.args["output"].exists())
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), head)

    def test_existing_output_is_never_overwritten(self):
        self.args["output"].mkdir()
        marker = self.args["output"] / "another-run.txt"
        marker.write_text("Keep this run")
        head = git(self.arch, "rev-parse", "HEAD")
        with self.assertRaises(FileExistsError):
            exercise_consumers(self.service, **self.args)
        self.assertEqual(marker.read_text(), "Keep this run")
        self.assertEqual(git(self.arch, "rev-parse", "HEAD"), head)


if __name__ == "__main__":
    unittest.main()
