# -*- coding: utf-8 -*-
"""R48-05: Context Authority Git readers must not follow inherited GIT_*.

Codex r48 reproduced this on the real checkout: pointing `GIT_DIR` at another
repository's `.git` changed `_project_revision`'s answer from this checkout's
revision to the foreign one. `build_context_pack` accepts `revision=None`, so
the public context interface reaches that path by default and could stamp a
Context Pack with the wrong revision. `make_main_head_verifier` reads
`refs/remotes/origin/main` the same way.

Both are pre-existing baseline code; they were found by this batch's
repository-wide isolation sweep and are fixed here with the same rule the
worklog/continuity stores already apply: the explicit repository always wins,
and every inherited GIT_* variable is stripped from the subprocess.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from extensions.context_authority.context_pack import _project_revision
from extensions.context_authority.verifiers import make_main_head_verifier


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


class ContextAuthorityGitIsolationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "ca-repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.name", "T")
        _git(self.repo, "config", "user.email", "t@example.invalid")
        (self.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "base")
        self.head = _git(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "update-ref", "refs/remotes/origin/main", self.head)

        self.other = Path(self._tmp.name) / "other"
        self.other.mkdir()
        _git(self.other, "init", "-q", "-b", "main")
        _git(self.other, "config", "user.name", "T")
        _git(self.other, "config", "user.email", "t@example.invalid")
        (self.other / "b.py").write_text("y = 2\n", encoding="utf-8")
        _git(self.other, "add", ".")
        _git(self.other, "commit", "-qm", "other")
        self.other_head = _git(self.other, "rev-parse", "HEAD")
        self.assertNotEqual(self.head, self.other_head)

    def tearDown(self):
        self._tmp.cleanup()

    def _hostile(self) -> dict:
        return {"GIT_DIR": str(self.other / ".git"),
                "GIT_WORK_TREE": str(self.other),
                "GIT_COMMON_DIR": str(self.other / ".git")}

    def test_project_revision_ignores_inherited_git_environment(self):
        self.assertEqual(_project_revision(str(self.repo), None), self.head)
        with patch.dict(os.environ, self._hostile()):
            self.assertEqual(_project_revision(str(self.repo), None), self.head)
            self.assertEqual(_project_revision(str(self.repo), self.head), self.head)

    def test_main_head_verifier_ignores_inherited_git_environment(self):
        verify = make_main_head_verifier(str(self.repo))
        self.assertEqual(verify({})["value"]["sha"], self.head)
        with patch.dict(os.environ, self._hostile()):
            result = verify({})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["value"]["sha"], self.head)
        self.assertNotEqual(result["value"]["sha"], self.other_head)


if __name__ == "__main__":
    unittest.main()
