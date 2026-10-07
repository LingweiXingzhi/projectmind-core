"""Read code through the existing hardened runner; write only configured map Git."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile

from repo_index.gitio import GitIoError, git, repository_root
from .errors import WorkspaceError, require
from .schema import SHA, canonical, identifier, path as evidence_path, validate_packet


def read_git(repo, *args):
    try:
        return git(repo, *args)
    except GitIoError as exc:
        raise WorkspaceError("EVIDENCE_MISMATCH", "固定 Git 对象不可读取") from exc


def full_revision(repo, revision):
    require(isinstance(revision, str) and SHA.fullmatch(revision), "STALE_CONTEXT")
    try:
        actual = read_git(repo, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    except WorkspaceError as exc:
        raise WorkspaceError("STALE_CONTEXT", "固定提交不在已登记仓库中") from exc
    require(actual == revision, "STALE_CONTEXT")
    return revision


def code_identity(repo):
    """Stable origin identity; local-only repositories deliberately stay local."""
    repo = repository_root(Path(repo))
    try:
        origin = git(repo, "config", "--get", "remote.origin.url").decode().strip()
    except GitIoError:
        origin = ""
    # No transport or credential lookup. Tokens/userinfo are never exported.
    require("\n" not in origin and "\x00" not in origin)
    require(not ("://" in origin and "@" in origin.split("://", 1)[1].split("/", 1)[0]),
            detail="代码来源 URL 不能包含凭据")
    locator = origin.rstrip("/") if origin else "local:" + str(repo)
    return "repo-" + hashlib.sha256(locator.encode()).hexdigest()


def verify_evidence(repo, evidence, code_revision):
    require(evidence["codeRevision"] == code_revision, "EVIDENCE_MISMATCH")
    relative = evidence_path(evidence["path"])
    listing = read_git(repo, "ls-tree", "-z", code_revision, "--", relative)
    require(listing.startswith((b"100644 blob ", b"100755 blob ")),
            "EVIDENCE_MISMATCH", "证据文件不存在或不是普通已提交文件")
    size = int(read_git(repo, "cat-file", "-s", code_revision + ":" + relative))
    require(size <= 1_000_000, "EVIDENCE_MISMATCH", "证据文件超过核查上限")
    if "lineEnd" in evidence:
        blob = read_git(repo, "show", code_revision + ":" + relative)
        require(evidence["lineEnd"] <= len(blob.splitlines()), "EVIDENCE_MISMATCH")


class GitPublisher:
    def __init__(self, repo, branch):
        self.repo = repository_root(Path(repo))
        require((self.repo / ".git").is_dir(), detail="架构发布使用专用普通 Git 工作副本")
        require(isinstance(branch, str) and branch.startswith("architecture/candidates/")
                and all(c not in branch for c in ("\n", "\r", "\x00")),
                detail="只允许 architecture/candidates/ 专用候选分支")
        self.branch = branch

    def head(self):
        require(read_git(self.repo, "symbolic-ref", "--short", "HEAD").decode().strip()
                == self.branch, "PUBLICATION_CONFLICT", "当前架构分支与配置不一致")
        return read_git(self.repo, "rev-parse", "HEAD").decode().strip()

    def clean(self):
        require(not read_git(self.repo, "status", "--porcelain", "--untracked-files=all"),
                "DIRTY_ARCHITECTURE_REPO")

    def prepare(self, packet):
        self.clean()
        return {"preHead": self.head(), "path": self.relative_path(packet["mapId"],
                packet["mapRevision"]), "packet": packet}

    @staticmethod
    def relative_path(map_id, map_revision):
        identifier(map_id)
        require(isinstance(map_revision, str) and map_revision.startswith("sha256:")
                and len(map_revision) == 71)
        from .schema import MAP_REV
        require(MAP_REV.fullmatch(map_revision))
        return "versions/" + map_id + "/" + map_revision[7:] + ".json"

    def _write_file(self, relative, content):
        target = self.repo / relative
        current = self.repo
        for part in Path(relative).parts:
            current = current / part
            require(not current.is_symlink(), "PUBLICATION_CONFLICT")
        target.parent.mkdir(parents=True, exist_ok=True)
        # A hard exit before replace must not leave an unexpected tracked-tree
        # file that blocks journal recovery. Git metadata is on the same volume.
        fd, temporary = tempfile.mkstemp(prefix="architecture-publication-", dir=self.repo / ".git")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _commit(self, relative, map_revision):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1",
                   GIT_NO_LAZY_FETCH="1", LC_ALL="C")
        for args in (["add", "--", relative],
                     ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                      "commit", "--only", "-m", "architecture: publish " + map_revision,
                      "--", relative]):
            try:
                result = subprocess.run(["git", "--no-lazy-fetch", "--no-replace-objects",
                                         "-C", str(self.repo), *args],
                                        env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise WorkspaceError("PUBLICATION_FAILED") from exc
            if result.returncode:
                raise WorkspaceError("PUBLICATION_FAILED", "Git commit 未成功；保留恢复日志")

    def publish(self, journal):
        # Shared across separate service instances/data roots, never tracked.
        lock = None
        try:
            lock = sqlite3.connect(self.repo / ".git/architecture-publication-lock.sqlite",
                                   timeout=15, isolation_level=None)
            lock.execute("BEGIN IMMEDIATE")
            relative, packet = journal["path"], journal["packet"]
            content = (canonical(packet) + "\n").encode()
            head = self.head()
            if head != journal["preHead"]:
                # Recover only the exact single publication commit, not an
                # unrelated commit that happens to contain the same file.
                parents = read_git(self.repo, "show", "-s", "--format=%P", head).decode().split()
                changed = read_git(self.repo, "diff-tree", "--no-commit-id",
                                   "--name-only", "-r", head).decode().splitlines()
                require(parents == [journal["preHead"]] and changed == [relative],
                        "PUBLICATION_CONFLICT")
                require(read_git(self.repo, "show", head + ":" + relative) == content,
                        "PUBLICATION_CONFLICT")
                self.clean()
                return head
            target = self.repo / relative
            status = read_git(self.repo, "status", "--porcelain", "-z",
                              "--untracked-files=all")
            # Recovery may own only the exact version file. Unexpected dirty
            # files, staged changes, symlinks or changed bytes are never reset.
            entries = [item for item in status.split(b"\0") if item]
            require(all(item[3:].decode("utf-8") == relative
                        and item[:2] in (b"??", b"A ", b" A") for item in entries),
                    "DIRTY_ARCHITECTURE_REPO")
            if target.exists():
                require(not target.is_symlink() and target.read_bytes() == content,
                        "VERSION_CONFLICT")
                require(bool(entries), "VERSION_CONFLICT",
                        "已有正式版本文件，不能创建覆盖提交")
            else:
                self._write_file(relative, content)
            self._commit(relative, packet["mapRevision"])
            committed = self.head()
            require(committed != head and read_git(self.repo, "show",
                    committed + ":" + relative) == content, "PUBLICATION_FAILED")
            self.clean()
            return committed
        except sqlite3.Error as exc:
            raise WorkspaceError("PUBLICATION_FAILED", "架构发布锁不可用") from exc
        except OSError as exc:
            raise WorkspaceError("PUBLICATION_FAILED", "架构版本写入未完成") from exc
        finally:
            if lock is not None:
                lock.close()

    @classmethod
    def read_version(cls, repo, map_id, map_revision, source_revision):
        repo = repository_root(Path(repo))
        full_revision(repo, source_revision)
        relative = cls.relative_path(map_id, map_revision)
        listing = read_git(repo, "ls-tree", "-z", source_revision, "--", relative)
        require(listing.startswith((b"100644 blob ", b"100755 blob ")),
                "EVIDENCE_MISMATCH")
        require(int(read_git(repo, "cat-file", "-s", source_revision + ":" + relative))
                <= 2_000_000, "INVALID_INPUT")
        try:
            packet = validate_packet(json.loads(read_git(repo, "show",
                                                         source_revision + ":" + relative)))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise WorkspaceError("EVIDENCE_MISMATCH") from exc
        require(packet["mapId"] == map_id and packet["mapRevision"] == map_revision,
                "STALE_CONTEXT")
        return {"version": packet, "provenance": {"mapSourceRevision": source_revision,
                "sourceKind": "git_commit", "limits":
                ["Git 字节和摘要已核对；不认证审核人的身份，不推断新代码已通过核查"]}}
