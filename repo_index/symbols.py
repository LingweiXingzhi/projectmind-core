"""Parse Python definitions from decoded source text without executing it."""

from __future__ import annotations

import ast

_DEFINITION_KINDS = {
    ast.ClassDef: "class",
    ast.FunctionDef: "function",
    ast.AsyncFunctionDef: "async_function",
}
_DOCSTRING_LIMIT = 2_000


def parse_symbols(path: str, source: str) -> dict:
    """Return lexical definitions, inclusive source ranges and cleaned docstrings.

    The caller supplies a repository-relative path and decoded source from one
    selected revision. This function does not read files, Git or project state.
    """
    if not isinstance(path, str) or not isinstance(source, str):
        raise TypeError("path and source must be strings")

    result = {
        "path": path,
        "language": "python",
        "status": "ok",
        "symbols": [],
        "warnings": [],
    }
    if not path.lower().endswith((".py", ".pyi")):
        result["status"] = "unsupported"
        result["warnings"].append("Unsupported file type; only .py and .pyi are parsed.")
        return result

    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError, UnicodeError, RecursionError) as exc:
        result["status"] = "parse_error"
        line = getattr(exc, "lineno", None)
        reason = getattr(exc, "msg", str(exc))[:240]
        result["warnings"].append(
            f"Parse error at line {line if line is not None else 'unknown'}: {reason}"
        )
        return result

    # Only definitions add scopes. Control-flow blocks preserve their parent's
    # nearest definition scope. Use a stack to avoid recursive visitor limits.
    pending = [(tree, ())]
    while pending:
        node, scope = pending.pop()
        category = _DEFINITION_KINDS.get(type(node))
        if category is not None:
            kind = category
            if scope and scope[-1][1] == "class" and category != "class":
                kind = "async_method" if category == "async_function" else "method"
            qualified_name = ".".join([name for name, _ in scope] + [node.name])
            docstring = ast.get_docstring(node, clean=True)
            if docstring is not None and len(docstring) > _DOCSTRING_LIMIT:
                docstring = docstring[:_DOCSTRING_LIMIT]
                result["warnings"].append(
                    f"Docstring for {qualified_name} at line {node.lineno} "
                    f"truncated to {_DOCSTRING_LIMIT} characters."
                )
            result["symbols"].append({
                "name": node.name,
                "qualified_name": qualified_name,
                "kind": kind,
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "docstring": docstring,
            })
            scope = (*scope, (node.name, category))
        pending.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))

    result["symbols"].sort(key=lambda item: (item["start_line"], item["qualified_name"]))
    return result

