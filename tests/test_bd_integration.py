"""Regression tests for findings fixed after the Codex B+D integration audit (round 1).

Covers the handoff→continuity work-notes roundtrip, remote scheme preservation,
lazy-fetch prohibition in D evidence reads, and worklog category type handling.
"""
import base64
import subprocess
import tempfile
import unittest
from pathlib import Path

from extension_host import ExtensionContext, ExtensionError, ExtensionHost
import app as core_app


ROOT = Path(__file__).resolve().parent.parent


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"git {args}: {result.stderr.strip()}")
    return result.stdout.strip()


def build_repo(base: Path) -> Path:
    repo = base / "fixture"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "fixture@example.com")
    git(repo, "config", "user.name", "Fixture")
    (repo / "a.py").write_text("def alpha():\n    pass\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "c1")
    return repo


def make_host(repo: Path) -> ExtensionHost:
    return ExtensionHost(
        ROOT / "extensions",
        ExtensionContext(
            repo=repo,
            map_path=ROOT / "data" / "project-map.json",
            snapshot=lambda: core_app.build_snapshot(repo, ROOT / "data" / "project-map.json"),
            compare=lambda b, t: core_app.compare_commits(repo, ROOT / "data" / "project-map.json", b, t),
        ),
    )


class WorkNotesRoundtripTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name))
        self.host = make_host(self.repo)
        self.revision = core_app.build_snapshot(
            self.repo, ROOT / "data" / "project-map.json")["revision"]
        self.locator = {"kind": "local_path", "value": str(self.repo)}

    def test_export_with_notes_imports_into_continuity(self):
        exported = self.host.run("handoff", "POST", {
            "expectedRevision": self.revision, "comparisonMode": "custom",
            "sourceLocator": self.locator,
            "workNotes": {"completed": "集成完成", "pending": "C 未开始",
                          "blockers": "", "nextSteps": "开始 C"}})
        self.assertIn("status", exported["handoff"]["workNotes"])
        imported = self.host.run("continuity", "POST",
                                 {"action": "import_packet", "packet": exported["handoff"]})
        self.assertEqual(imported["record"]["state"], "receiving")
        self.assertEqual(imported["record"]["task"]["completed"], "集成完成")

    def test_export_without_notes_still_imports(self):
        exported = self.host.run("handoff", "POST", {
            "expectedRevision": self.revision, "comparisonMode": "custom",
            "sourceLocator": self.locator})
        imported = self.host.run("continuity", "POST",
                                 {"action": "import_packet", "packet": exported["handoff"]})
        self.assertEqual(imported["record"]["state"], "receiving")


class RemoteSchemeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name))
        git(self.repo, "remote", "add", "origin", "ssh://git@git.example:2222/team/repo.git")
        self.host = make_host(self.repo)

    def test_config_keeps_remote_scheme(self):
        got = self.host.run("continuity", "GET", {"action": "config"})
        self.assertEqual(got["defaultSource"]["kind"], "git_remote")
        self.assertEqual(got["defaultSource"]["value"], "ssh://git@git.example:2222/team/repo.git")

    def test_remotes_keeps_canonical_and_original(self):
        from extensions.continuity.inspection import remotes
        entries = remotes(self.repo)
        self.assertEqual(entries[0]["address"], "git.example:2222/team/repo")
        self.assertEqual(entries[0]["url"], "ssh://git@git.example:2222/team/repo.git")


class LazyFetchGuardTests(unittest.TestCase):
    def test_inspection_git_pins_no_lazy_fetch(self):
        source = (ROOT / "extensions" / "continuity" / "inspection.py").read_text(encoding="utf-8")
        self.assertIn("--no-lazy-fetch", source)
        self.assertIn("GIT_NO_LAZY_FETCH", source)


class WorklogCategoryTypeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name))
        self.host = make_host(self.repo)

    def test_non_string_category_is_400(self):
        with self.assertRaises(ExtensionError) as ctx:
            self.host.run("worklog", "POST", {
                "action": "save", "category": [], "date": "2026-10-04",
                "title": "t", "body": "b", "author": "a"})
        self.assertEqual(int(ctx.exception.status), 400)


if __name__ == "__main__":
    unittest.main()
