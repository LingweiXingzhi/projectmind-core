import json
import os
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from app import AIError, ai_status, build_snapshot, compare_commits, explain_change, export_markdown, read_evidence, request_model


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

    def test_ai_explanation_only_receives_selected_changed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run_git(repo, "init")
            run_git(repo, "config", "user.name", "ProjectMind Test")
            run_git(repo, "config", "user.email", "test@example.invalid")
            (repo / "entry.py").write_text("old entry\n", encoding="utf-8")
            (repo / "unrelated.py").write_text("old unrelated\n", encoding="utf-8")
            run_git(repo, "add", ".")
            run_git(repo, "commit", "-m", "base")
            base = run_git(repo, "rev-parse", "HEAD")
            map_path = repo / "map.json"
            map_path.write_text(json.dumps({"nodes": [
                {"id": "selected", "title": "Selected", "summary": "Demo", "evidence": [{"path": "entry.py"}]},
                {"id": "other", "title": "Other", "summary": "Demo", "evidence": [{"path": "unrelated.py"}]},
            ]}), encoding="utf-8")
            (repo / "entry.py").write_text("new entry\n", encoding="utf-8")
            (repo / "unrelated.py").write_text("new unrelated\n", encoding="utf-8")
            run_git(repo, "add", ".")
            run_git(repo, "commit", "-m", "change")
            target = run_git(repo, "rev-parse", "HEAD")
            candidate = {"summary": "Entry changed", "observations": ["Changed line"],
                         "possibleEffects": [], "unknowns": ["Runtime behavior"], "evidencePaths": ["entry.py"]}
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "PROJECTMIND_AI_MODEL": "test-model"}):
                with patch("app.request_model", return_value=candidate) as model:
                    result = explain_change(repo, map_path, base, target, "selected")
                sent = model.call_args.args[0]
                self.assertEqual(sent["changedEvidencePaths"], ["entry.py"])
                self.assertIn("new entry", sent["diff"])
                self.assertNotIn("unrelated.py", sent["diff"])
                self.assertEqual(result["status"], "ai_candidate")
                with patch("app.request_model", return_value={**candidate, "evidencePaths": ["unrelated.py"]}):
                    with self.assertRaises(AIError):
                        explain_change(repo, map_path, base, target, "selected")

    def test_model_request_is_stateless_and_collects_message_text(self) -> None:
        reply = {"status": "completed", "output": [
            {"type": "reasoning"},
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps({
                "summary": "Change", "observations": [], "possibleEffects": [], "unknowns": [], "evidencePaths": []})}]},
        ]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "PROJECTMIND_AI_MODEL": "test-model"}):
            with patch("app.urlopen", return_value=BytesIO(json.dumps(reply).encode("utf-8"))) as post:
                result = request_model({"changedEvidencePaths": [], "diff": "sample"})
            body = json.loads(post.call_args.args[0].data)
            self.assertFalse(body["store"])
            self.assertEqual(body["text"]["format"]["type"], "json_schema")
            self.assertEqual(result["summary"], "Change")

    def test_ai_is_explicitly_unavailable_without_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ai_status()["configured"])
            with self.assertRaises(AIError):
                request_model({})


if __name__ == "__main__":
    unittest.main()
