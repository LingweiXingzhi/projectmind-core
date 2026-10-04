# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock

from extensions.map_proposal import extension


class TestMapProposal(unittest.TestCase):
    def setUp(self):
        self.rev = "a" * 40
        self.ctx = MagicMock()
        self.ctx.snapshot.return_value = {
            "revision": self.rev,
            "nodes": [],
            "edges": [],
        }

    def test_sha_mismatch_refusal(self):
        """C-S02: SHA 不匹配必须抛异常拒绝"""
        with self.assertRaises(Exception):
            extension.handle(
                self.ctx,
                "POST",
                {"code_facts": {"revision": "b" * 40, "files": []}},
            )

    def test_empty_facts(self):
        """C-S03: 空事实输入不产生候选且必须带原因"""
        res = extension.handle(
            self.ctx,
            "POST",
            {"code_facts": {"revision": self.rev, "files": [], "skipped": []}},
        )
        self.assertEqual(res["candidates"], [])
        self.assertEqual(res["proposals"], [])
        self.assertTrue(res.get("note") or res.get("status"))

    def test_happy_path_and_contract_shape(self):
        """C-S01, C-S06, C-S11 及规范校验"""
        facts = {
            "revision": self.rev,
            "files": [
                {
                    "path": "app.py",
                    "language": "python",
                    "entries": [{"name": "run", "kind": "function", "line": 10}],
                }
            ],
            "skipped": [],
        }
        res = extension.handle(self.ctx, "POST", {"code_facts": facts})

        self.assertEqual(res["status"], "rule_candidate")
        self.assertEqual(len(res["candidates"]), 1)
        c = res["candidates"][0]
        self.assertEqual(c["evidencePaths"], ["app.py"])
        self.assertIsInstance(c["unknowns"], list)

        self.assertEqual(len(res["proposals"]), 1)
        p = res["proposals"][0]
        self.assertEqual(p["status"], "PROPOSED")
        self.assertTrue(p["human_required"])
        self.assertNotIn("position", p["proposed_change"], "反目标：严禁修改 position")
        self.assertTrue(len(p["evidence"]) > 0, "反目标：evidence 不得为空")

    def test_skipped_falls_to_unresolved(self):
        """skipped 文件进入 unresolved，不基于猜测生成 NODE_ADD"""
        facts = {
            "revision": self.rev,
            "files": [],
            "skipped": [{"path": "bad.py", "reason": "syntax error"}],
        }
        res = extension.handle(self.ctx, "POST", {"code_facts": facts})
        self.assertEqual(len(res["proposals"]), 0)
        unres_paths = [u["subject"] for u in res["unresolved"]]
        self.assertIn("bad.py", unres_paths)


if __name__ == "__main__":
    unittest.main()
