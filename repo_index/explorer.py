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
import re
import threading
import tokenize
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path

from repo_index import gitio
from extensions.code_facts.facts import CodeFactsError, collect_code_facts

SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")
MAX_FILES = 2000
MAX_FILE_BYTES = 1_048_576
MAX_TOTAL_BYTES = 16_777_216
MAX_CONTEXTS = 4
MAX_LINES_PER_REQUEST = 500
BINARY_SNIFF_BYTES = 8192

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


def _decode_source(raw: bytes) -> str:
    if b"\0" in raw[:BINARY_SNIFF_BYTES]:
        raise _Unreadable(REASON_BINARY)
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
            sources[path] = _decode_source(raw)
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
    by the API is the base64 of the original bytes — two different raw byte
    paths always map to two different identities, and the Git original is
    preserved rather than a re-escaped display string.
    """
    return "b64:" + base64.b64encode(raw_path).decode("ascii")


def parse_name_status(raw: bytes) -> list[dict]:
    parts = [part for part in raw.split(b"\0") if part]
    changes: list[dict] = []
    index = 0
    while index < len(parts):
        code = parts[index]
        index += 1
        if code.startswith((b"R", b"C")):
            # _decode_git_path's second element IS the "undecodable" flag
            # (False = decoded fine); never double-negate it.
            old_path, old_broken = _decode_git_path(parts[index])
            path, path_broken = _decode_git_path(parts[index + 1])
            index += 2
            entry = {"status": code[:1].decode("ascii"), "path": path, "oldPath": old_path}
            undecodable = old_broken or path_broken
        else:
            path, path_broken = _decode_git_path(parts[index])
            index += 1
            entry = {"status": code.decode("ascii"), "path": path, "oldPath": None}
            undecodable = path_broken
        if undecodable:
            entry["pathUndecodable"] = True
        changes.append(entry)
    return changes


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
            "capabilities": {"files": True, "symbols": True,
                             "imports": False, "changes": True},
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
        """Placeholder until C's parse_imports lands (task book §6.5):
        status="unavailable", never a wrapped empty success."""
        context = self.get(project_id, revision)
        self._validate_path(path)
        if path not in context.manifest:
            raise ExplorerError(HTTPStatus.NOT_FOUND, "PATH_NOT_IN_REVISION",
                                "路径不在该提交的清单中")
        if path not in context.allowed:
            reason = next((item["reason"] for item in context.skipped
                           if item["path"] == path), "该文件在本次索引中被跳过")
            raise ExplorerError(HTTPStatus.FORBIDDEN, "FILE_SKIPPED", reason)
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "path": path,
            "status": "unavailable",
            "imports": [],
            "dependents": [],
            "warnings": ["静态导入关系尚未接入解析器；目录与源码浏览不受影响"],
        }

    # -- changes --------------------------------------------------------------
    def changes(self, project_id: str, base: str, target: str) -> dict:
        """File changes between two full commit SHAs of this project's repo
        (task book §6.6): raw Git name-status letters with rename detection;
        nothing silently dropped. The task-book signature carries projectId,
        base and target only — no revision parameter."""
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
        """Legacy parser transition (task book §6.4, accepted R2-Q6):
        collect_code_facts entries mapped as-is, end_line always null with
        an explicit range-incomplete warning; no fabricated ranges."""
        context = self.get(project_id, revision)
        self._validate_path(path)
        if path not in context.manifest:
            raise ExplorerError(HTTPStatus.NOT_FOUND, "PATH_NOT_IN_REVISION",
                                "路径不在该提交的清单中")
        if path not in context.allowed:
            reason = next((item["reason"] for item in context.skipped
                           if item["path"] == path), "该文件在本次索引中被跳过")
            raise ExplorerError(HTTPStatus.FORBIDDEN, "FILE_SKIPPED", reason)
        try:
            result = collect_code_facts(context.repo_root, context.revision, paths=[path])
        except CodeFactsError as exc:
            raise self._code_facts_error(exc) from exc
        file_entry = next((item for item in result["files"] if item["path"] == path), None)
        skipped_entry = next((item for item in result["skipped"] if item["path"] == path), None)
        warnings = ["legacy_code_facts 不提供结束行，源码范围不完整"]
        if file_entry is not None:
            symbols = [{
                "name": entry["name"],
                "qualified_name": entry["name"],
                "kind": entry["kind"],
                "start_line": entry["line"],
                "end_line": None,
                "docstring": None,
            } for entry in file_entry["entries"]]
            status = "ok"
        elif skipped_entry is not None:
            reason = skipped_entry["reason"]
            status = "parse_error" if ("编码" in reason or "语法" in reason) else "unsupported"
            symbols = []
            warnings.append(reason)
        else:
            raise ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR",
                                "解析器未返回该文件的任何记录")
        return {
            "schemaVersion": 1,
            "projectId": context.project_id,
            "revision": context.revision,
            "path": path,
            "status": status,
            "symbols": symbols,
            "warnings": warnings,
            "parser": "legacy_code_facts",
        }

    @staticmethod
    def _code_facts_error(exc: CodeFactsError) -> ExplorerError:
        message = str(exc)
        if "revision" in message:
            return ExplorerError(HTTPStatus.BAD_REQUEST, "REVISION_INVALID", message)
        if "2000" in message or "16 MiB" in message or "1 MiB" in message:
            return ExplorerError(HTTPStatus.BAD_REQUEST, "BUDGET_EXCEEDED", message)
        if "对象" in message and "不可用" in message:
            # 终审 F5：对象缺失是明确的一类失败（仓库未补全对象），不得
            # 混入 REPO_UNREADABLE。
            return ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "OBJECT_MISSING", message)
        return ExplorerError(HTTPStatus.INTERNAL_SERVER_ERROR, "REPO_UNREADABLE", message)

    # -- tree ----------------------------------------------------------------
    def tree(self, project_id: str, revision: str) -> dict:
        context = self.get(project_id, revision)
        directories: dict[str, dict] = {}
        files: list[dict] = []
        for record in context.entries:
            undecodable = record["path"] is None
            if undecodable:
                path = record["raw_path"].decode("utf-8", "backslashreplace")
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
            if undecodable:
                # 终审 F4：展示文本之外携带 base64 身份；前端据此禁止源码跳转。
                entry["pathUndecodable"] = True
                entry["pathIdentity"] = record["identity"]
                entry["skippedReason"] = next(
                    (item["reason"] for item in context.skipped
                     if item.get("pathIdentity") == record["identity"]),
                    REASON_NAME_ENCODING)
            elif path not in context.allowed:
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
