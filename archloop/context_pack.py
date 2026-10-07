"""Controlled source-context packs: what a real generation/correction call may see.

Rules (A instruction, stage 2): an existing-project generation must carry the
fixed commit's controlled source excerpts, public entry points, symbol and
relation facts and the user's own description, and must record its coverage and
what was missing. File names alone are not "having read the project". The pack
is bounded (never the whole repository), excludes credential-looking files, and
never sends anything that is not committed at the named revision.

Facts used (all already-integrated modules):
- repo_index.gitio.git for the pinned tree listing
- extensions.code_facts.facts.read_source for decoding a committed blob
- repo_index.symbols.parse_symbols / repo_index.imports.parse_imports for the
  symbol and import facts of each included file
"""
from __future__ import annotations

import re

from .contract import ContractError, is_full_sha

ENTRY_NAMES = ("app.py", "main.py", "server.py", "cli.py", "manage.py", "__init__.py", "__main__.py")
EXCLUDED_DIR_PARTS = (".git", "node_modules", "__pycache__", ".venv", "venv", "env",
                      "dist", "build", ".tox", ".mypy_cache", ".pytest_cache", "site-packages")
EXCLUDED_NAME_PATTERNS = (
    r"^\.env", r"\.env$", r"\.env\.", r"secret", r"credential", r"password", r"token",
    r"\.pem$", r"\.key$", r"\.pfx$", r"\.p12$", r"\.keystore$", r"\.sqlite3?$", r"\.db$",
    r"id_rsa", r"id_ed25519", r"\.pyc$",
)
CONTENT_SECRET_PATTERNS = (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9]{24,}\b",
)
# A key/value pair with a quoted value. The key name may itself be quoted
# ({"api_key": "…"}) and may be prefixed (OPENAI_API_KEY, clientSecret), so
# {"api_key": "…"} is caught exactly like api_key = "…" (BATCH-2 GEN-01).
KEY_VALUE_PATTERN = re.compile(
    r"['\"]?([A-Za-z0-9_][A-Za-z0-9_.\-]*)['\"]?\s*[:=]\s*(['\"])([^'\"]{16,})\2")
# credential words, matched as whole name components (never as substrings)
SECRET_KEY_COMPONENTS = ("key", "token", "secret", "password", "passwd", "credential", "credentials")
SECRET_ANYWHERE_COMPONENTS = ("secret", "password", "passwd", "credential", "credentials")
# documentation placeholders are not credentials (a README shows how to set a key)
PLACEHOLDER_MARKERS = ("你的", "<", ">", "your", "xxx", "example", "placeholder",
                       "changeme", "todo", "redacted", "*", "…")


def _key_name_is_secret(name: str) -> bool:
    """True when the field NAME reads as a credential field.

    Components decide, not substrings: snake/kebab/camelCase boundaries are
    split and the LAST component must be a credential word (`api_key`,
    `accessToken`, `CLIENT_SECRET`, `KEY`); a "secret"/"password"-class word is
    honoured anywhere (`secret_key_base`). Substrings like `monkey`, `keynote`
    or `service_name` must NOT count — a substring match would exclude ordinary
    configuration files from the pack (BATCH-3 GEN-01).
    """
    if not name:
        return False
    # Preserve acronym boundaries: clientAPIKey -> client_API_Key.
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", spaced)
    parts = [part.lower() for part in re.split(r"[^A-Za-z0-9]+", spaced) if part]
    if not parts:
        return False
    if parts[-1] in SECRET_KEY_COMPONENTS:
        return True
    return any(part in SECRET_ANYWHERE_COMPONENTS for part in parts)


def _looks_like_secret(text: str) -> bool:
    for pattern in CONTENT_SECRET_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            fragment = match.group(0).lower()
            if any(marker in fragment for marker in PLACEHOLDER_MARKERS):
                continue
            return True
    for match in KEY_VALUE_PATTERN.finditer(text):
        if not _key_name_is_secret(match.group(1)):
            continue
        fragment = match.group(0).lower()
        if any(marker in fragment for marker in PLACEHOLDER_MARKERS):
            continue
        return True
    return False


def _excluded(path: str) -> str | None:
    parts = path.replace("\\", "/").split("/")
    if any(part in EXCLUDED_DIR_PARTS for part in parts[:-1]):
        return "目录被排除（虚拟环境/缓存/依赖）"
    name = parts[-1]
    for pattern in EXCLUDED_NAME_PATTERNS:
        if re.search(pattern, name, re.I):
            return "疑似凭据或二进制文件，默认不外发"
    return None


def _entry_rank(path: str) -> tuple:
    name = path.rsplit("/", 1)[-1]
    depth = path.count("/")
    return (0 if name in ENTRY_NAMES else 1, depth, path)


