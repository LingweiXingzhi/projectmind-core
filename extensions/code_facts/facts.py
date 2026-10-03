"""Extract definitions from committed blobs without running project code."""
from __future__ import annotations

import ast
import io
import os
import re
import subprocess
import tokenize
from pathlib import Path

MAX_FILES = 2000
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 16_777_216
SHA_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class CodeFactsError(ValueError):
    """Expected input or repository error, safe to show to a local user."""


def _git(repo: Path, *args: str) -> bytes:
    # Ignore inherited GIT_DIR/GIT_WORK_TREE and other overrides: repo is explicit.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1", "LC_ALL": "C"})
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "--no-pager", "-C", str(repo), *args],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CodeFactsError("Git 不可用或读取超时") from exc
    if result.returncode:
        if result.returncode == 129 and b"no-lazy-fetch" in result.stderr:
            raise CodeFactsError("Git 版本需支持 --no-lazy-fetch，请升级 Git 后重试")
        raise CodeFactsError("无法读取指定 Git 仓库、提交或对象")
    return result.stdout


def repository_root(repo: Path | str) -> Path:
    try:
        root = Path(repo).expanduser().resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise CodeFactsError("仓库路径无效") from exc
    if not root.is_dir():
        raise CodeFactsError("仓库路径必须是目录")
    actual = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve()
    if actual != root:
        raise CodeFactsError("请提供 Git 仓库根目录，而非子目录")
    return root


def current_revision(repo: Path | str) -> str:
    """For initial UI defaults only; extraction still requires an explicit full SHA."""
    root = repository_root(repo)
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()


def _paths(paths: list[str] | None) -> list[str] | None:
    if paths is None:
        return None
    if not isinstance(paths, list) or len(paths) > MAX_FILES:
        raise CodeFactsError("paths 必须是最多 2000 项的路径列表")
    result = []
    for path in paths:
        if (
            not isinstance(path, str) or not path or "\\" in path
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or any(part in ("", ".", "..") for part in path.split("/"))
        ):
            raise CodeFactsError("路径须为仓库内相对文件路径，使用 /，不能含 .. 或控制字符")
        if path not in result:
            result.append(path)
    return result


def _definitions(syntax: ast.AST) -> list[dict]:
    # An explicit stack also handles valid, deeply chained expressions without
    # exhausting Python's recursion limit in NodeVisitor.generic_visit.
    pending = [(syntax, ())]
    entries = []
    categories = {ast.ClassDef: "class", ast.FunctionDef: "function",
                  ast.AsyncFunctionDef: "async_function"}
    while pending:
        node, scope = pending.pop()
        category = categories.get(type(node))
        if category:
            kind = category
            if scope and scope[-1][1] == "class" and category != "class":
                kind = "async_method" if category == "async_function" else "method"
            name = ".".join([part[0] for part in scope] + [node.name])
            entries.append({"name": name, "kind": kind, "line": node.lineno})
            scope = (*scope, (node.name, category))
        pending.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
    return entries


def collect_code_facts(repo: Path | str, revision: str, paths: list[str] | None = None) -> dict:
    """Return {revision, files, skipped}; paths=None selects all committed files.

    Only def/async def/class declarations are facts. Qualified names describe
    lexical nesting, not call relationships, runtime reachability or responsibility.
    Invalid inputs reject the request; unsupported/unparseable files are skipped.
    """
    if not isinstance(revision, str) or not SHA_PATTERN.fullmatch(revision):
        raise CodeFactsError("revision 必须是完整的 40 或 64 位小写 Git 提交 SHA")
    requested = _paths(paths)
    root = repository_root(repo)
    resolved = _git(root, "rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
    if resolved != revision:
        raise CodeFactsError("revision 必须直接指向提交，不能是标签对象")
    raw_tree = _git(root, "ls-tree", "-r", "-z", "--long", revision)
    tree = {}
    for record in raw_tree.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, oid, size = metadata.split()
        path = raw_path.decode("utf-8", errors="backslashreplace")
        tree[path] = (mode, object_type, oid, size, raw_path)
    if requested is not None:
        if any(path not in tree for path in requested):
            raise CodeFactsError("所选文件在指定提交中不存在；请核对提交和相对路径")
        selected = sorted(requested)
    else:
        selected = sorted(tree)
    if len(selected) > MAX_FILES:
        raise CodeFactsError("本次文件超过 2000 个，请通过 paths 缩小范围")
    files, skipped = [], []
    total_bytes = 0
    for path in selected:
        mode, object_type, oid, size, raw_path = tree[path]
        reason = None
        try:
            raw_path.decode("utf-8")
        except UnicodeError:
            reason = "文件名不是 UTF-8，首版不支持"
        if reason is None and (object_type != b"blob" or mode not in (b"100644", b"100755")):
            reason = "首版不读取符号链接或子模块"
        if reason is None and not path.endswith(".py"):
            reason = "首版仅支持 .py Python 文件"
        if reason is None and not size.isdigit():
            raise CodeFactsError("指定提交的对象在本地不可用，请先补全仓库；提取不会自动获取对象")
        if reason is None and int(size) > MAX_FILE_BYTES:
            reason = "文件超过首版 1 MiB 上限"
        if reason:
            skipped.append({"path": path, "reason": reason})
            continue
        total_bytes += int(size)
        if total_bytes > MAX_TOTAL_BYTES:
            raise CodeFactsError("本次 Python 内容超过 16 MiB，请缩小文件范围")
        raw = _git(root, "cat-file", "blob", oid.decode("ascii"))
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            syntax = ast.parse(source, filename=path)
        except (SyntaxError, UnicodeError, LookupError, ValueError, RecursionError):
            skipped.append({"path": path, "reason": "无法按当前 Python 解析器读取编码或语法"})
            continue
        files.append({"path": path, "language": "python", "entries": _definitions(syntax)})
    return {"revision": resolved, "files": files, "skipped": skipped}
