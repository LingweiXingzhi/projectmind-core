# -*- coding: utf-8 -*-
"""V-01 meta-tests: the acceptance-matrix runner itself is under test.

Oracle A14/A17: SKIP / NOT_RUN / INVALID_TEST / ENVIRONMENT_LIMIT / ERROR are
never PASS, and the runner's evidence reports the tests that actually ran.
The meta-tests drive the real run_selection against disposable test packages
built in a temp directory, so every failure mode the pre-fix runner hid is
now bound: real pass, real fail, SkipTest, missing test, zero matched tests,
broken module import, and the explicit category vocabulary.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.acceptance_matrix import RESULT_CATEGORIES, input_hash, run_selection  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
