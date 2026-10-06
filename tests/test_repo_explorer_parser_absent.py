# -*- coding: utf-8 -*-
"""R49-01: the two parser guards are independent — and honest.

B (symbols) and C (imports) arrive separately, so a deployment that has only
one of them must keep the other endpoint working. And a failure INSIDE a parser
that IS installed must surface as an error, never be misreported as "the parser
was never delivered".

Each case runs in its own interpreter with a meta-path finder that makes one
module genuinely unimportable.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import importlib.abc, json, sys

blocked = json.loads(sys.argv[1])
reported = json.loads(sys.argv[2])


class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name in blocked:
            raise ModuleNotFoundError("No module named " + repr(reported[name]),
                                      name=reported[name])
        return None


sys.meta_path.insert(0, Finder())
import repo_index.explorer as explorer
print(json.dumps({"symbols": explorer.parse_symbols is None,
                  "imports": explorer.parse_imports is None}))
"""

SYMBOLS = "repo_index.symbols"
IMPORTS = "repo_index.imports"


def run(blocked: list, reported: dict):
    return subprocess.run(
        [sys.executable, "-B", "-c", PROBE, json.dumps(blocked), json.dumps(reported)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", timeout=60)


class ParserGuardTests(unittest.TestCase):
    def test_a_complete_deployment_has_both_parsers(self):
        done = run([], {})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"symbols": False, "imports": False})

    def test_missing_symbols_parser_does_not_disable_imports(self):
        done = run([SYMBOLS], {SYMBOLS: SYMBOLS})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"symbols": True, "imports": False})

    def test_missing_imports_parser_does_not_disable_symbols(self):
        done = run([IMPORTS], {IMPORTS: IMPORTS})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"symbols": False, "imports": True})

    def test_both_parsers_missing(self):
        done = run([SYMBOLS, IMPORTS], {SYMBOLS: SYMBOLS, IMPORTS: IMPORTS})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"symbols": True, "imports": True})

    def test_a_failure_inside_an_installed_parser_is_not_reported_as_absent(self):
        # The module exists, but one of ITS dependencies is missing: that is an
        # installation error, so the import must fail loudly instead of
        # downgrading a working parser to "not integrated".
        done = run([SYMBOLS], {SYMBOLS: "some_internal_dependency"})
        self.assertNotEqual(done.returncode, 0,
                            "an internal import failure must not be swallowed")
        self.assertIn("some_internal_dependency", done.stderr)


if __name__ == "__main__":
    unittest.main()
