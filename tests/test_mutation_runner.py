# -*- coding: utf-8 -*-
"""V-02 meta-tests: the mutation runner's own classification is under test.

Oracle A13/V-02: SEMANTIC_CAUGHT may only follow a RED declared-guard suite
on a valid, applied mutation. The Codex review reproduced the inverted-flag
attack — a replacement that changes nothing and green guards classified as
SEMANTIC_CAUGHT — so these meta-tests bind the classification directly:
run_guards is mocked, while anchor discovery, mutation application and the
parse-validity gate run against the real repository clone.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import mutation_runner

# M5_position_allowed: real anchor in extensions/map_proposal/model.py.
M_FAST = mutation_runner.MUTATIONS[4]


class MutationRunnerMetaTests(unittest.TestCase):
    def run_evaluate(self, mutation, guard_green):
        mid, desc, invariant, rel_file, old, new, guards = mutation
        with tempfile.TemporaryDirectory() as parent:
            results = []
            failing = [] if guard_green else \
                [{"module": guards[0], "tail": "assertion failed"}]
            # First call is the baseline sanity run (must be green for a
            # meaningful evaluation); the second is the post-mutation run.
            calls = iter([(True, []), (guard_green, failing)])
            with mock.patch.object(mutation_runner, "run_guards",
                                   side_effect=lambda clone, modules: next(calls)):
                mutation_runner.evaluate(mid, desc, invariant, rel_file, old, new,
                                         guards, Path(parent), results)
            self.assertEqual(len(results), 1)
            return results[0]

    def test_green_guards_on_valid_mutation_is_missed_never_caught(self):
        # The review attack: a valid replacement plus green guards must be
        # SEMANTIC_MISSED — never SEMANTIC_CAUGHT.
        record = self.run_evaluate(M_FAST, guard_green=True)
        self.assertEqual(record["status"], "SEMANTIC_MISSED")

    def test_red_guards_on_valid_mutation_is_semantic_caught(self):
        record = self.run_evaluate(M_FAST, guard_green=False)
        self.assertEqual(record["status"], "SEMANTIC_CAUGHT")
        self.assertTrue(record["failing"])

    def test_environment_fault_in_post_mutation_guards_is_not_a_kill(self):
        # V-02 review #2 HIGH: a spawn failure/timeout in the POST-mutation
        # guard run used to fold into a fake nonzero exit and count as
        # SEMANTIC_CAUGHT even on a green baseline. The real run() must
        # surface EnvironmentFault and evaluate must classify
        # ENVIRONMENT_ERROR — never SEMANTIC_CAUGHT.
        real_run = mutation_runner.subprocess.run
        calls = {"n": 0}

        def flaky(cmd, **kwargs):
            calls["n"] += 1
            # 1 = git clone; 2-3 = baseline guard subprocesses (green);
            # 4+ = post-mutation guard subprocesses -> environment fault.
            if cmd[0] == "git" or calls["n"] <= 3:
                return real_run(cmd, **kwargs)
            raise OSError(2, "spawn failed")

        mid, desc, invariant, rel_file, old, new, guards = M_FAST
        with tempfile.TemporaryDirectory() as parent:
            results = []
            with mock.patch.object(mutation_runner.subprocess, "run",
                                   side_effect=flaky):
                mutation_runner.evaluate(mid, desc, invariant, rel_file, old,
                                         new, guards, Path(parent), results)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "ENVIRONMENT_ERROR")
            self.assertNotIn("SEMANTIC_CAUGHT", results[0]["status"])

    def test_environment_fault_in_baseline_is_not_a_kill(self):
        real_run = mutation_runner.subprocess.run

        def flaky(cmd, **kwargs):
            if cmd[0] == "git":
                return real_run(cmd, **kwargs)
            raise OSError(2, "spawn failed")

        mid, desc, invariant, rel_file, old, new, guards = M_FAST
        with tempfile.TemporaryDirectory() as parent:
            results = []
            with mock.patch.object(mutation_runner.subprocess, "run",
                                   side_effect=flaky):
                mutation_runner.evaluate(mid, desc, invariant, rel_file, old,
                                         new, guards, Path(parent), results)
            self.assertEqual(results[0]["status"], "ENVIRONMENT_ERROR")

    def test_drifted_anchor_is_anchor_not_found(self):
        mid, desc, invariant, rel_file, _old, _new, guards = M_FAST
        drifted = (mid, desc, invariant, rel_file,
                   "def no_such_anchor_exists():\n    pass\n", "x", guards)
        record = self.run_evaluate(drifted, guard_green=False)
        self.assertEqual(record["status"], "ANCHOR_NOT_FOUND")

    def test_invalid_python_after_mutation_is_invalid_mutation_never_caught(self):
        mid, desc, invariant, rel_file, _old, _new, guards = M_FAST
        invalid = (mid, desc, invariant, rel_file,
                   "MAX_NODES = 2000", "MAX_NODES = (2000", guards)
        record = self.run_evaluate(invalid, guard_green=False)
        self.assertEqual(record["status"], "INVALID_MUTATION")


if __name__ == "__main__":
    unittest.main()
