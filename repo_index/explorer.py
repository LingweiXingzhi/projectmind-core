"""Repo-explorer contexts: open a repository at one fixed commit and
serve its committed tree and file contents.

Contract highlights (accepted in the A-20261006-0007 design gate):
- one context binds (repo root realpath, full commit SHA) and the
  commit's tracked manifest; contents are read by manifest OID only;
- budgets run at open: 2000 indexed files, 1 MiB per blob, 16 MiB total;
  everything else stays visible in the tree with a skip reason;
- the registry is an LRU of 4 immutable contexts guarded by one lock;
  opens of the same (repo, SHA) are idempotent.
"""
from __future__ import annotations

import base64
import io
import posixpath
import re
import threading
import tokenize
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path

from repo_index import gitio
from extensions.code_facts.facts import CodeFactsError, read_source

# Task book §6.4/§6.5: a parser that was never delivered answers "unavailable"
# on its own endpoint. B and C arrive independently, so the two guards are
# separate — one missing parser must never disable the other — and only a
# genuinely absent module counts, never an internal failure inside a parser
# that IS installed (that must surface as an error, not as "not integrated").
try:
    from repo_index.imports import parse_imports
except ModuleNotFoundError as exc:
    if exc.name != "repo_index.imports":
        raise
    parse_imports = None

try:
    from repo_index.symbols import parse_symbols
except ModuleNotFoundError as exc:
    if exc.name != "repo_index.symbols":
        raise
    parse_symbols = None

SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
MAX_FILES = 2000
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 16_777_216
MAX_CONTEXTS = 4
MAX_LINES_PER_REQUEST = 500
BINARY_SNIFF_BYTES = 8192
PYTHON_SUFFIXES = (".py", ".pyi")

REASON_BINARY = "二进制内容，首版不提供源码视图"
REASON_OVERSIZE = "文件超过 1 MiB 上限"
REASON_NAME_ENCODING = "文件名不是 UTF-8，首版不支持"
REASON_SYMLINK = "符号链接，首版不读取"
REASON_SUBMODULE = "子模块，首版不读取"
REASON_SPECIAL_MODE = "首版不读取该类型的清单条目"
REASON_COUNT = "一次索引最多 2000 个文件"
REASON_TOTAL_BUDGET = "解析源码总量超限"
REASON_ENCODING = "编码不支持或解码失败"


class ExplorerError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RepoContext:
    project_id: str
    repo_root: Path
    revision: str
    entries: tuple[dict, ...]          # manifest records, tree order input
    manifest: dict[str, dict]          # utf-8 path -> record
    allowed: frozenset[str]
    skipped: tuple[dict[str, str], ...]
    sources: dict[str, str]            # allowed path -> decoded source
    coverage: dict = field(default_factory=dict)


def _resolve_revision(repo_root: Path, revision: str) -> str:
    if revision != "HEAD" and not SHA_PATTERN.fullmatch(revision):
        raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                            "revision 仅接受 HEAD 或完整 40/64 位提交 SHA")
    try:
        raw = gitio.git(repo_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    except gitio.GitIoError as exc:
        raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                            "revision 无法解析为提交") from exc
    resolved = raw.decode("ascii", errors="replace").strip()
    if revision != "HEAD" and resolved != revision:
        raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                            "revision 必须直接指向提交")
    return resolved


def _read_manifest(repo_root: Path, revision: str) -> list[dict]:
    try:
        raw = gitio.git(repo_root, "ls-tree", "-r", "-z", "--long", revision)
    except gitio.GitIoError as exc:
        raise ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "REPO_UNREADABLE",
                            "无法读取指定提交的清单") from exc
    entries: list[dict] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, oid, size_raw = metadata.split()
        # Git reports "-" as the size for non-blob entries (gitlinks); parse
        # sizes only where they exist and classify before any arithmetic.
        size = None if size_raw == b"-" else int(size_raw)
        try:
            path = raw_path.decode("utf-8")
            identity = None
        except UnicodeError:
            path = None
            identity = _undecodable_identity(raw_path)
        entries.append({
            "path": path,
            "raw_path": raw_path,
            "identity": identity,
            "mode": mode,
            "object_type": object_type,
            "oid": oid.decode("ascii"),
            "size": size,
        })
    return entries


class _Unreadable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _decode_source(raw: bytes, path: str) -> str:
    """Decode one blob for browsing.

    A PEP 263 coding cookie describes **Python source**, so it is only
    consulted for `.py`/`.pyi`. Every other browsable text file is UTF-8: a
    plain text file whose first line merely looks like a cookie must stay
    browsable instead of being skipped as an encoding failure (R48-08).
    """
    if b"\0" in raw[:BINARY_SNIFF_BYTES]:
        raise _Unreadable(REASON_BINARY)
    if not path.lower().endswith(PYTHON_SUFFIXES):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _Unreadable(REASON_ENCODING) from exc
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
    except (SyntaxError, UnicodeError, LookupError, ValueError) as exc:
        # tokenize.detect_encoding raises SyntaxError for unknown or
        # contradictory encoding declarations (B1-a-02).
        raise _Unreadable(REASON_ENCODING) from exc


