"""Regression for PR58 GEN-01; ordinary camelCase names remain usable."""
import unittest
import json
from pathlib import Path
import sys
import tempfile
from archloop.context_pack import _key_name_is_secret, _looks_like_secret
from archloop.context_pack import build_context_pack

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_archloop_a_backend_b import tiny_code_repo, run_git


class AcronymCredentialTests(unittest.TestCase):
    def test_acronym_boundaries_and_regular_names(self):
        for key in ("clientAPIKey", "APIKey", "HTTPAccessToken", "OIDCClientSecret", "clientAPI_KEY"):
            with self.subTest(key=key):
                self.assertTrue(_key_name_is_secret(key))
                self.assertTrue(_looks_like_secret(f'{key} = "abcdefghijklmnop123456"'))
        for key in ("monkey", "turkey", "keynote", "HTTPServiceName", "clientAPIEndpoint"):
            with self.subTest(key=key):
                self.assertFalse(_key_name_is_secret(key))

    def test_placeholder_words_in_field_names_or_inside_values_do_not_hide_credentials(self):
        for text in ('yourAPIKey = "q7V2n9J4r6L8p3H5z1B0d2M4"',
                     'TODO_API_KEY = "q7V2n9J4r6L8p3H5z1B0d2M4"',
                     'clientAPIKey = "actualTODOtokenabc123xyz"',
                     'clientAPIKey = "aaaxxxyyybbbbeeee4444"'):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_secret(text))
        for value in ('your-api-key-placeholder', '<YOUR_API_KEY_HERE>', 'xxxxxxxxxxxxxxxxxxxxxxxx'):
            self.assertFalse(_looks_like_secret(f'clientAPIKey = "{value}"'))

    def test_committed_source_pack_excludes_acronym_credentials_without_losing_regular_code(self):
        # Synthetic credential-looking text, never a real account/API secret.
        value = "q7V2n9J4r6L8p3H5z1B0d2M4"
        with tempfile.TemporaryDirectory() as directory:
            repo = tiny_code_repo(Path(directory))
            (repo / "app.py").write_text(f'clientAPIKey = "{value}"\n')
            (repo / "README.md").write_text(f'HTTPAccessToken: "{value}"\n')
            (repo / "consumer.py").write_text(f'yourAPIKey = "{value}"\n')
            safe = 'clientAPIEndpoint = "https://service.invalid/v1"\ndef monkey():\n    return "turkey"\n'
            (repo / "ordinary.py").write_text(safe)
            run_git(repo, "add", "app.py", "README.md", "ordinary.py", "consumer.py")
            run_git(repo, "commit", "-m", "synthetic context exclusion fixture")
            revision = run_git(repo, "rev-parse", "HEAD")
            # Worktree edits must not change the fixed revision's classification.
            (repo / "app.py").write_text("def harmless_worktree_only(): pass\n")
            (repo / "ordinary.py").write_text(f'clientAPIKey = "{value}"\n')
            pack = build_context_pack(str(repo), revision)
            self.assertEqual(pack["codeRevision"], revision)
            self.assertEqual(pack["coverage"]["codeRevision"], revision)
            self.assertNotIn(value, json.dumps(pack))
            self.assertTrue({"app.py", "README.md", "consumer.py"} <= {row["path"] for row in pack["excluded"]})
            included = {row["path"]: row for row in pack["files"]}
            self.assertEqual(included["ordinary.py"]["excerpt"], safe)
            self.assertNotIn("app.py", included)


if __name__ == "__main__": unittest.main()
