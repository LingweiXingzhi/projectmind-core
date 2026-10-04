"""Git diff signal extraction for C (import/dependency signals come from the diff).

changed_paths 口径以请求为准(A 的 /api/compare 同源);这里只读取 patch 文本以提取
import 行信号——不自行判定“哪些文件变了”。
"""
from __future__ import annotations

import os
import re
import subprocess

_ADDED_STATIC = re.compile(r"^\+\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\b|import\s+([\w.,\s]+))")
_ADDED_DYNAMIC = re.compile(r"^\+\s*.*(?:importlib\.import_module|__import__)\s*\(")
_REMOVED_STATIC = re.compile(r"^-\s*(?:from\s+([A-Za-z_][\w.]*)\s+import\b|import\s+([\w.,\s]+))")


class DiffSignalError(ValueError):
    pass


def _git(repo, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_NO_LAZY_FETCH": "1", "LC_ALL": "C"})
    try:
        result = subprocess.run(["git", "--no-lazy-fetch", "-C", str(repo), *args],
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=15, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiffSignalError("Git 读取失败或超时") from exc
    if result.returncode:
        raise DiffSignalError("无法读取指定提交的差异")
    return result.stdout


def _modules(match):
    dotted = match.group(1)
    if dotted:
        return [dotted]
    names = []
    for part in (match.group(2) or "").split(","):
        part = part.strip().split(" as ")[0].strip()
        if part:
            names.append(part)
    return names


def import_signals(repo, base_revision, target_revision, changed_py_paths):
    """Return {'added': [(path, module, line)], 'removed': [...], 'dynamic': [(path, line)]}."""
    signals = {"added": [], "removed": [], "dynamic": []}
    if not changed_py_paths:
        return signals
    raw = _git(repo, "diff", "--no-ext-diff", "-U0", base_revision, target_revision, "--",
               *sorted(set(changed_py_paths)))
    path = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            continue
        if line.startswith("--- "):
            continue
        if path is None:
            continue
        added_static = _ADDED_STATIC.match(line)
        if added_static:
            for module in _modules(added_static):
                signals["added"].append({"path": path, "module": module,
                                         "line": line.lstrip("+- ").strip()[:200]})
            continue
        if _ADDED_DYNAMIC.match(line):
            signals["dynamic"].append({"path": path, "line": line.lstrip("+- ").strip()[:200]})
            continue
        removed_static = _REMOVED_STATIC.match(line)
        if removed_static:
            for module in _modules(removed_static):
                signals["removed"].append({"path": path, "module": module,
                                           "line": line.lstrip("+- ").strip()[:200]})
    return signals


def resolve_module(module, known_paths):
    """module dotted name → repo-relative path candidates ∩ known_paths。"""
    if not module:
        return None
    base = module.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in known_paths:
            return candidate
    return None