def _split_source_lines(source: str) -> list[str]:
    """Split on physical line terminators only (\\r\\n, \\r, \\n).

    str.splitlines would also break at U+2028/U+2025-style characters and
    desynchronize file lines from Python AST line numbers (B1-a-05).
    """
    if source == "":
        return []
    lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", source)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _classify_and_read(repo_root: Path, entries: list[dict]) -> tuple[dict[str, dict], tuple[dict[str, str], ...], dict[str, str]]:
    """Classify every tracked file; read blobs only within the budget.

    Fixed order: per-file 1 MiB cap first, then stable path order for
    the cumulative 16 MiB parse budget and the 2000-file cap; binary
    content and encoding failures surface as explicit skip reasons.
    """
    manifest: dict[str, dict] = {}
    skipped: list[dict[str, str]] = []
    candidates: list[tuple[str, dict]] = []
    for entry in entries:
        if entry["path"] is None:
            # 终审 F4：非法 UTF-8 名以 base64 身份进 skipped/树，display 文本
            # 仅作展示——不同原始字节路径永不合并，也不会与合法路径同名碰撞。
            display = entry["raw_path"].decode("utf-8", "backslashreplace")
            skipped.append({"path": display,
                            "pathIdentity": entry["identity"],
                            "pathUndecodable": True,
                            "reason": REASON_NAME_ENCODING})
            continue
        manifest[entry["path"]] = entry
        if entry["object_type"] == b"commit" or entry["mode"] == b"160000":
            skipped.append({"path": entry["path"], "reason": REASON_SUBMODULE})
            continue
        if entry["mode"] == b"120000":
            skipped.append({"path": entry["path"], "reason": REASON_SYMLINK})
            continue
        if entry["object_type"] != b"blob" or entry["mode"] not in (b"100644", b"100755"):
            skipped.append({"path": entry["path"], "reason": REASON_SPECIAL_MODE})
            continue
        if entry["size"] is None:
            skipped.append({"path": entry["path"], "reason": REASON_SPECIAL_MODE})
            continue
        if entry["size"] > MAX_FILE_BYTES:
            skipped.append({"path": entry["path"], "reason": REASON_OVERSIZE})
            continue
        candidates.append((entry["path"], entry))

    sources: dict[str, str] = {}
    indexed = 0
    total_bytes = 0
    for path, entry in sorted(candidates, key=lambda item: item[0]):
        if indexed >= MAX_FILES:
            skipped.append({"path": path, "reason": REASON_COUNT})
            continue
        if total_bytes + entry["size"] > MAX_TOTAL_BYTES:
            skipped.append({"path": path, "reason": REASON_TOTAL_BUDGET})
            continue
        try:
            raw = gitio.git(repo_root, "cat-file", "blob", entry["oid"])
        except gitio.GitIoError as exc:
            raise ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "OBJECT_MISSING",
                                "指定提交的对象在本地不可用") from exc
        total_bytes += len(raw)
        indexed += 1
        try:
            sources[path] = _decode_source(raw, path)
        except _Unreadable as exc:
            skipped.append({"path": path, "reason": exc.reason})
    return manifest, tuple(skipped), sources


def _decode_git_path(token: bytes) -> tuple[str, bool]:
    """Decode a raw Git path, preserving identity for non-UTF-8 names.

    backslashreplace yields a distinct string per distinct byte sequence, so
    two different invalid names can never collapse into one addressable path
    (B3B5-07); the undecodable flag lets callers refuse to open them.
    """
    try:
        return token.decode("utf-8"), False
    except UnicodeError:
        return token.decode("utf-8", "backslashreplace"), True


def _undecodable_identity(raw_path: bytes) -> str:
    """Collision-free identity for a non-UTF-8 Git path (终审 F4).

    The backslashreplace display text could coincide with a *legal* file
    name that literally contains those characters, so the identity carried
    by the API prefixes the base64 of the original bytes with NUL — Git
    paths can never contain NUL, so no legal path can ever equal an
    undecodable identity (r25: plain "b64:" was still forgeable).
    """
    return "\x00b64:" + base64.b64encode(raw_path).decode("ascii")


def _dir_link(prefix_raw: bytes) -> str:
    """Link identity for the directory at `prefix_raw` (终审 F4, r25).

    The identity belongs to the directory prefix itself, independent of
    whether any particular child path is decodable: a decodable prefix is
    its own plain text (UTF-8 decoding is injective, so two different legal
    prefixes never merge); an undecodable prefix gets the NUL-prefixed
    base64 form that no legal path can reproduce.
    """
    try:
        return prefix_raw.decode("utf-8")
    except UnicodeError:
        return _undecodable_identity(prefix_raw)


