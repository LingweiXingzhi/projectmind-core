import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import build_snapshot, compare_commits, export_markdown, read_evidence


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
                    "nodes": [{"id": "one", "title": "Example", "summary": "A test node", "entryPoint": "entry.py", "evidence": [
                        {"path": "entry.py", "reason": "entry"},
                        {"path": "missing.py", "reason": "missing"}
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
            exported = export_markdown(snapshot)
            self.assertIn(f"Git 提交：{commit}", exported)
            self.assertIn("entry.py — 该提交中存在", exported)
            self.assertIn("missing.py — 该提交中缺失", exported)

    def test_only_declared_paths_can_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            map_path = repo / "map.json"
            map_path.write_text(json.dumps({"nodes": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_evidence(repo, map_path, "secret.txt", "0" * 40)

    def test_rename_and_delete_only_flag_nodes_with_changed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init")
            run_git(repo, "config", "user.name", "ProjectMind Test")
            run_git(repo, "config", "user.email", "test@example.invalid")
            (repo / "old.py").write_text("entry point\n", encoding="utf-8")
            (repo / "unchanged.py").write_text("other\n", encoding="utf-8")
            run_git(repo, "add", "old.py", "unchanged.py")
            run_git(repo, "commit", "-m", "base")
            base = run_git(repo, "rev-parse", "HEAD")
            map_path = repo / "map.json"
            map_path.write_text(json.dumps({"nodes": [
                {"id": "old", "evidence": [{"path": "old.py"}]},
                {"id": "renamed", "evidence": [{"path": "renamed.py"}]},
                {"id": "unrelated", "evidence": [{"path": "unchanged.py"}]},
            ]}), encoding="utf-8")

            run_git(repo, "mv", "old.py", "renamed.py")
            run_git(repo, "commit", "-m", "rename")
            renamed = run_git(repo, "rev-parse", "HEAD")
            first = compare_commits(repo, map_path, base, renamed)
            self.assertEqual(first["changes"][0]["oldPath"], "old.py")
            self.assertEqual(first["changes"][0]["path"], "renamed.py")
            self.assertTrue(first["changes"][0]["code"].startswith("R"))
            self.assertEqual({item["nodeId"] for item in first["reviewCandidates"]}, {"old", "renamed"})

            run_git(repo, "rm", "renamed.py")
            run_git(repo, "commit", "-m", "delete")
            deleted = run_git(repo, "rev-parse", "HEAD")
            second = compare_commits(repo, map_path, renamed, deleted)
            self.assertEqual(second["changes"], [{"code": "D", "path": "renamed.py"}])
            self.assertEqual([item["nodeId"] for item in second["reviewCandidates"]], ["renamed"])


if __name__ == "__main__":
    unittest.main()
