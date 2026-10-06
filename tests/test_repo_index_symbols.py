"""Independent contract examples for the Python symbol parser."""

import unittest

from repo_index.symbols import parse_symbols


class ParseSymbolsTests(unittest.TestCase):
    def assert_contract(self, result, path, status):
        self.assertIs(type(result), dict)
        self.assertEqual(
            set(result), {"path", "language", "status", "symbols", "warnings"}
        )
        self.assertIs(type(result["path"]), str)
        self.assertEqual(result["path"], path)
        self.assertIs(type(result["status"]), str)
        self.assertEqual(result["status"], status)
        if status != "unsupported":
            self.assertEqual(result["language"], "python")
        self.assertIs(type(result["symbols"]), list)
        self.assertIs(type(result["warnings"]), list)
        for warning in result["warnings"]:
            self.assertIs(type(warning), str)
            self.assertTrue(warning.strip())
        for symbol in result["symbols"]:
            self.assertIs(type(symbol), dict)
            self.assertEqual(
                set(symbol),
                {
                    "name", "qualified_name", "kind", "start_line", "end_line",
                    "docstring",
                },
            )
            for field in ("name", "qualified_name", "kind"):
                self.assertIs(type(symbol[field]), str)
            self.assertIn(
                symbol["kind"],
                {"class", "function", "async_function", "method", "async_method"},
            )
            self.assertIs(type(symbol["start_line"]), int)
            self.assertIs(type(symbol["end_line"]), int)
            self.assertGreaterEqual(symbol["start_line"], 1)
            self.assertGreaterEqual(symbol["end_line"], symbol["start_line"])
            if symbol["docstring"] is not None:
                self.assertIs(type(symbol["docstring"]), str)
                self.assertLessEqual(len(symbol["docstring"]), 2000)

    def assert_ok_symbols(self, path, source, expected_symbols):
        result = parse_symbols(path, source)
        self.assert_contract(result, path, "ok")
        self.assertEqual(result["symbols"], expected_symbols)
        self.assertEqual(result["warnings"], [])

    def test_function_class_and_method_have_exact_source_ranges(self):
        source = (
            "def compute(value):\n"
            "    result = value + 1\n"
            "    return result\n"
            "\n"
            "class Service:\n"
            "    def run(self):\n"
            "        message = 'ready'\n"
            "        return message\n"
        )

        result = parse_symbols("pkg/service.py", source)

        self.assert_contract(result, "pkg/service.py", "ok")
        self.assertEqual(
            result,
            {
                "path": "pkg/service.py",
                "language": "python",
                "status": "ok",
                "symbols": [
                    {
                        "name": "compute",
                        "qualified_name": "compute",
                        "kind": "function",
                        "start_line": 1,
                        "end_line": 3,
                        "docstring": None,
                    },
                    {
                        "name": "Service",
                        "qualified_name": "Service",
                        "kind": "class",
                        "start_line": 5,
                        "end_line": 8,
                        "docstring": None,
                    },
                    {
                        "name": "run",
                        "qualified_name": "Service.run",
                        "kind": "method",
                        "start_line": 6,
                        "end_line": 8,
                        "docstring": None,
                    },
                ],
                "warnings": [],
            },
        )

    def test_async_function_and_method(self):
        source = (
            "async def fetch():\n"
            "    return 1\n"
            "\n"
            "class Worker:\n"
            "    async def work(self):\n"
            "        return 2\n"
        )
        self.assert_ok_symbols(
            "worker.py", source,
            [
                {
                    "name": "fetch", "qualified_name": "fetch",
                    "kind": "async_function", "start_line": 1, "end_line": 2,
                    "docstring": None,
                },
                {
                    "name": "Worker", "qualified_name": "Worker",
                    "kind": "class", "start_line": 4, "end_line": 6,
                    "docstring": None,
                },
                {
                    "name": "work", "qualified_name": "Worker.work",
                    "kind": "async_method", "start_line": 5, "end_line": 6,
                    "docstring": None,
                },
            ],
        )

    def test_if_try_except_and_for_do_not_create_definition_scopes(self):
        source = (
            "class Container:\n"
            "    if enabled:\n"
            "        def conditional(self):\n"
            "            pass\n"
            "    try:\n"
            "        def attempted(self):\n"
            "            pass\n"
            "    except Exception:\n"
            "        def recovered(self):\n"
            "            pass\n"
            "    for item in items:\n"
            "        async def looped(self):\n"
            "            pass\n"
        )
        self.assert_ok_symbols(
            "container.py", source,
            [
                {
                    "name": "Container", "qualified_name": "Container",
                    "kind": "class", "start_line": 1, "end_line": 13,
                    "docstring": None,
                },
                {
                    "name": "conditional",
                    "qualified_name": "Container.conditional",
                    "kind": "method", "start_line": 3, "end_line": 4,
                    "docstring": None,
                },
                {
                    "name": "attempted", "qualified_name": "Container.attempted",
                    "kind": "method", "start_line": 6, "end_line": 7,
                    "docstring": None,
                },
                {
                    "name": "recovered", "qualified_name": "Container.recovered",
                    "kind": "method", "start_line": 9, "end_line": 10,
                    "docstring": None,
                },
                {
                    "name": "looped", "qualified_name": "Container.looped",
                    "kind": "async_method", "start_line": 12, "end_line": 13,
                    "docstring": None,
                },
            ],
        )

    def test_nested_definitions_use_nearest_definition_scope_and_source_order(self):
        source = (
            "class Outer:\n"
            "    def build(self):\n"
            "        def helper():\n"
            "            return 1\n"
            "        async def async_helper():\n"
            "            return 2\n"
            "        class Inner:\n"
            "            def act(self):\n"
            "                pass\n"
            "            async def wait(self):\n"
            "                pass\n"
            "        return Inner\n"
            "    def finish(self):\n"
            "        pass\n"
            "\n"
            "def outside():\n"
            "    pass\n"
        )
        self.assert_ok_symbols(
            "nested.py", source,
            [
                {
                    "name": "Outer", "qualified_name": "Outer",
                    "kind": "class", "start_line": 1, "end_line": 14,
                    "docstring": None,
                },
                {
                    "name": "build", "qualified_name": "Outer.build",
                    "kind": "method", "start_line": 2, "end_line": 12,
                    "docstring": None,
                },
                {
                    "name": "helper", "qualified_name": "Outer.build.helper",
                    "kind": "function", "start_line": 3, "end_line": 4,
                    "docstring": None,
                },
                {
                    "name": "async_helper",
                    "qualified_name": "Outer.build.async_helper",
                    "kind": "async_function", "start_line": 5, "end_line": 6,
                    "docstring": None,
                },
                {
                    "name": "Inner", "qualified_name": "Outer.build.Inner",
                    "kind": "class", "start_line": 7, "end_line": 11,
                    "docstring": None,
                },
                {
                    "name": "act", "qualified_name": "Outer.build.Inner.act",
                    "kind": "method", "start_line": 8, "end_line": 9,
                    "docstring": None,
                },
                {
                    "name": "wait", "qualified_name": "Outer.build.Inner.wait",
                    "kind": "async_method", "start_line": 10, "end_line": 11,
                    "docstring": None,
                },
                {
                    "name": "finish", "qualified_name": "Outer.finish",
                    "kind": "method", "start_line": 13, "end_line": 14,
                    "docstring": None,
                },
                {
                    "name": "outside", "qualified_name": "outside",
                    "kind": "function", "start_line": 16, "end_line": 17,
                    "docstring": None,
                },
            ],
        )

    def test_control_blocks_inside_function_keep_function_scope(self):
        source = (
            "def factory():\n"
            "    if True:\n"
            "        def operation():\n"
            "            pass\n"
            "    try:\n"
            "        async def later():\n"
            "            pass\n"
            "    finally:\n"
            "        class Product:\n"
            "            def produce(self):\n"
            "                pass\n"
        )
        self.assert_ok_symbols(
            "factory.py", source,
            [
                {
                    "name": "factory", "qualified_name": "factory",
                    "kind": "function", "start_line": 1, "end_line": 11,
                    "docstring": None,
                },
                {
                    "name": "operation", "qualified_name": "factory.operation",
                    "kind": "function", "start_line": 3, "end_line": 4,
                    "docstring": None,
                },
                {
                    "name": "later", "qualified_name": "factory.later",
                    "kind": "async_function", "start_line": 6, "end_line": 7,
                    "docstring": None,
                },
                {
                    "name": "Product", "qualified_name": "factory.Product",
                    "kind": "class", "start_line": 9, "end_line": 11,
                    "docstring": None,
                },
                {
                    "name": "produce",
                    "qualified_name": "factory.Product.produce",
                    "kind": "method", "start_line": 10, "end_line": 11,
                    "docstring": None,
                },
            ],
        )

    def test_decorators_and_multiline_signatures_preserve_definition_ranges(self):
        source = (
            "@class_decorator\n"
            "class Decorated:\n"
            "    @staticmethod\n"
            "    @other_decorator(\n"
            "        option=True,\n"
            "    )\n"
            "    def build(\n"
            "        first,\n"
            "        second,\n"
            "    ):\n"
            "        value = (\n"
            "            first + second\n"
            "        )\n"
            "        return value\n"
            "\n"
            "@first_decorator\n"
            "@second_decorator\n"
            "async def run(\n"
            "    value,\n"
            "):\n"
            "    return value\n"
        )
        self.assert_ok_symbols(
            "decorated.py", source,
            [
                {
                    "name": "Decorated", "qualified_name": "Decorated",
                    "kind": "class", "start_line": 2, "end_line": 14,
                    "docstring": None,
                },
                {
                    "name": "build", "qualified_name": "Decorated.build",
                    "kind": "method", "start_line": 7, "end_line": 14,
                    "docstring": None,
                },
                {
                    "name": "run", "qualified_name": "run",
                    "kind": "async_function", "start_line": 18, "end_line": 21,
                    "docstring": None,
                },
            ],
        )

    def test_duplicate_function_and_method_names_are_not_overwritten(self):
        source = (
            "def same():\n"
            "    pass\n"
            "\n"
            "def same():\n"
            "    pass\n"
            "\n"
            "class Same:\n"
            "    def same(self):\n"
            "        pass\n"
            "\n"
            "    def same(self):\n"
            "        pass\n"
        )
        self.assert_ok_symbols(
            "duplicates.py", source,
            [
                {
                    "name": "same", "qualified_name": "same",
                    "kind": "function", "start_line": 1, "end_line": 2,
                    "docstring": None,
                },
                {
                    "name": "same", "qualified_name": "same",
                    "kind": "function", "start_line": 4, "end_line": 5,
                    "docstring": None,
                },
                {
                    "name": "Same", "qualified_name": "Same",
                    "kind": "class", "start_line": 7, "end_line": 12,
                    "docstring": None,
                },
                {
                    "name": "same", "qualified_name": "Same.same",
                    "kind": "method", "start_line": 8, "end_line": 9,
                    "docstring": None,
                },
                {
                    "name": "same", "qualified_name": "Same.same",
                    "kind": "method", "start_line": 11, "end_line": 12,
                    "docstring": None,
                },
            ],
        )

    def test_chinese_names_and_docstrings_keep_text_and_clean_indentation(self):
        source = (
            "class 服务:\n"
            "    \"\"\"服务说明。\n"
            "\n"
            "        第二段。\n"
            "    \"\"\"\n"
            "    def 处理(self):\n"
            "        \"\"\"第一行。\n"
            "\n"
            "            第二行。\n"
            "        \"\"\"\n"
            "        return '中文'\n"
        )
        self.assert_ok_symbols(
            "pkg/中文.py", source,
            [
                {
                    "name": "服务", "qualified_name": "服务",
                    "kind": "class", "start_line": 1, "end_line": 11,
                    "docstring": "服务说明。\n\n第二段。",
                },
                {
                    "name": "处理", "qualified_name": "服务.处理",
                    "kind": "method", "start_line": 6, "end_line": 11,
                    "docstring": "第一行。\n\n第二行。",
                },
            ],
        )

    def test_docstring_at_2000_characters_is_not_truncated(self):
        source = 'def exact():\n    """' + ("x" * 2000) + '"""\n    pass\n'
        self.assert_ok_symbols(
            "exact.py", source,
            [
                {
                    "name": "exact", "qualified_name": "exact",
                    "kind": "function", "start_line": 1, "end_line": 3,
                    "docstring": "x" * 2000,
                },
            ],
        )

    def test_long_docstring_is_truncated_by_characters_with_warning(self):
        source = 'def 长文():\n    """' + ("中" * 2001) + '"""\n    pass\n'
        result = parse_symbols("long.py", source)
        self.assert_contract(result, "long.py", "ok")
        self.assertEqual(
            result["symbols"],
            [
                {
                    "name": "长文", "qualified_name": "长文",
                    "kind": "function", "start_line": 1, "end_line": 3,
                    "docstring": "中" * 2000,
                },
            ],
        )
        self.assertTrue(result["warnings"])

    def test_python_and_stub_extensions_are_case_insensitive(self):
        for path in ("pkg/module.py", "pkg/module.Py", "pkg/types.pyi", "pkg/types.PYI"):
            with self.subTest(path=path):
                self.assert_ok_symbols(
                    path, "def declared() -> int: ...\n",
                    [
                        {
                            "name": "declared", "qualified_name": "declared",
                            "kind": "function", "start_line": 1, "end_line": 1,
                            "docstring": None,
                        },
                    ],
                )

    def test_empty_and_whitespace_only_files_are_successful_empty_results(self):
        for source in ("", " \t\n\n", "# 只有注释\n\n"):
            with self.subTest(source=source):
                self.assert_ok_symbols("empty.py", source, [])

    def test_syntax_error_discards_partial_symbols_and_reports_error_line(self):
        source = "def good():\n    pass\n\ndef broken(:\n    pass\n"
        result = parse_symbols("syntax.py", source)
        self.assert_contract(result, "syntax.py", "parse_error")
        self.assertEqual(result["symbols"], [])
        self.assertTrue(result["warnings"])
        warning_text = "\n".join(result["warnings"])
        self.assertRegex(warning_text, r"(?<!\d)4(?!\d)")
        self.assertRegex(warning_text, r"[A-Za-z\u4e00-\u9fff]")
        self.assertNotIn(source, warning_text)

    def test_non_python_extensions_are_unsupported_even_with_invalid_source(self):
        for path in ("notes.txt", "script.js", "module.py.txt", "README", "module"):
            with self.subTest(path=path):
                result = parse_symbols(path, "def broken(:\n")
                self.assert_contract(result, path, "unsupported")
                self.assertEqual(result["symbols"], [])

    def test_null_character_error_reports_line_for_all_python_newlines(self):
        for newline in ("\n", "\r\n", "\r"):
            with self.subTest(newline=newline):
                source = "def ok():" + newline + "    pass" + newline + "\x00" + newline
                result = parse_symbols("null.py", source)
                self.assert_contract(result, "null.py", "parse_error")
                self.assertEqual(result["symbols"], [])
                self.assertTrue(result["warnings"])
                warning_text = "\n".join(result["warnings"])
                self.assertRegex(warning_text, r"(?<!\d)3(?!\d)")
                self.assertNotIn(source, warning_text)

    def test_comments_and_strings_do_not_create_symbols(self):
        source = (
            "# def fake():\n"
            "# class Fake:\n"
            "text = '''\n"
            "def hidden():\n"
            "    pass\n"
            "class Hidden:\n"
            "    pass\n"
            "'''\n"
            "def real():\n"
            "    return text\n"
        )
        self.assert_ok_symbols(
            "strings.py", source,
            [
                {
                    "name": "real", "qualified_name": "real",
                    "kind": "function", "start_line": 9, "end_line": 10,
                    "docstring": None,
                },
            ],
        )

    def test_source_imports_and_module_and_class_bodies_are_not_executed(self):
        source = (
            "import definitely_missing_source_dependency\n"
            "raise RuntimeError('source must not run')\n"
            "def visible():\n"
            "    return 1\n"
            "class Demo:\n"
            "    assert False, 'class body must not run'\n"
            "    def method(self):\n"
            "        return 2\n"
        )
        self.assert_ok_symbols(
            "never-executed.py", source,
            [
                {
                    "name": "visible", "qualified_name": "visible",
                    "kind": "function", "start_line": 3, "end_line": 4,
                    "docstring": None,
                },
                {
                    "name": "Demo", "qualified_name": "Demo",
                    "kind": "class", "start_line": 5, "end_line": 8,
                    "docstring": None,
                },
                {
                    "name": "method", "qualified_name": "Demo.method",
                    "kind": "method", "start_line": 7, "end_line": 8,
                    "docstring": None,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
