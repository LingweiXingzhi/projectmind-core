# -*- coding: utf-8 -*-
"""UI-01 regressions: evidence links honor the /api/evidence contract.

Two layers:
- the pure decision (web/evidence-links.js) is exercised through node for
  every change type x map-declaration combination from the repair plan's
  smoke list (added, deleted, renamed, modified mapped, modified unmapped);
- the backend truth the decision must obey is pinned against the real
  read_evidence endpoint function (declared+present -> 200; undeclared ->
  controlled error; declared-but-absent-at-revision -> controlled 404).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

HARNESS = (
    "const fs = require('fs');\n"
    "eval(fs.readFileSync(process.argv[1], 'utf8'));\n"
    "const cases = JSON.parse(process.argv[2]);\n"
    "const out = cases.map((c) => evidenceTargetsFor(c.change, new Set(c.declared)));\n"
    "console.log(JSON.stringify(out));\n"
)


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()


@unittest.skipIf(NODE is None, "node is not available for the pure-function harness")
class EvidenceLinkDecisionTests(unittest.TestCase):
    def decide(self, cases):
        proc = subprocess.run(
            [NODE, "-e", HARNESS, str(ROOT / "web" / "evidence-links.js"),
             json.dumps(cases)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_added_file(self):
        # ADDED: the content context is the target revision — but only when
        # the path is map evidence (undeclared additions have no evidence
        # view; the old UI linked them into a 400).
        (added_declared,) = self.decide([
            {"change": {"code": "A", "path": "pkg/new.py"}, "declared": ["pkg/new.py"]}])
        self.assertEqual(added_declared, [{"path": "pkg/new.py", "revision": "target"}])
        (added_undeclared,) = self.decide([
            {"change": {"code": "A", "path": "pkg/new.py"}, "declared": []}])
        self.assertEqual(added_undeclared, [])

    def test_deleted_file(self):
        # DELETED: the content context is the base revision; a target link
        # would 404 and fabricate "target evidence" for a deleted file.
        (deleted_declared,) = self.decide([
            {"change": {"code": "D", "path": "pkg/old.py"}, "declared": ["pkg/old.py"]}])
        self.assertEqual(deleted_declared, [{"path": "pkg/old.py", "revision": "base"}])
        (deleted_undeclared,) = self.decide([
            {"change": {"code": "D", "path": "pkg/old.py"}, "declared": []}])
        self.assertEqual(deleted_undeclared, [])

    def test_renamed_file(self):
        # RENAMED: old path at base AND new path at target, each only when
        # declared.
        (both,) = self.decide([
            {"change": {"code": "R100", "oldPath": "pkg/old.py", "path": "pkg/new.py"},
             "declared": ["pkg/old.py", "pkg/new.py"]}])
        self.assertEqual(both, [
            {"path": "pkg/old.py", "revision": "base"},
            {"path": "pkg/new.py", "revision": "target"},
        ])
        (old_only,) = self.decide([
            {"change": {"code": "R100", "oldPath": "pkg/old.py", "path": "pkg/new.py"},
             "declared": ["pkg/old.py"]}])
        self.assertEqual(old_only, [{"path": "pkg/old.py", "revision": "base"}])
        (new_only,) = self.decide([
            {"change": {"code": "R100", "oldPath": "pkg/old.py", "path": "pkg/new.py"},
             "declared": ["pkg/new.py"]}])
        self.assertEqual(new_only, [{"path": "pkg/new.py", "revision": "target"}])

    def test_modified_file(self):
        (mapped,) = self.decide([
            {"change": {"code": "M", "path": "pkg/a.py"}, "declared": ["pkg/a.py"]}])
        self.assertEqual(mapped, [{"path": "pkg/a.py", "revision": "target"}])
        (unmapped,) = self.decide([
            {"change": {"code": "M", "path": "pkg/a.py"}, "declared": []}])
        self.assertEqual(unmapped, [])


def demo_node(identifier: str, paths: list) -> dict:
    return {"id": identifier, "title": identifier, "summary": "s", "entryPoint": "e",
            "position": {"x": 0, "y": 0},
            "evidence": [{"path": p, "reason": "r"} for p in paths]}


class EvidenceEndpointContractTests(unittest.TestCase):
    """The backend truth the UI decision is bound to."""

    def test_declared_but_absent_at_revision_is_controlled_error(self) -> None:
        from app import read_evidence
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init")
            run_git(repo, "config", "user.name", "t")
            run_git(repo, "config", "user.email", "t@example.invalid")
            (repo / "entry.py").write_text("base content\n", encoding="utf-8")
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-m", "base")
            base = run_git(repo, "rev-parse", "HEAD")
            (repo / "entry.py").unlink()
            run_git(repo, "add", "-A")
            run_git(repo, "commit", "-m", "delete entry")
            target = run_git(repo, "rev-parse", "HEAD")
            map_path = repo / "map.json"
            map_path.write_text(json.dumps({
                "note": "m",
                "nodes": [demo_node("one", ["entry.py"])],
                "edges": [],
            }), encoding="utf-8")
            # Declared and present at base: valid evidence view (the UI's
            # deleted-file link target).
            evidence = read_evidence(repo, map_path, "entry.py", base)
            self.assertEqual(evidence["content"], "base content\n")
            # Declared but absent at target: controlled error (404 class),
            # never empty content pretending to be evidence.
            with self.assertRaises(FileNotFoundError):
                read_evidence(repo, map_path, "entry.py", target)


if __name__ == "__main__":
    unittest.main()
