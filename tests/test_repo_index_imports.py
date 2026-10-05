import unittest
from repo_index.imports import parse_imports


class TestRepoIndexImports(unittest.TestCase):

    def test_basic_imports_and_aliases(self):
        code = "import os\nimport sys as system, math"
        res = parse_imports("test.py", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(len(res["imports"]), 3)
        self.assertEqual(res["imports"][0]["module"], "os")
        self.assertEqual(res["imports"][1]["alias"], "system")
        self.assertIsNone(res["imports"][2]["alias"])

    def test_from_relative_imports(self):
        code = "from .utils import helper as h\nfrom ..core import Service\nfrom . import config"
        res = parse_imports("pkg/mod.py", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["imports"][0]["level"], 1)
        self.assertEqual(res["imports"][0]["alias"], "h")
        self.assertEqual(res["imports"][1]["level"], 2)
        self.assertEqual(res["imports"][2]["module"], "")
        self.assertEqual(res["imports"][2]["name"], "config")

    def test_wildcard_and_multiline(self):
        code = "from pkg import (\n    a,\n    b as b_alias\n)\nfrom wild import *"
        res = parse_imports("test.py", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["imports"][0]["line"], 1)
        self.assertEqual(res["imports"][0]["end_line"], 4)
        self.assertTrue(any("Wildcard" in w for w in res["warnings"]))

    def test_nested_in_function_or_condition(self):
        code = "def foo():\n    if True:\n        import inside\n"
        res = parse_imports("test.py", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["imports"][0]["module"], "inside")

    def test_syntax_error_and_unsupported(self):
        res_err = parse_imports("err.py", "def foo(:")
        self.assertEqual(res_err["status"], "parse_error")
        self.assertEqual(res_err["imports"], [])

        res_txt = parse_imports("test.txt", "import os")
        self.assertEqual(res_txt["status"], "unsupported")

    def test_empty_file(self):
        res = parse_imports("empty.py", "   \n")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["imports"], [])


if __name__ == "__main__":
    unittest.main()

    def test_pseudo_imports_and_dynamic_calls(self):
        code = '''
# import fake_comment_module
fake_str = "import fake_string_module"
mod = __import__('dynamic_module')
importlib.import_module('another_dynamic')
'''
        res = parse_imports("test.py", code)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(len(res["imports"]), 0)
