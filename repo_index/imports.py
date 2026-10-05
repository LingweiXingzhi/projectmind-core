import ast
from pathlib import PurePath
from typing import Any, Dict, List


def parse_imports(path: str, source: str) -> Dict[str, Any]:
    norm_path = path.replace("\\", "/")
    ext = PurePath(norm_path).suffix.lower()

    if ext not in (".py", ".pyi"):
        return {
            "path": norm_path,
            "language": "unknown",
            "status": "unsupported",
            "imports": [],
            "warnings": [f"Unsupported file extension: {ext}"],
        }

    if not source.strip():
        return {
            "path": norm_path,
            "language": "python",
            "status": "ok",
            "imports": [],
            "warnings": [],
        }

    try:
        tree = ast.parse(source, filename=norm_path)
    except SyntaxError as e:
        return {
            "path": norm_path,
            "language": "python",
            "status": "parse_error",
            "imports": [],
            "warnings": [f"SyntaxError at line {e.lineno}: {e.msg}"],
        }
    except Exception as e:
        return {
            "path": norm_path,
            "language": "python",
            "status": "parse_error",
            "imports": [],
            "warnings": [f"Parse failed: {str(e)}"],
        }

    imports_list: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            start_line = getattr(node, "lineno", 1)
            end_line = getattr(node, "end_lineno", start_line)
            for alias in node.names:
                imports_list.append({
                    "kind": "import",
                    "module": alias.name,
                    "level": 0,
                    "name": None,
                    "alias": alias.asname,
                    "line": start_line,
                    "end_line": end_line,
                })
        elif isinstance(node, ast.ImportFrom):
            start_line = getattr(node, "lineno", 1)
            end_line = getattr(node, "end_lineno", start_line)
            module = node.module or ""
            level = node.level or 0
            for alias in node.names:
                if alias.name == "*":
                    warnings.append(f"Wildcard import at line {start_line} was not expanded")
                imports_list.append({
                    "kind": "from",
                    "module": module,
                    "level": level,
                    "name": alias.name,
                    "alias": alias.asname,
                    "line": start_line,
                    "end_line": end_line,
                })

    # 按源码行号稳定排序，保留同语句别名的原始顺序
    imports_list.sort(key=lambda x: (x["line"], x["end_line"]))

    return {
        "path": norm_path,
        "language": "python",
        "status": "ok",
        "imports": imports_list,
        "warnings": warnings,
    }
