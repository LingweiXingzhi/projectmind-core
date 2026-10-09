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
    """Expected input or repository error, safe to show to a local user.

    `kind` is a stable machine-readable classification (终审 F5)：callers
    must branch on kind, never on message text. One of:
      "invalid_input"    — bad repo/path/paths argument
      "revision_invalid" — revision not a full commit SHA
      "budget"           — file-count or total-size budget exceeded
      "object_missing"   — a referenced Git object is not locally available
      "repo_unreadable"  — Git itself failed (transport/environment/unknown)
    """

    def __init__(self, message: str, kind: str = "repo_unreadable") -> None:
        super().__init__(message)
        self.kind = kind


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


def _object_missing(root: Path, oid: str) -> bool | None:
    """Structured existence probe (r30/r32 F5): ``git cat-file --batch-check``.

    Returns True only when git itself answered the structured record
    ``<oid> missing``; False when git answered a present-object record
    (``<oid> <type> <size>``); None whenever the answer is not a
    determinate structured response — spawn failure, timeout, non-zero
    exit (unreadable repo, config failure, e.g. exit 128) or malformed
    output. Inconclusive probes must never be the basis for
    object_missing classification; only the structured "missing"
    response counts, no message matching. The probe inherits the main
    reader's no-lazy-fetch / no-network configuration.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    # Same original-object configuration as the main reader (_git): replace
    # refs disabled, so the probe judges existence of the ORIGINAL object,
    # never a replacement (r33 F5 residual).
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1",
                "GIT_NO_REPLACE_OBJECTS": "1", "LC_ALL": "C"})
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "--no-pager", "-C", str(root),
             "cat-file", "--batch-check"],
            input=oid.encode("ascii") + b"\n",
            capture_output=True, timeout=10, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        # Command/config/repo-level failure (e.g. exit 128): indeterminate.
        return None
    record = result.stdout.split(b"\n", 1)[0].split()
    if len(record) == 2 and record[0].lower() == oid.encode("ascii") \
            and record[1] == b"missing":
        return True
    if len(record) == 3 and record[0].lower() == oid.encode("ascii") \
            and record[1] in (b"blob", b"tree", b"commit", b"tag") \
            and record[2].isdigit():
        return False
    return None


def repository_root(repo: Path | str) -> Path:
    try:
        root = Path(repo).expanduser().resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise CodeFactsError("仓库路径无效", kind="invalid_input") from exc
    if not root.is_dir():
        raise CodeFactsError("仓库路径必须是目录", kind="invalid_input")
    actual = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve()
    if actual != root:
        raise CodeFactsError("请提供 Git 仓库根目录，而非子目录", kind="invalid_input")
    return root


def current_revision(repo: Path | str) -> str:
    """For initial UI defaults only; extraction still requires an explicit full SHA."""
    root = repository_root(repo)
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()


def _paths(paths: list[str] | None) -> list[str] | None:
    if paths is None:
        return None
    if not isinstance(paths, list) or len(paths) > MAX_FILES:
        raise CodeFactsError("paths 必须是最多 2000 项的路径列表", kind="invalid_input")
    result = []
    for path in paths:
        if (
            not isinstance(path, str) or not path or "\\" in path
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or any(part in ("", ".", "..") for part in path.split("/"))
        ):
            raise CodeFactsError("路径须为仓库内相对文件路径，使用 /，不能含 .. 或控制字符",
                                 kind="invalid_input")
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


def read_source(repo: Path | str, revision: str, path: str) -> str:
    """Read and decode ONE committed blob at an explicit full commit SHA.

    The explorer's parser hand-off (task book §5: "输入 source 是调用方已
    解码的源码字符串；解码、Git 读取及大小限制由 A 负责") needs the decoded
    text of a single file at the pinned revision, and it needs exactly the
    same terminal failure classification the batch collector already
    guarantees (终审 F5): a ``cat-file`` failure is only reported as
    ``object_missing`` when the structured existence probe confirms the
    object is gone; every other cause (spawn failure, timeout, non-zero
    exit — e.g. exit 128) stays ``repo_unreadable``. Routing the read
    through the same ``_git`` / ``_object_missing`` pair keeps that
    classification single-sourced instead of re-deriving it per caller.

    Decoding honours PEP 263 via ``tokenize.detect_encoding`` exactly like
    the collector. The revision must be a full commit SHA.
    """
    if not isinstance(revision, str) or not SHA_PATTERN.fullmatch(revision):
        raise CodeFactsError("revision 必须是完整的 40 或 64 位小写 Git 提交 SHA",
                             kind="revision_invalid")
    root = repository_root(repo)
    resolved = _git(root, "rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
    if resolved != revision:
        raise CodeFactsError("revision 必须直接指向提交，不能是标签对象",
                             kind="revision_invalid")
    raw_tree = _git(root, "ls-tree", "-z", revision, "--", path)
    record = raw_tree.split(b"\0", 1)[0]
    if not record:
        raise CodeFactsError("所选文件在指定提交中不存在；请核对提交和相对路径",
                             kind="invalid_input")
    metadata, _raw_path = record.split(b"\t", 1)
    _mode, _object_type, oid = metadata.split()
    try:
        raw = _git(root, "cat-file", "blob", oid.decode("ascii"))
    except CodeFactsError:
        # r30 F5：cat-file 失败原因不唯一，只有独立存在性探针确证对象缺失
        # 时才归 object_missing，其余保持原始 repo_unreadable 分类。
        if _object_missing(root, oid.decode("ascii")) is True:
            raise CodeFactsError(
                "指定提交的对象在本地不可用，请先补全仓库；提取不会自动获取对象",
                kind="object_missing")
        raise
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
    except (SyntaxError, UnicodeError, LookupError, ValueError) as exc:
        raise CodeFactsError("无法按当前 Python 解析器读取该文件的编码",
                             kind="repo_unreadable") from exc


def collect_code_facts(repo: Path | str, revision: str, paths: list[str] | None = None) -> dict:
    """Return {revision, files, skipped}; paths=None selects all committed files.

    Only def/async def/class declarations are facts. Qualified names describe
    lexical nesting, not call relationships, runtime reachability or responsibility.
    Invalid inputs reject the request; unsupported/unparseable files are skipped.
    """
    if not isinstance(revision, str) or not SHA_PATTERN.fullmatch(revision):
        raise CodeFactsError("revision 必须是完整的 40 或 64 位小写 Git 提交 SHA",
                             kind="revision_invalid")
    requested = _paths(paths)
    root = repository_root(repo)
    resolved = _git(root, "rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
    if resolved != revision:
        raise CodeFactsError("revision 必须直接指向提交，不能是标签对象",
                             kind="revision_invalid")
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
            raise CodeFactsError("所选文件在指定提交中不存在；请核对提交和相对路径",
                                 kind="invalid_input")
        selected = sorted(requested)
    else:
        selected = sorted(tree)
    if len(selected) > MAX_FILES:
        raise CodeFactsError("本次文件超过 2000 个，请通过 paths 缩小范围", kind="budget")
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
            # ls-tree 对本地缺失的对象报 "-" 尺寸——真·对象缺失（终审 F5）。
            raise CodeFactsError("指定提交的对象在本地不可用，请先补全仓库；提取不会自动获取对象",
                                 kind="object_missing")
        if reason is None and int(size) > MAX_FILE_BYTES:
            reason = "文件超过首版 1 MiB 上限"
        if reason:
            skipped.append({"path": path, "reason": reason})
            continue
        total_bytes += int(size)
        if total_bytes > MAX_TOTAL_BYTES:
            raise CodeFactsError("本次 Python 内容超过 16 MiB，请缩小文件范围", kind="budget")
        try:
            raw = _git(root, "cat-file", "blob", oid.decode("ascii"))
        except CodeFactsError:
            # r30 F5 残留：cat-file 失败原因不唯一（超时、启动 OSError、
            # 一般非零退出都可能），一律按对象缺失会误分类。只有当独立
            # 存在性探针确证对象缺失时才归 object_missing；其余保持原始
            # repo_unreadable 分类（超时/启动失败/非零退出 → REPO_UNREADABLE）。
            if _object_missing(root, oid.decode("ascii")) is True:
                raise CodeFactsError(
                    "指定提交的对象在本地不可用，请先补全仓库；提取不会自动获取对象",
                    kind="object_missing")
            raise
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            syntax = ast.parse(source, filename=path)
        except (SyntaxError, UnicodeError, LookupError, ValueError, RecursionError):
            skipped.append({"path": path, "reason": "无法按当前 Python 解析器读取编码或语法"})
            continue
        files.append({"path": path, "language": "python", "entries": _definitions(syntax)})
    return {"revision": resolved, "files": files, "skipped": skipped}