def build_context_pack(repo_path: str, revision: str, *, max_files: int = 48,
                       max_file_chars: int = 6000, max_total_chars: int = 120_000,
                       max_docs: int = 6, doc_chars: int = 2500) -> dict:
    """Build a bounded, recorded context pack for one fixed commit."""
    if not is_full_sha(revision):
        raise ContractError("VALIDATION_FAILED", "上下文包需要完整代码提交 SHA")
    from extensions.code_facts.facts import read_source
    from repo_index.gitio import repository_root, git

    root = repository_root(repo_path)
    raw = git(root, "ls-tree", "-r", "-z", "--name-only", revision)
    tracked = [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]
    py_files = [path for path in tracked if path.endswith(".py")]
    docs = [path for path in tracked if re.search(r"\.md$", path, re.I)]

    # credential-looking files are named once, for every tracked file, so the
    # pack records what was deliberately not read (not only what it read)
    excluded: list[dict] = []
    for path in tracked:
        reason = _excluded(path)
        if reason:
            excluded.append({"path": path, "reason": reason})
    excluded_paths = {item["path"] for item in excluded}
    candidates = [path for path in sorted(py_files, key=_entry_rank)
                  if path not in excluded_paths]

    files = []
    used = 0
    skipped: list[dict] = []
    symbols_total = 0
    for path in candidates:
        if len(files) >= max_files or used >= max_total_chars:
            skipped.append({"path": path, "reason": "超出本次有界选择预算（文件数或总字符数）"})
            continue
        try:
            source = read_source(root, revision, path)
        except Exception as exc:  # unreadable/undecodable objects are recorded, not guessed
            skipped.append({"path": path, "reason": f"读取失败：{type(exc).__name__}"})
            continue
        if _looks_like_secret(source):
            excluded.append({"path": path, "reason": "内容疑似凭据，默认不外发"})
            continue
        from repo_index.symbols import parse_symbols
        from repo_index.imports import parse_imports
        try:
            symbol_view = parse_symbols(path, source)
        except Exception:
            symbol_view = {"symbols": []}
        try:
            import_view = parse_imports(path, source)
        except Exception:
            import_view = {"imports": []}
        symbols = symbol_view.get("symbols", []) or []
        symbols_total += len(symbols)
        excerpt = source[:max_file_chars]
        files.append({
            "path": path,
            "bytes": len(source.encode("utf-8")),
            "excerptChars": len(excerpt),
            "truncated": len(source) > len(excerpt),
            "symbols": [{"name": item.get("name"), "kind": item.get("kind"),
                         "line": item.get("line"), "qualified": item.get("qualified_name")}
                        for item in symbols[:40]],
            "imports": (import_view.get("imports", []) or [])[:40],
            "excerpt": excerpt,
        })
        used += len(excerpt)

    def doc_rank(path: str) -> tuple:
        lowered = path.lower()
        if lowered.startswith("readme"):
            return (0, path)
        if lowered.startswith("docs/"):
            return (1, path)
        return (2, path)

    doc_pack = []
    for path in sorted(docs, key=doc_rank)[:max_docs]:
        if path in excluded_paths:
            continue
        try:
            text = read_source(root, revision, path)
        except Exception as exc:
            skipped.append({"path": path, "reason": f"读取失败：{type(exc).__name__}"})
            continue
        if _looks_like_secret(text):
            excluded.append({"path": path, "reason": "内容疑似凭据，默认不外发"})
            continue
        doc_pack.append({"path": path, "excerpt": text[:doc_chars],
                         "truncated": len(text) > doc_chars})

    entry_points = sorted({f"{file_entry['path']}::{symbol['name']}"
                           for file_entry in files
                           for symbol in file_entry["symbols"]
                           if symbol["kind"] in ("function", "async_function", "class")
                           and (symbol["name"] in ("main", "run", "serve", "create_app",
                                                   "handle", "start")
                                or file_entry["path"].rsplit("/", 1)[-1] in ENTRY_NAMES)})[:40]

    coverage = {
        "codeRevision": revision,
        "trackedFiles": len(tracked),
        "pythonFiles": len(py_files),
        "filesIncluded": len(files),
        "docsIncluded": len(doc_pack),
        "symbolsIncluded": symbols_total,
        "charsIncluded": used + sum(len(item["excerpt"]) for item in doc_pack),
        "notIncluded": len(skipped),
        "excluded": len(excluded),
        "selectionRule": "入口同名文件优先，其次按路径深度；有界文件数/字符数预算，确定性顺序",
    }
    return {
        "codeRevision": revision,
        "files": files,
        "docs": doc_pack,
        "entryPoints": entry_points,
        "skipped": skipped[:50],
        "excluded": excluded[:50],
        "coverage": coverage,
        "limits": ["上下文是有界选择，不包含全部仓库内容；未列出的文件没有被读取",
                   "符号与导入是静态声明事实，不代表运行调用链",
                   "凭据与疑似密钥内容默认不外发"],
    }


__all__ = ["build_context_pack"]
