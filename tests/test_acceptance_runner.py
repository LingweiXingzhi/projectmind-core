# -*- coding: utf-8 -*-
"""V-01 meta-tests: the acceptance-matrix runner itself is under test.

Oracle A14/A17: SKIP / NOT_RUN / INVALID_TEST / ENVIRONMENT_LIMIT / ERROR are
never PASS, and the runner's evidence reports the tests that actually ran.
The meta-tests drive the real run_selection against disposable test packages
built in a temp directory, so every failure mode the pre-fix runner hid is
bound: real pass, real fail, SkipTest, missing test, zero matched tests,
broken module import, category vocabulary — and, after the Codex review, the
S30 subprocess path itself (a skipped A30 test exits 0 but is SKIP,
enumeration failure is INVALID_TEST, evidence carries parsed outcomes).
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import acceptance_matrix
from tests.acceptance_matrix import RESULT_CATEGORIES, input_hash, run_selection


PASS_MOD = '''
import unittest

class FakePass(unittest.TestCase):
    def test_ok_one(self):
        self.assertTrue(True)

    def test_ok_two(self):
        self.assertEqual(1 + 1, 2)
'''

FAIL_MOD = '''
import unittest

class FakeFail(unittest.TestCase):
    def test_bad_assertion(self):
        self.assertEqual(1, 2)
'''

SKIP_MOD = '''
import unittest

class FakeSkip(unittest.TestCase):
    def test_ok_before_skip(self):
        self.assertTrue(True)

    def test_skipped_item(self):
        self.skipTest("environment: no such device")
'''

RAISE_MOD = '''
import unittest

class FakeError(unittest.TestCase):
    def test_raises(self):
        raise RuntimeError("boom")
'''

BROKEN_IMPORT_MOD = 'raise RuntimeError("import-time failure")\n'

EMPTY_MOD = '''
import unittest

class FakeEmpty(unittest.TestCase):
    pass
'''


class RunnerMetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        pkg = Path(tmp.name) / "fake_matrix_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        for name, source in (
            ("mod_pass.py", PASS_MOD),
            ("mod_fail.py", FAIL_MOD),
            ("mod_skip.py", SKIP_MOD),
            ("mod_raise.py", RAISE_MOD),
            ("mod_broken_import.py", BROKEN_IMPORT_MOD),
            ("mod_empty.py", EMPTY_MOD),
        ):
            (pkg / name).write_text(source, encoding="utf-8")
        sys.path.insert(0, tmp.name)
        cls.addClassCleanup(sys.path.remove, tmp.name)

    def test_real_pass_is_pass(self):
        res = run_selection([("mod_pass", "test_")], import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "PASS")
        self.assertEqual(
            (res["passed"], res["skipped"], res["failed"], res["total"]), (2, 0, 0, 2))
        self.assertIn("2 passed", res["evidence"])

    def test_real_fail_is_fail_never_pass(self):
        res = run_selection([("mod_fail", "test_")], import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "FAIL")
        self.assertIn("test_bad_assertion", res["evidence"])

    def test_skiptest_is_skip_never_pass(self):
        # V-01 core regression: the pre-fix runner counted skipped tests as
        # passes because result.skipped was never examined.
        res = run_selection([("mod_skip", "test_")], import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "SKIP")
        self.assertNotEqual(res["result"], "PASS")
        self.assertEqual(res["skipped"], 1)
        self.assertIn("skip is never PASS", res["evidence"])

    def test_error_is_fail_never_pass(self):
        res = run_selection([("mod_raise", "test_")], import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "FAIL")
        self.assertIn("test_raises", res["evidence"])

    def test_zero_matched_tests_is_not_run_never_pass(self):
        res = run_selection([("mod_pass", "test_nothing_matches_this_")],
                            import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "NOT_RUN")
        self.assertIn("NO TESTS MAPPED", res["evidence"])

    def test_missing_module_is_invalid_test_never_pass(self):
        res = run_selection([("mod_does_not_exist", "test_")],
                            import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "INVALID_TEST")

    def test_broken_module_import_is_invalid_test_never_pass(self):
        # compile failure / import-time failure of a mapped module can never
        # be counted as a passing row (V-01: compile failure != PASS).
        res = run_selection([("mod_broken_import", "test_")],
                            import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "INVALID_TEST")

    def test_class_without_matching_tests_is_not_run(self):
        res = run_selection([("mod_empty", "test_")], import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "NOT_RUN")

    def test_zero_match_selection_is_not_run_even_with_passing_sibling(self):
        # V-01 review MEDIUM: a passing selection must not mask a zero-match
        # sibling; the row is NOT_RUN until every selection binds tests.
        res = run_selection([("mod_pass", "test_"), ("mod_pass", "test_no_match_")],
                            import_root="fake_matrix_pkg")
        self.assertEqual(res["result"], "NOT_RUN")
        self.assertIn("test_no_match_", res["evidence"])

    def test_result_categories_are_explicit_and_only_pass_passes(self):
        # A14/A17 vocabulary: seven explicit categories; the non-pass
        # categories can never be confused with PASS by consumers.
        self.assertEqual(len(RESULT_CATEGORIES), 7)
        for category in ("SKIP", "NOT_RUN", "INVALID_TEST", "ENVIRONMENT_LIMIT", "ERROR"):
            self.assertNotEqual(category, "PASS")

    def test_input_hash_covers_all_selections_not_only_the_first(self):
        # V-01: the pre-fix hash covered only the first selection's function
        # sources; the repaired hash must change with any mapped selection.
        whole = input_hash([("test_w3_relations", "test_s03_"),
                            ("test_w4_ca_trust", "test_s19_")])
        first_only = input_hash([("test_w3_relations", "test_s03_")])
        self.assertNotEqual(whole, first_only)

    def test_input_hash_changes_with_a_zero_match_selection(self):
        # V-01 review MEDIUM: the selection identity is part of the input, so
        # adding a zero-match selection must change the hash.
        base = input_hash([("test_w3_relations", "test_s03_")])
        extended = input_hash([("test_w3_relations", "test_s03_"),
                               ("test_w3_relations", "test_no_match_xyz_")])
        self.assertNotEqual(base, extended)


A30_OK_MOD = (
    "import unittest\n"
    "\n"
    "class FakeA30Tests(unittest.TestCase):\n"
    "    def test_a30_runtime_containment(self):\n"
    "        self.assertTrue(True)\n"
)

A30_SKIP_MOD = (
    "import unittest\n"
    "\n"
    "class FakeA30Tests(unittest.TestCase):\n"
    "    def test_a30_runtime_containment(self):\n"
    "        self.assertTrue(True)\n"
    "\n"
    "    def test_a30_other_route_survives(self):\n"
    "        self.skipTest('environment: no such device')\n"
)

A30_FAIL_MOD = (
    "import unittest\n"
    "\n"
    "class FakeA30Tests(unittest.TestCase):\n"
    "    def test_a30_runtime_containment(self):\n"
    "        self.assertEqual(1, 2)\n"
)

A30_ABSENT_MOD = (
    "import unittest\n"
    "\n"
    "class UnrelatedTests(unittest.TestCase):\n"
    "    def test_unrelated(self):\n"
    "        self.assertTrue(True)\n"
)

A30_BROKEN_MOD = "raise RuntimeError('broken test module')\n"


class S30PathMetaTests(unittest.TestCase):
    """The S30 helper must bind the actual test_a30_* outcomes, not the
    subprocess exit code: a skipped A30 test exits 0 and is never PASS."""

    def build_fake_worktree(self, source):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "fake-a30"
        (root / "tests").mkdir(parents=True)
        (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "tests" / "test_extensions.py").write_text(source, encoding="utf-8")
        patcher = mock.patch.object(acceptance_matrix, "A30_WORKTREE", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        # The in-runtime candidate must deterministically find NO a30 tests
        # so the helper falls through to the fake worktree: on the BCD base
        # this checkout legitimately carries the real A30 tests in-runtime.
        stub_root = Path(tmp.name) / "stub-runtime"
        (stub_root / "tests").mkdir(parents=True)
        (stub_root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (stub_root / "tests" / "test_extensions.py").write_text(
            "import unittest\n\nclass UnrelatedTests(unittest.TestCase):\n"
            "    def test_unrelated(self):\n        self.assertTrue(True)\n",
            encoding="utf-8")
        runtime_patcher = mock.patch.object(acceptance_matrix, "ROOT", stub_root)
        runtime_patcher.start()
        self.addCleanup(runtime_patcher.stop)
        return root

    def test_s30_all_green_a30_tests_are_pass(self):
        self.build_fake_worktree(A30_OK_MOD)
        outcome = acceptance_matrix.run_a30_fix_tests()
        self.assertEqual(outcome["result"], "PASS")
        self.assertIn("FakeA30Tests.test_a30_runtime_containment=ok",
                      outcome["evidence"])

    def test_s30_skipped_a30_test_is_skip_never_pass(self):
        # V-01 review HIGH: the skipped A30 test exits 0, so the pre-fix
        # return-code-only check classified the run PASS. It must be SKIP.
        self.build_fake_worktree(A30_SKIP_MOD)
        outcome = acceptance_matrix.run_a30_fix_tests()
        self.assertEqual(outcome["result"], "SKIP")
        self.assertIn("test_a30_other_route_survives=skipped", outcome["evidence"])

    def test_s30_failing_a30_test_is_fail(self):
        self.build_fake_worktree(A30_FAIL_MOD)
        outcome = acceptance_matrix.run_a30_fix_tests()
        self.assertEqual(outcome["result"], "FAIL")
        self.assertIn("test_a30_runtime_containment=FAIL", outcome["evidence"])

    def test_s30_no_a30_tests_anywhere_is_not_run(self):
        self.build_fake_worktree(A30_ABSENT_MOD)
        outcome = acceptance_matrix.run_a30_fix_tests()
        self.assertEqual(outcome["result"], "NOT_RUN")

    def test_s30_broken_enumeration_is_invalid_test(self):
        self.build_fake_worktree(A30_BROKEN_MOD)
        outcome = acceptance_matrix.run_a30_fix_tests()
        self.assertEqual(outcome["result"], "INVALID_TEST")


if __name__ == "__main__":
    unittest.main()