def parse_name_status(raw: bytes) -> list[dict]:
    """Parse `git diff --name-status -z -M` output with machine identity.

    终审 F4（changes 侧）：展示文本（path/oldPath）与机器身份（identity/
    oldIdentity/newIdentity）分离。身份由 raw Git path bytes 派生，且与
    tree 使用同一底层 helper `_dir_link`——不得另造不兼容编码：
    - 可解码路径：身份就是其自身明文（UTF-8 解码单射，两个合法路径永不合并）；
    - 不可解码路径：NUL 前缀 base64 身份（Git 路径不含 NUL，任何合法
      路径都无法复现，backslashreplace 展示文本也无法伪造）。
    因此两个不同 raw byte path 即使展示文本完全相同，身份也必然不同，
    entry 不会被覆盖、折叠或去重；rename 两侧身份分别记录。
    """
    parts = [part for part in raw.split(b"\0") if part]
    changes: list[dict] = []
    index = 0
    while index < len(parts):
        code = parts[index]
        index += 1
        if code.startswith((b"R", b"C")):
            old_raw, new_raw = parts[index], parts[index + 1]
            index += 2
            # _decode_git_path's second element IS the "undecodable" flag
            # (False = decoded fine); never double-negate it.
            old_path, old_broken = _decode_git_path(old_raw)
            path, path_broken = _decode_git_path(new_raw)
            entry = {
                "status": code[:1].decode("ascii"),
                # path/identity 是 rename 的新侧；newPath/newIdentity 与之
                # 同值，让 rename 记录按专项复核要求自描述两侧身份。
                "path": path,
                "identity": _dir_link(new_raw),
                "newPath": path,
                "newIdentity": _dir_link(new_raw),
                "oldPath": old_path,
                "oldIdentity": _dir_link(old_raw),
            }
            undecodable = old_broken or path_broken
        else:
            raw_path = parts[index]
            index += 1
            path, path_broken = _decode_git_path(raw_path)
            entry = {
                "status": code.decode("ascii"),
                "path": path,
                "identity": _dir_link(raw_path),
                "oldPath": None,
            }
            undecodable = path_broken
        if undecodable:
            entry["pathUndecodable"] = True
        changes.append(entry)
    return changes


def _module_index(known: frozenset[str]) -> dict[tuple[str, str], list[str]]:
    """(module path, casefolded extension) -> EVERY real repository path.

    Only the extension is case-normalised, so `helper.PY` is a Python module
    while `Helper.py` is still a different module from `helper.py` — the same
    rule the parsers apply to file types (R48-03). Several real paths can share
    one key (`helper.py` and `helper.PY`); all of them are kept and the caller
    gets them sorted, so the outcome never depends on set/hash iteration order
    (R49-03) and several candidates are reported as ambiguous rather than
    silently reduced to whichever happened to be inserted first.
    """
    index: dict[tuple[str, str], list[str]] = {}
    for path in known:
        name = path.rsplit("/", 1)[-1]
        dot = name.rfind(".")
        if dot <= 0:
            continue
        index.setdefault((path[: len(path) - len(name)] + name[:dot],
                          name[dot + 1:].casefold()), []).append(path)
    return index


def _directories(known: frozenset[str]) -> frozenset[str]:
    found: set[str] = set()
    for path in known:
        parts = path.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            found.add("/".join(parts[:index]))
    return frozenset(found)


def _is_package(directory: str, index: dict) -> bool:
    return ((f"{directory}/__init__", "py") in index
            or (f"{directory}/__init__", "pyi") in index)


def _package_context(source_path: str, index: dict) -> tuple[str, list[str]]:
    """`(search root, package components)` for a file (r04 R3-Q1).

    The search root is the deepest ancestor directory of the file that is not
    itself a package; the package components are the package chain below it, so
    the package name is the dotted path from the search root down to the file's
    own directory and the depth `d` is its length:

    - `src/core/mod.py` -> search root `src`, package `core`, d = 1
    - `src/consumer.py` -> search root `src`, package "", d = 0 (directly under
      a search root: no package context, but the search root still governs its
      ABSOLUTE imports)
    - `pkg/ns/inner.py` where `pkg/ns` has no `__init__.py` -> search root
      `pkg/ns`, package "", d = 0 (the PEP 420 namespace shape)
    - `service.py` at the repository root -> search root "", package "", d = 0

    `d == 0` means every RELATIVE import is unresolved; it does not mean the
    file has no search root.
    """
    directory = posixpath.dirname(source_path)
    parts = directory.split("/") if directory else []
    depth = len(parts)
    while depth > 0 and _is_package("/".join(parts[:depth]), index):
        depth -= 1
    return "/".join(parts[:depth]), parts[depth:]


