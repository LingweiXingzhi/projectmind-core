# -*- coding: utf-8 -*-
"""终审 F4（changes/rename machine identity）真实 Git fixture 回归。

用 Git 底层命令（hash-object + mktree -z + commit-tree）构造 base/target
两个提交：不同 raw byte path 的展示文本完全相同（backslashreplace 文本与
合法的"字面反斜杠名"一致）。验收标准（专项复核 A 节）：

- add / modify / delete / rename 四种 display collision 各自保持两条 entry；
- identity（含 rename 的 oldIdentity/newIdentity）互不相同；
- rename 的 newPath/newIdentity/oldPath/oldIdentity 齐备；
- 不可解码侧 identity 以 NUL+b64 命名空间隔离，且不能作为源码路径打开；
- UI（buildChangeRows 纯函数）每条 entry 一行、key 互不相同、不合并。
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from app import make_handler
from repo_index.explorer import ExplorerRegistry

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ,
       "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def run_git_bytes(repo: Path, *args: str, data: bytes | None = None,
                  env: dict | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], input=data,
                          capture_output=True, check=True, env=env).stdout


class ChangesIdentityFixtureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "changes-identity-repo"
        self.repo.mkdir()
        run_git_bytes(self.repo, "init", "-q", "-b", "main")
        run_git_bytes(self.repo, "config", "user.name", "T")
        run_git_bytes(self.repo, "config", "user.email", "t@example.invalid")

        def blob(content: bytes) -> bytes:
            return run_git_bytes(self.repo, "hash-object", "-w", "--stdin",
                                 data=content).strip()

        def mktree(entries: bytes) -> bytes:
            return run_git_bytes(self.repo, "mktree", "-z", data=entries).strip()

        def entry(mode: bytes, oid: bytes, name: bytes) -> bytes:
            return mode + b" blob " + oid + b"\t" + name + b"\0"

        def commit(tree: bytes, parent: bytes | None, message: bytes) -> bytes:
            args = ["commit-tree", tree.decode("ascii")]
            if parent is not None:
                args += ["-p", parent.decode("ascii")]
            return run_git_bytes(self.repo, *args, data=message,
                                 env=ENV).strip()

        # ---- C1：del/mod/ren 各含一对"展示文本相同"的文件 ----
        # 非法 UTF-8 名（含 0xff 字节）与其 backslashreplace 展示文本恰好
        # 等于合法的"字面反斜杠名"——两种 raw path 的展示完全一致。
        pairs = {}
        for kind in (b"del", b"mod", b"ren"):
            pairs[kind + b"-invalid"] = blob(kind + b" invalid v1\n")
            pairs[kind + b"-legal"] = blob(kind + b" legal v1\n")
        c1_entries = b"".join([
            # 0xff 名：display 为 "del-\xff.py" 形式
            entry(b"100644", pairs[b"del-invalid"], b"del-\xff.py"),
            entry(b"100644", pairs[b"mod-invalid"], b"mod-\xff.py"),
            entry(b"100644", pairs[b"ren-invalid"], b"ren-\xff-old.py"),
            # 字面反斜杠名：display 与上一一对应（Python 字节串 b"\\xff"）
            entry(b"100644", pairs[b"del-legal"], b"del-\\xff.py"),
            entry(b"100644", pairs[b"mod-legal"], b"mod-\\xff.py"),
            entry(b"100644", pairs[b"ren-legal"], b"ren-\\xff-old.py"),
        ])
        c1_tree = mktree(c1_entries)
        self.base = commit(c1_tree, None, b"base with collision pairs\n").decode("ascii")

        # ---- C2：add 碰撞对 + 双删 + 双改 + 双改名 ----
        add_invalid = blob(b"added invalid\n")
        add_legal = blob(b"added legal\n")
        c2_entries = b"".join([
            entry(b"100644", blob(b"mod invalid v2\n"), b"mod-\xff.py"),
            entry(b"100644", blob(b"mod legal v2\n"), b"mod-\\xff.py"),
            entry(b"100644", add_invalid, b"add-\xff.py"),
            entry(b"100644", add_legal, b"add-\\xff.py"),
            entry(b"100644", pairs[b"ren-invalid"], b"ren-\xff-new.py"),
            entry(b"100644", pairs[b"ren-legal"], b"ren-\\xff-new.py"),
        ])
        c2_tree = mktree(c2_entries)
        self.target = commit(c2_tree, self.base.encode("ascii"),
                             b"target: add/modify/delete/rename collisions\n").decode("ascii")
        run_git_bytes(self.repo, "update-ref", "refs/heads/main", self.target.encode("ascii"))

        self._server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.repo, None, explorer_registry=ExplorerRegistry()))
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self.port = self._server.server_address[1]
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/repo-explorer/open",
                     body=json.dumps({"repoPath": str(self.repo)}),
                     headers={"Content-Type": "application/json"})
        opened = json.loads(conn.getresponse().read())
        conn.close()
        self.project_id = opened["projectId"]

    def tearDown(self):
        self._server.shutdown()
        self._server.server_close()
        self._tmp.cleanup()

    def _changes(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/changes?projectId={self.project_id}"
                     f"&base={self.base}&target={self.target}")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw)

    def _by_display(self, changes, status_letter):
        picked = [c for c in changes if c["status"] == status_letter]
        return picked

    # ---- add display collision ----
    def test_add_display_collision_keeps_two_distinct_entries(self):
        status, body = self._changes()
        self.assertEqual(status, 200)
        adds = self._by_display(body["changes"], "A")
        self.assertEqual(len(adds), 2, "two raw adds share the display text")
        self.assertEqual(len({c["path"] for c in adds}), 1, "displays are identical")
        self.assertEqual(len({c["identity"] for c in adds}), 2,
                         "identities must differ for different raw byte paths")
        invalid = [c for c in adds if c.get("pathUndecodable")]
        legal = [c for c in adds if not c.get("pathUndecodable")]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(len(legal), 1)
        self.assertTrue(invalid[0]["identity"].startswith("\x00b64:"))
        self.assertEqual(legal[0]["identity"], legal[0]["path"])

    # ---- modify display collision ----
    def test_modify_display_collision_keeps_two_distinct_entries(self):
        status, body = self._changes()
        self.assertEqual(status, 200)
        mods = self._by_display(body["changes"], "M")
        self.assertEqual(len(mods), 2)
        self.assertEqual(len({c["identity"] for c in mods}), 2)
        self.assertTrue(all(c["oldPath"] is None for c in mods))

    # ---- delete display collision ----
    def test_delete_display_collision_keeps_two_distinct_entries(self):
        status, body = self._changes()
        self.assertEqual(status, 200)
        deletes = self._by_display(body["changes"], "D")
        self.assertEqual(len(deletes), 2)
        self.assertEqual(len({c["path"] for c in deletes}), 1, "displays are identical")
        self.assertEqual(len({c["identity"] for c in deletes}), 2)
        self.assertTrue(all(c["oldPath"] is None for c in deletes))

    # ---- rename display collision: old/new identities both preserved ----
    def test_rename_display_collision_keeps_old_and_new_identities(self):
        status, body = self._changes()
        self.assertEqual(status, 200)
        renames = self._by_display(body["changes"], "R")
        self.assertEqual(len(renames), 2, "two raw renames must stay two records")
        # oldPath/newPath 展示文本完全相同——只能靠身份区分。
        self.assertEqual(len({c["oldPath"] for c in renames}), 1)
        self.assertEqual(len({c["path"] for c in renames}), 1)
        self.assertEqual(len({c["oldIdentity"] for c in renames}), 2,
                         "oldIdentity must distinguish the two renames")
        self.assertEqual(len({c["newIdentity"] for c in renames}), 2,
                         "newIdentity must distinguish the two renames")
        for change in renames:
            self.assertEqual(change["newPath"], change["path"])
            self.assertEqual(change["newIdentity"], change["identity"])
            self.assertNotEqual(change["oldIdentity"], change["newIdentity"])
            self.assertTrue(change["oldPath"].endswith("old.py"))
            self.assertTrue(change["path"].endswith("new.py"))
        invalid = [c for c in renames if c.get("pathUndecodable")]
        legal = [c for c in renames if not c.get("pathUndecodable")]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(len(legal), 1)
        self.assertTrue(invalid[0]["oldIdentity"].startswith("\x00b64:"))
        self.assertTrue(invalid[0]["newIdentity"].startswith("\x00b64:"))
        self.assertEqual(legal[0]["oldIdentity"], legal[0]["oldPath"])
        self.assertEqual(legal[0]["newIdentity"], legal[0]["path"])

    # ---- 普通改名（唯一一条、无碰撞）行为不变 ----
    def test_plain_rename_fields_unchanged(self):
        # 在 changes-repo 式普通仓库上验证普通 UTF-8 rename 契约不变：
        # path=新路径、oldPath=旧路径，新增 identity 等于各自明文。
        from repo_index.explorer import parse_name_status
        parsed = parse_name_status(b"R100\0old-name.py\0new-name.py\0")
        self.assertEqual(parsed[0]["status"], "R")
        self.assertEqual(parsed[0]["path"], "new-name.py")
        self.assertEqual(parsed[0]["oldPath"], "old-name.py")
        self.assertEqual(parsed[0]["identity"], "new-name.py")
        self.assertEqual(parsed[0]["newIdentity"], "new-name.py")
        self.assertEqual(parsed[0]["oldIdentity"], "old-name.py")
        self.assertNotIn("pathUndecodable", parsed[0])

    # ---- identity 不能作为源码路径使用 ----
    def test_machine_identity_is_not_openable_as_source_path(self):
        status, body = self._changes()
        self.assertEqual(status, 200)
        invalid = next(c for c in body["changes"]
                       if c.get("pathUndecodable") and c["status"] == "A")
        identity = invalid["identity"]
        self.assertTrue(identity.startswith("\x00b64:"))
        # NUL 前缀身份永远无法通过 file API 的路径校验（控制字符拒绝）：
        # machine identity 不能被误用作源码路径。
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", f"/api/repo-explorer/file?projectId={self.project_id}"
                     f"&revision={self.target}&path={quote(identity, safe='')}"
                     f"&startLine=1&endLine=10")
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        self.assertEqual(response.status, 400)
        self.assertEqual(json.loads(raw)["error"]["code"], "PATH_INVALID")

    # ---- UI（buildChangeRows 纯函数）：碰撞 entries 全保留、key 互异 ----
    def test_ui_change_rows_keep_colliding_entries_distinct(self):
        if shutil.which("node") is None:
            self.skipTest("node is not available for the pure-function harness")
        status, body = self._changes()
        self.assertEqual(status, 200)
        harness = (
            "const fs = require('fs');\n"
            "eval(fs.readFileSync(process.argv[1], 'utf8'));\n"
            "const changes = JSON.parse(process.argv[2]);\n"
            "console.log(JSON.stringify(buildChangeRows(changes)));\n"
        )
        proc = subprocess.run(
            ["node", "-e", harness, str(ROOT / "web" / "explorer-core.js"),
             json.dumps(body["changes"], ensure_ascii=False)],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = json.loads(proc.stdout)
        self.assertEqual(len(rows), len(body["changes"]),
                         "every change entry becomes exactly one row — no merging")
        self.assertEqual(len({row["key"] for row in rows}), len(rows),
                         "row keys (machine identity) must be pairwise distinct")
        # rename 行：key 与 oldKey 都来自身份，碰撞 rename 不合并。
        rename_rows = [row for row in rows if row["status"] == "R"]
        self.assertEqual(len(rename_rows), 2)
        self.assertEqual(len({row["key"] for row in rename_rows}), 2)
        self.assertEqual(len({row["oldKey"] for row in rename_rows}), 2)
        self.assertEqual(len({row["display"] for row in rename_rows}), 1,
                         "displays are identical; only identities distinguish them")


if __name__ == "__main__":
    unittest.main()
