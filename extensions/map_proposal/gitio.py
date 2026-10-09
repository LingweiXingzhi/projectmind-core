# -*- coding: utf-8 -*-
"""Read-only Git access for C (P05, ported from LOCAL diff_model._git).

Environment is cleaned of GIT_* overrides, lazy fetch and external diffs are
disabled, every read is pinned to an explicit revision. Nothing here writes to
the repository or the working tree.
"""
from __future__ import annotations

import os
import subprocess


class DiffSignalError(ValueError):
    """A pinned Git read failed; the caller must degrade, never guess."""


def git(repo, *args) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "LC_ALL": "C",
        }
    )
    try:
        result = subprocess.run(
            ["git", "--no-lazy-fetch", "-C", str(repo), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=15,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiffSignalError("Git 读取失败或超时") from exc
    if result.returncode:
        raise DiffSignalError("无法读取指定提交的内容")
    return result.stdout


def ls_tree_names(repo, revision) -> set:
    """All repo-relative paths present at a pinned revision (one process)."""
    raw = git(repo, "ls-tree", "-r", "--name-only", "-z", revision)
    return {name for name in raw.decode("utf-8", errors="replace").split("\0") if name}


def read_blob(repo, revision, path) -> str:
    raw = git(repo, "show", f"{revision}:{path}")
    return raw.decode("utf-8", errors="replace")


def diff_patches(repo, base_revision, target_revision, paths) -> bytes:
    if not paths:
        return b""
    return git(
        repo,
        "diff",
        "--no-ext-diff",
        "-U0",
        base_revision,
        target_revision,
        "--",
        *sorted(set(paths)),
    )
