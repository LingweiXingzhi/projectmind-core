"""Independent contract examples for the Python symbol parser."""

import unittest

from repo_index.symbols import parse_symbols


class ParseSymbolsTests(unittest.TestCase):
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

        self.assertIs(type(result), dict)
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


if __name__ == "__main__":
    unittest.main()
