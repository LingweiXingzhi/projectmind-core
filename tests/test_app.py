import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import build_snapshot, read_evidence


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args]).decode("utf-8", errors="replace").strip()


class SnapshotTests(unittest.TestCase):
    def test_evidence_is_read_from_pinned_commit_not_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init")
            run_git(repo, "config", "user.name", "ProjectMind Test")
            run_git(repo, "config", "user.email", "test@example.invalid")
            (repo / "entry.py").write_text("committed version\n", encoding="utf-8")
            run_git(repo, "add", "entry.py")
            run_git(repo, "commit", "-m", "add entry")
            commit = run_git(repo, "rev-parse", "HEAD")
            (repo / "entry.py").write_text("uncommitted version\n", encoding="utf-8")
            map_path = repo / "map.json"
            map_path.write_text(
                json.dumps({
                    "note": "demo",
                    "nodes": [{"id": "one", "evidence": [
                        {"path": "entry.py"}, {"path": "missing.py"}
                    ]}],
                    "edges": [],
                }),
                encoding="utf-8",
            )

            snapshot = build_snapshot(repo, map_path)
            self.assertEqual(snapshot["revision"], commit)
            self.assertTrue(snapshot["nodes"][0]["evidence"][0]["existsAtCommit"])
            self.assertFalse(snapshot["nodes"][0]["evidence"][1]["existsAtCommit"])
            evidence = read_evidence(repo, map_path, "entry.py", commit)
            self.assertEqual(evidence["content"], "committed version\n")

    def test_only_declared_paths_can_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            map_path = repo / "map.json"
            map_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_evidence(repo, map_path, "secret.txt", "0" * 40)


if __name__ == "__main__":
    unittest.main()
