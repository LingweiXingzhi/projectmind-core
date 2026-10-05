# -*- coding: utf-8 -*-
"""B1 slice 6: registry LRU capacity, eviction, and in-flight references.

Accepted contract R2-Q2: at most 4 contexts; eviction yields a stable
410 CONTEXT_EVICTED for new requests; requests already holding their
context object finish unaffected; revision must match the bound SHA.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from repo_index.explorer import ExplorerError, ExplorerRegistry


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


class RegistryLruTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "lru-repo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "main")
        run_git(self.repo, "config", "user.name", "T")
        run_git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "x.py").write_text("x = 1\n", encoding="utf-8")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "c1")
        self.shas = [run_git(self.repo, "rev-parse", "HEAD")]
        for i in range(2, 7):
            (self.repo / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
            run_git(self.repo, "add", ".")
            run_git(self.repo, "commit", "-qm", f"c{i}")
            self.shas.append(run_git(self.repo, "rev-parse", "HEAD"))
        self.registry = ExplorerRegistry()

    def tearDown(self):
        self._tmp.cleanup()

    def open_at(self, sha: str) -> dict:
        return self.registry.open(str(self.repo), sha)

    def test_open_beyond_capacity_evicts_oldest(self):
        opened = [self.open_at(sha) for sha in self.shas]  # 6 opens, cap 4
        oldest = opened[0]
        newest = opened[-1]
        with self.assertRaises(ExplorerError) as evicted:
            self.registry.get(oldest["projectId"], oldest["revision"])
        self.assertEqual(evicted.exception.status.value, 410)
        self.assertEqual(evicted.exception.code, "CONTEXT_EVICTED")
        kept = self.registry.get(newest["projectId"], newest["revision"])
        self.assertEqual(kept.revision, newest["revision"])

    def test_second_newest_stays_within_capacity(self):
        opened = [self.open_at(sha) for sha in self.shas]
        second_newest = opened[-2]
        context = self.registry.get(second_newest["projectId"], second_newest["revision"])
        self.assertEqual(context.revision, second_newest["revision"])

    def test_revision_mismatch_is_rejected(self):
        opened = self.open_at(self.shas[-1])
        with self.assertRaises(ExplorerError) as mismatch:
            self.registry.get(opened["projectId"], self.shas[0])
        self.assertEqual(mismatch.exception.code, "REVISION_MISMATCH")

    def test_in_flight_context_survives_eviction(self):
        first = self.open_at(self.shas[0])
        context = self.registry.get(first["projectId"], first["revision"])
        for sha in self.shas[1:]:
            self.open_at(sha)
        self.assertEqual(context.revision, self.shas[0])
        self.assertIn("x.py", context.sources)
        self.assertTrue(context.coverage["trackedFileCount"] >= 1)

    def test_reopening_evicted_context_issues_fresh_identity(self):
        first = self.open_at(self.shas[0])
        for sha in self.shas[1:]:
            self.open_at(sha)
        reopened = self.open_at(self.shas[0])
        self.assertNotEqual(reopened["projectId"], first["projectId"])
        self.assertEqual(reopened["revision"], first["revision"])


if __name__ == "__main__":
    unittest.main()