def _module_matches(prefix: str, index: dict) -> list[str]:
    """Concrete source blobs for one module path (R2-Q7: x.py or x/__init__.py)."""
    found: list[str] = []
    for key in ((prefix, "py"), (prefix, "pyi"),
                (f"{prefix}/__init__", "py"), (f"{prefix}/__init__", "pyi")):
        for path in index.get(key, ()):
            if path not in found:
                found.append(path)
    return found


def _import_prefixes(entry: dict, source_path: str, index: dict
                     ) -> tuple[list[str], list[str], bool, str | None]:
    """Module paths this record can denote, or (·, ·, ·, rejection reason).

    Returns `(name prefixes, module prefixes, has_name, reason)`: the name
    prefixes describe the `M/name` submodule reading, the module prefixes
    describe the module `M` itself, and `has_name` is True only for a
    `from M import name` record (a plain import or a wildcard has no name
    reading and may resolve straight to a package `__init__`).

    Accepted rule (r04 R3-Q1): a relative import needs `1 <= level <= d` where
    d is the package depth measured from the file's search root, and the base
    is the package moved up `level - 1` components. `level > d` never matches,
    even when a file with that name happens to exist at the search root or the
    repository root. Absolute imports are tried against the repository root
    and the file's own search root (R2-Q7), never across another search root.

    The name part wins when it names a real submodule; otherwise the module's
    own source blobs are what the statement depends on (r03 R2-Q7: "只有候选
    文件真实存在才连接… 歧义（同名文件与同名包并存）保留 ambiguous"). The one
    case that must stay unresolved is a module whose only source blob is a
    package `__init__` — `from pkg import name` may then be an attribute or
    re-export defined there, and the first version does no cross-file
    inference. `has_name` marks that distinction for the caller.
    """
    level = entry.get("level") or 0
    module_rest = (entry.get("module") or "").replace(".", "/")
    name = entry.get("name")
    search_root, package_parts = _package_context(source_path, index)
    if level:
        if not package_parts:
            return [], [], False, "文件不在包内，相对导入没有包语境"
        if level > len(package_parts):
            return [], [], False, (f"相对导入越出顶层包（level={level} > 包深度 {len(package_parts)}）")
        base = "/".join(part for part in
                        (search_root,
                         "/".join(package_parts[:len(package_parts) - (level - 1)])) if part)
        roots = [base]
    else:
        # Absolute imports are looked up from the repository root and from the
        # file's own search root (r03 R2-Q7), never across another search root.
        roots = [""] + ([search_root] if search_root else [])
    module_prefixes = [target for target in
                       ("/".join(part for part in (root, module_rest) if part) for root in roots)
                       if target]
    if entry.get("kind") == "import" or not name or name == "*":
        return module_prefixes, module_prefixes, False, None
    return ([f"{prefix}/{name}" for prefix in module_prefixes], module_prefixes, True, None)


def _unique_or_ambiguous(candidates: list[str]) -> dict:
    if len(candidates) == 1:
        return {"status": "resolved", "targetPath": candidates[0],
                "candidates": candidates}
    return {"status": "ambiguous", "targetPath": None, "candidates": candidates}


def _import_decision(entry: dict, source_path: str, index: dict,
                     directories: frozenset[str]) -> tuple[dict, str | None]:
    """`(resolution, reason)` for one C import record.

    Accepted rule (r03 R2-Q7, exercised by D's independent fixture oracle):

    1. the name reading wins when `M/name` names real source blobs;
    2. otherwise the module `M` is the dependency: a single plain module file
       resolves, two candidates (`M.py` and `M/__init__.py` both existing) stay
       `ambiguous` with both listed, and nothing found is `unresolved`;
    3. a module whose ONLY source blob is a package `__init__` is the one case
       that cannot confirm `name` at all — `from pkg import name` may be an
       attribute or re-export defined there, so it is `unresolved` and never a
       target (no cross-file inference);
    4. a module path that names a directory without `__init__.py` is the
       PEP 420 namespace-package shape: unresolved, with that stated reason.
    """
    name_prefixes, module_prefixes, has_name, rejected = _import_prefixes(
        entry, source_path, index)
    if rejected is not None:
        return {"status": "unresolved", "targetPath": None, "candidates": []}, rejected
    named = sorted({path for prefix in name_prefixes
                    for path in _module_matches(prefix, index)})
    if named:
        return _unique_or_ambiguous(named), None
    # The name could not be found. A NAME path that is a directory without
    # `__init__.py` is the PEP 420 namespace shape and explains the gap
    # (R2-Q7). This is tested on the name prefix only: the module fallback
    # below still applies when a real `helper.py` sits next to a nameless
    # `helper/` directory, so that directory can never mask the real candidate
    # (R49-04).
    for prefix in name_prefixes:
        if prefix in directories and not _is_package(prefix, index):
            return ({"status": "unresolved", "targetPath": None, "candidates": []},
                    "可能的命名空间包，无源码入口")
    modules = sorted({path for prefix in module_prefixes
                      for path in _module_matches(prefix, index)})
    if not modules:
        return {"status": "unresolved", "targetPath": None, "candidates": []}, "未找到候选源码文件"
    if len(modules) > 1:
        return {"status": "ambiguous", "targetPath": None, "candidates": modules}, None
    if has_name and posixpath.basename(modules[0]).startswith("__init__."):
        return ({"status": "unresolved", "targetPath": None, "candidates": []},
                "可能是包属性或重导出")
    return {"status": "resolved", "targetPath": modules[0], "candidates": modules}, None


