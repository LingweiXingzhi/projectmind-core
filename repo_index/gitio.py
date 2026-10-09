"""Hardened Git runner for the repo explorer.

Reads committed objects only. Unlike app.git() this runner also disables
replace refs (a local replace ref must never change what a fixed SHA
reads) and enforces a timeout, matching the guarantees the code-facts
collector already provides. Never fetches: lazy fetch is forbidden.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

TIMEOUT_SECONDS = 30


class GitIoError(Exception):
    """Git could not provide the requested object; safe to show locally."""


def git(repo: Path, *args: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "LC_ALL": "C",
    })
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "--no-pager", "--no-replace-objects",
             "-C", str(repo), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, check=False, env=env, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitIoError("Git 读取超时") from exc
    except OSError as exc:
        raise GitIoError("Git 不可用") from exc
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitIoError(message or f"git {' '.join(args)} failed")
    return result.stdout


def repository_root(repo_path: Path) -> Path:
    """Resolve the real repository root, refusing subdirectories."""
    root = Path(repo_path).expanduser()
    try:
        root = root.resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise GitIoError(f"仓库路径无效: {repo_path}") from exc
    if not root.is_dir():
        raise GitIoError(f"仓库路径无效: {repo_path}")
    reported = Path(git(root, "rev-parse", "--show-toplevel").decode(
        "utf-8", errors="replace").strip()).resolve()
    if reported != root:
        raise GitIoError(f"仓库路径无效: {repo_path}")
    return root