def _import_resolution(entry: dict, source_path: str, index: dict,
                       directories: frozenset[str]) -> dict:
    return _import_decision(entry, source_path, index, directories)[0]


class ExplorerRegistry:
    """Thread-safe LRU of opened repo contexts (capacity 4)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_key: "OrderedDict[tuple[str, str], RepoContext]" = OrderedDict()
        self._by_id: dict[str, RepoContext] = {}

    # -- open ---------------------------------------------------------------
    def open(self, repo_path: str, revision: str = "HEAD") -> dict:
        given = Path(repo_path)
        # The task contract takes a local ABSOLUTE path; a relative or empty
        # value would otherwise resolve against the server's cwd and open
        # some unintended repository.
        if not given.is_absolute():
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REPO_INVALID",
                                "repoPath 必须是本机仓库的绝对路径")
        try:
            repo_root = gitio.repository_root(given)
        except gitio.GitIoError as exc:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REPO_INVALID", str(exc)) from exc
        with self._lock:
            sha = _resolve_revision(repo_root, revision)
            key = (str(repo_root), sha)
            context = self._by_key.get(key)
            if context is not None:
                self._by_key.move_to_end(key)
                return self._open_response(context)
            context = self._build_context(repo_root, sha)
            self._store(context)
            return self._open_response(context)

    def _store(self, context: RepoContext) -> None:
        while len(self._by_key) >= MAX_CONTEXTS:
            _, evicted = self._by_key.popitem(last=False)
            self._by_id.pop(evicted.project_id, None)
        self._by_key[(str(context.repo_root), context.revision)] = context
        self._by_id[context.project_id] = context

    def _build_context(self, repo_root: Path, sha: str) -> RepoContext:
        entries = _read_manifest(repo_root, sha)
        manifest, skipped, sources = _classify_and_read(repo_root, entries)
        allowed = frozenset(sources)
        coverage = {
            "trackedFileCount": sum(
                1 for entry in manifest.values()
                if entry["object_type"] == b"blob" and entry["mode"] in (b"100644", b"100755")
            ),
            "indexedFileCount": len(allowed),
            "skipped": list(skipped),
            "partial": bool(skipped),
        }
        return RepoContext(
            project_id=uuid.uuid4().hex,
            repo_root=repo_root,
            revision=sha,
            entries=tuple(entries),
            manifest=manifest,
            allowed=allowed,
            skipped=skipped,
            sources=sources,
            coverage=coverage,
        )

    def _open_response(self, context: RepoContext) -> dict:
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "repositoryName": context.repo_root.name,
            "revision": context.revision,
            # r02 Q6: capabilities express what this deployment can actually
            # do. A parser that was never delivered is reported as unavailable
            # here too, so `open` can never advertise an ability its own
            # endpoint then refuses (R49-02).
            "capabilities": {"files": True,
                             "symbols": parse_symbols is not None,
                             "imports": parse_imports is not None,
                             "changes": True},
            "coverage": context.coverage,
        }

    # -- lookup (tree/file slices build on this) ----------------------------
    def _get_by_id(self, project_id: str) -> RepoContext:
        with self._lock:
            context = self._by_id.get(project_id)
            if context is None:
                raise ExplorerError(HTTPStatus.GONE, "CONTEXT_EVICTED",
                                    "上下文不存在或已被淘汰，请重新 open")
            self._by_key.move_to_end((str(context.repo_root), context.revision))
            return context

    def get(self, project_id: str, revision: str) -> RepoContext:
        context = self._get_by_id(project_id)
        if revision != context.revision:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_MISMATCH",
                                "revision 与该 projectId 绑定的提交不一致")
        return context

    # -- file -----------------------------------------------------------------
    def file(self, project_id: str, revision: str, path: str,
             start_line: int, end_line: int) -> dict:
        context = self.get(project_id, revision)
        self._validate_path(path)
        if path not in context.manifest:
            raise ExplorerError(HTTPStatus.NOT_FOUND, "PATH_NOT_IN_REVISION",
                                "路径不在该提交的清单中")
        if path not in context.allowed:
            reason = next((item["reason"] for item in context.skipped
                           if item["path"] == path), "该文件在本次索引中被跳过")
            raise ExplorerError(HTTPStatus.FORBIDDEN, "FILE_SKIPPED", reason)
        lines = _split_source_lines(context.sources[path])
        total_lines = len(lines)
        # 参数校验先于空文件提前返回（终审 F3）：空文件同样不得绕过
        # startLine/endLine 的合法性检查。
        if start_line < 1 or end_line < start_line:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "LINE_RANGE_INVALID",
                                "行号范围无效")
        if end_line - start_line + 1 > MAX_LINES_PER_REQUEST:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "LINE_RANGE_TOO_LARGE",
                                f"单次最多返回 {MAX_LINES_PER_REQUEST} 行")
        if total_lines == 0:
            return self._file_response(context, path, 0, 0, 0, "", False)
        if start_line > total_lines:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "LINE_RANGE_INVALID",
                                "行号范围无效")
        clipped_end = min(end_line, total_lines)
        content = "".join(lines[start_line - 1:clipped_end])
        returned = clipped_end - start_line + 1
        # Accepted Q5 definition: true while any line of the file remains
        # unreturned by this response — including lines before the window
        # (B1-a-04).
        return self._file_response(context, path, start_line, clipped_end,
                                   total_lines, content, returned < total_lines)

    @staticmethod
    def _file_response(context: RepoContext, path: str, start_line: int, end_line: int,
                       total_lines: int, content: str, truncated: bool) -> dict:
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "path": path,
            "startLine": start_line,
            "endLine": end_line,
            "totalLines": total_lines,
            "content": content,
            "truncated": truncated,
        }

    @staticmethod
    def _validate_path(path: str) -> None:
        invalid = (
            not isinstance(path, str) or not path
            or ":" in path or "\\" in path or path.startswith("/")
            or any(ord(char) < 32 or ord(char) == 127 for char in path)
            or any(segment in ("", ".", "..") for segment in path.split("/"))
        )
        if invalid:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "PATH_INVALID",
                                "路径须为仓库内相对文件路径，使用 /，不能含 .. 或控制字符")

    # -- relations ------------------------------------------------------------
    def relations(self, project_id: str, revision: str, path: str) -> dict:
        """Import relations via C's `parse_imports` (task book §6.5).

        `imports` keeps C's original fields and adds A's own
        `resolution{status, targetPath, candidates}`; a unique resolved target
        is the only case that fills `targetPath`. `dependents` lists
        `{path, line, end_line}` from other files whose imports resolve to
        this one — a resolved record only, so an uncertain reverse edge is
        never shown as a confirmed dependency. Parsing failures keep
        `parse_error` and are never wrapped as a successful empty result; when
        some files in the scanned range could not be parsed, a warning says
        so (部分解析覆盖时界面注明"已解析范围内未发现").
        """
        context = self.get(project_id, revision)
        self._validate_path(path)
        if path not in context.manifest:
            raise ExplorerError(HTTPStatus.NOT_FOUND, "PATH_NOT_IN_REVISION",
                                "路径不在该提交的清单中")
        if path not in context.allowed:
            reason = next((item["reason"] for item in context.skipped
                           if item["path"] == path), "该文件在本次索引中被跳过")
            raise ExplorerError(HTTPStatus.FORBIDDEN, "FILE_SKIPPED", reason)
        if parse_imports is None:
            # §6.5: no import parser integrated -> status "unavailable", never a
            # wrapped empty success.
            return {
                "schemaVersion": 1,
                "projectId": context.project_id,
                "revision": context.revision,
                "path": path,
                "status": "unavailable",
                "imports": [],
                "dependents": [],
                "importScan": None,
                "warnings": ["静态导入解析器尚未接入；目录与源码浏览不受影响"],
            }
        # The scan range must equal the parsers' own supported range, so the
        # extension test is case-insensitive: `consumer.PY` is a Python file to
        # parse_imports and must therefore also be scanned for dependents
        # (R48-03, R2-Q8 "仅 .py 且在 allowed 集合的文件计入分母").
        known = frozenset(item for item in context.allowed
                          if item.lower().endswith((".py", ".pyi")))
        index = _module_index(known)
        directories = _directories(known)
        parsed = parse_imports(path, context.sources[path])
        imports = []
        warnings = list(parsed["warnings"])
        for entry in parsed["imports"]:
            resolution, reason = _import_decision(entry, path, index, directories)
            imports.append(dict(entry, resolution=resolution))
            if reason is not None:
                warnings.append(f"{path} 第 {entry['line']} 行未解析：{reason}")
        dependents: list[dict] = []
        scanned = 0
        failed = 0
        for other in sorted(known):
            other_parsed = parsed if other == path else parse_imports(other, context.sources[other])
            if other_parsed["status"] != "ok":
                failed += 1
                continue
            scanned += 1
            if other == path:
                continue
            for entry in other_parsed["imports"]:
                resolution = _import_resolution(entry, other, index, directories)
                if resolution["status"] == "resolved" and resolution["targetPath"] == path:
                    dependents.append({"path": other, "line": entry["line"],
                                       "end_line": entry["end_line"]})
        # R2-Q8: the response states its own scan coverage, and any gap is
        # reported instead of being shown as a complete scan. "Not scanned"
        # files are the manifest's Python files that the open budget skipped.
        unscanned = sum(1 for item in context.manifest
                        if item.lower().endswith((".py", ".pyi"))
                        and item not in context.allowed)
        # R49-06: the warning states the COVERAGE GAP only. Whether the
        # (possibly empty) dependents list means "nothing found" is decided by
        # the reader — the UI says "已解析范围内未发现导入本文件的记录" only when
        # the list really is empty, so a non-empty list is never contradicted by
        # the warning text here.
        if failed:
            warnings.append(f"{failed} 个文件解析失败；dependents 仅为已解析范围内的结果")
        if unscanned:
            warnings.append(f"{unscanned} 个 Python 文件未被 open 纳入内容索引"
                            "（预算、编码或类型跳过），dependents 覆盖不完整，"
                            "不得视为完整扫描结论")
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "path": path,
            "status": parsed["status"],
            "imports": imports,
            "dependents": dependents,
            "importScan": {"scanned": scanned, "parseFailed": failed, "total": len(known)},
            "warnings": warnings,
        }

    # -- changes --------------------------------------------------------------
    def changes(self, project_id: str, base: str, target: str) -> dict:
        """File changes between two full commit SHAs of this project's repo
        (task book §6.6): raw Git name-status letters with rename detection;
        nothing silently dropped. The task-book signature carries projectId,
        base and target only — no revision parameter.

        终审 F4：每个 entry 携带 machine identity（identity，rename 另有
        oldIdentity/newIdentity），由 raw Git path bytes 派生并与 tree 的
        身份规则同一 helper——展示文本相同的碰撞 entry 依赖身份保持独立。
        """
        context = self._get_by_id(project_id)
        base_sha = self._resolve_pinned_commit(context.repo_root, base, "base")
        target_sha = self._resolve_pinned_commit(context.repo_root, target, "target")
        try:
            raw = gitio.git(context.repo_root, "diff", "--name-status", "-z", "-M",
                            base_sha, target_sha, "--")
        except gitio.GitIoError as exc:
            raise ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "REPO_UNREADABLE",
                                "无法读取指定提交之间的差异") from exc
        changes = parse_name_status(raw)
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "baseRevision": base_sha,
            "targetRevision": target_sha,
            "changes": changes,
        }

    @staticmethod
    def _resolve_pinned_commit(repo_root: Path, value: str, field: str) -> str:
        if not isinstance(value, str) or not SHA_PATTERN.fullmatch(value):
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                                f"{field} 必须是完整的 40/64 位提交 SHA")
        try:
            resolved = gitio.git(repo_root, "rev-parse", "--verify",
                                 f"{value}^{{commit}}").decode("ascii", errors="replace").strip()
        except gitio.GitIoError as exc:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                                f"{field} 无法解析为该仓库中的提交") from exc
        if resolved != value:
            raise ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID",
                                f"{field} 必须直接指向提交")
        return resolved

    # -- symbols --------------------------------------------------------------
    def symbols(self, project_id: str, revision: str, path: str) -> dict:
        """Full symbols via B's `parse_symbols` (task book §6.4/§5):
        `parser="python_ast_v1"` with inclusive end_line and cleaned
        docstrings, replacing the legacy code-facts transition (whose null
        end_line / range-incomplete warning is withdrawn).

        The source is read at the context's pinned revision through A's
        hardened Git layer; the terminal failure classification is the
        collector's own (终审 F5), so an unavailable object still answers
        OBJECT_MISSING and any other Git failure REPO_UNREADABLE. Admission
        is shared with `file` (404 / 403 FILE_SKIPPED) and never fabricates
        an empty success for a parse failure.
        """
        context = self.get(project_id, revision)
        self._validate_path(path)
        if path not in context.manifest:
            raise ExplorerError(HTTPStatus.NOT_FOUND, "PATH_NOT_IN_REVISION",
                                "路径不在该提交的清单中")
        if path not in context.allowed:
            reason = next((item["reason"] for item in context.skipped
                           if item["path"] == path), "该文件在本次索引中被跳过")
            raise ExplorerError(HTTPStatus.FORBIDDEN, "FILE_SKIPPED", reason)
        if parse_symbols is None:
            # §6.4: with no parser integrated the endpoint says so explicitly
            # instead of wrapping an empty result as success.
            return {
                "schemaVersion": 1,
                "projectId": context.project_id,
                "revision": context.revision,
                "path": path,
                "status": "unavailable",
                "symbols": [],
                "warnings": ["符号解析器尚未接入；目录与源码浏览不受影响"],
                "parser": None,
            }
        if path.lower().endswith(PYTHON_SUFFIXES):
            # Only Python sources are read through the PEP 263 reader; a
            # browsable text file whose first line looks like a coding cookie
            # must still answer `unsupported`, not a 500 decoding failure
            # (R48-08). The snapshot source is taken at the pinned revision
            # either way.
            try:
                source = read_source(context.repo_root, context.revision, path)
            except CodeFactsError as exc:
                raise self._code_facts_error(exc) from exc
        else:
            source = context.sources[path]
        result = parse_symbols(path, source)
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "path": path,
            "status": result["status"],
            "symbols": result["symbols"],
            "warnings": result["warnings"],
            "parser": "python_ast_v1",
        }

    @staticmethod
    def _code_facts_error(exc: CodeFactsError) -> ExplorerError:
        """终审 F5：按 CodeFactsError.kind 这一稳定机器可读分类映射，
        不做任何自然语言关键词猜测。invalid_input / repo_unreadable 及
        未知 kind 一律落 REPO_UNREADABLE（与既有兜底行为一致）。"""
        mapping = {
            "revision_invalid": (HTTPStatus.BAD_REQUEST, "REVISION_INVALID"),
            "budget": (HTTPStatus.BAD_REQUEST, "BUDGET_EXCEEDED"),
            "object_missing": (HTTPStatus.INTERNAL_SERVER_ERROR, "OBJECT_MISSING"),
        }
        status, code = mapping.get(getattr(exc, "kind", None),
                                   (HTTPStatus.INTERNAL_SERVER_ERROR, "REPO_UNREADABLE"))
        return ExplorerError(status, code, str(exc))

    # -- tree ----------------------------------------------------------------
    def tree(self, project_id: str, revision: str) -> dict:
        context = self.get(project_id, revision)
        directories: dict[str, dict] = {}   # link identity -> entry
        files: list[dict] = []
        for record in context.entries:
            undecodable = record["path"] is None
            if undecodable:
                # 终审 F4（r24 残留）：不可解码路径与其祖先目录的链接值一律
                # 用 base64 身份——两个不同原始字节目录的展示文本可能相同，
                # 按展示文本去重会把两组合并进同一节点。展示文本另存
                # displayPath；合法路径的链接值就是其自身明文。
                raw = record["raw_path"]
                raw_segments = raw.split(b"/")
                link = record["identity"]
                display = raw.decode("utf-8", "backslashreplace")
                parent_link = ""
                for index in range(1, len(raw_segments)):
                    prefix_raw = b"/".join(raw_segments[:index])
                    dir_link = _dir_link(prefix_raw)
                    if dir_link not in directories:
                        dir_display = prefix_raw.decode("utf-8", "backslashreplace")
                        dir_entry = {
                            "path": dir_link,
                            "displayPath": dir_display,
                            "parentPath": parent_link,
                            "kind": "directory",
                            "language": None,
                        }
                        if dir_link != dir_display:
                            # decodable prefixes are their own plain text, so
                            # link == display marks a legal dir name
                            dir_entry["pathUndecodable"] = True
                        directories[dir_link] = dir_entry
                    parent_link = dir_link
                entry = {
                    "path": link,
                    "displayPath": display,
                    "parentPath": parent_link,
                    "kind": "file",
                    "language": "python" if display.endswith((".py", ".pyi")) else None,
                    "pathUndecodable": True,
                    "pathIdentity": record["identity"],
                    "skippedReason": next(
                        (item["reason"] for item in context.skipped
                         if item.get("pathIdentity") == record["identity"]),
                        REASON_NAME_ENCODING),
                }
            else:
                path = record["path"]
                segments = path.split("/")
                for index in range(1, len(segments)):
                    dir_path = "/".join(segments[:index])
                    if dir_path not in directories:
                        directories[dir_path] = {
                            "path": dir_path,
                            "parentPath": "" if index == 1 else "/".join(segments[:index - 1]),
                            "kind": "directory",
                            "language": None,
                        }
                entry = {
                    "path": path,
                    "parentPath": "" if len(segments) == 1 else "/".join(segments[:-1]),
                    "kind": "file",
                    "language": "python" if path.endswith((".py", ".pyi")) else None,
                }
                if path not in context.allowed:
                    reason = next((item["reason"] for item in context.skipped
                                   if item["path"] == path), None)
                    if reason is not None:
                        entry["skippedReason"] = reason
            files.append(entry)
        entries = sorted(files + list(directories.values()), key=lambda item: item["path"])
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "entries": entries,
            "coverage": context.coverage,
        }
