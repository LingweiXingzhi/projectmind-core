# -*- coding: utf-8 -*-
"""Role C independent unit tests for archloop candidate proposals."""

import unittest
from extensions.map_proposal.candidates import (
    generate_bootstrap_proposal,
    generate_nl_correction_patch,
    generate_incremental_proposal,
    detect_process_deviations,
    ERR_STALE_CONTEXT,
    ERR_EVIDENCE_MISMATCH
)


class TestArchloopCCandidates(unittest.TestCase):

    def test_bootstrap_planning_mode(self):
        """验证无代码规划模式：codeRepoId 与 codeRevision 为 null，依据为需求 ID。"""
        ctx = {
            "mode": "planning",
            "workspaceId": "ws_test_plan",
            "goals": [
                {"id": "req_01", "title": "认证中心", "description": "处理用户登录", "detail": "需支持 OAuth2"}
            ]
        }
        res = generate_bootstrap_proposal(ctx)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["mode"], "planning")
        self.assertIsNone(res["codeRepoId"])
        self.assertIsNone(res["codeRevision"])
        self.assertEqual(len(res["graphCandidate"]["nodes"]), 1)
        node = res["graphCandidate"]["nodes"][0]
        self.assertEqual(node["status"], "planned")
        self.assertEqual(node["evidence"][0]["kind"], "user_requirement")

    def test_bootstrap_existing_project_mode(self):
        """验证已有代码模式：带具体 codeRevision 与代码符号证据。"""
        ctx = {
            "mode": "existing_project",
            "codeRepoId": "repo_core",
            "codeRevision": "c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db",
            "facts": {
                "symbols": [
                    {"path": "auth/token.py", "name": "create_token", "qualified_name": "auth.token.create_token", "kind": "function"}
                ]
            }
        }
        res = generate_bootstrap_proposal(ctx)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["codeRevision"], "c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db")
        self.assertTrue(len(res["graphCandidate"]["nodes"]) >= 1)
        node = res["graphCandidate"]["nodes"][0]
        self.assertEqual(node["status"], "implemented")
        self.assertEqual(node["evidence"][0]["kind"], "source_symbol")

    def test_nl_correction_patch_preserves_unselected_nodes(self):
        """验证自然语言纠正仅生成局部 Patch，不覆盖未选中节点。"""
        base_graph = {
            "mapRevision": "map_v1",
            "nodes": [
                {"nodeId": "node_a", "title": "A", "role": "原始职责 A"},
                {"nodeId": "node_b", "title": "B", "role": "原始职责 B"}
            ]
        }
        selection = {"nodeId": "node_a"}
        patch = generate_nl_correction_patch(base_graph, selection, "修正职责为高吞吐处理")
        self.assertEqual(patch["status"], "ok")
        self.assertEqual(patch["baseMapRevision"], "map_v1")
        self.assertEqual(len(patch["operations"]), 1)
        self.assertEqual(patch["operations"][0]["nodeId"], "node_a")
        self.assertIn("修正职责为高吞吐处理", patch["operations"][0]["changes"]["role"])

    def test_incremental_proposal_operations(self):
        """验证增量更新提案：处理新增、修改与删除文件。"""
        base_graph = {"mapRevision": "map_v1", "codeRevision": "rev_old"}
        facts_diff = {
            "added_files": ["new_module/worker.py"],
            "modified_files": ["core/app.py"],
            "deleted_files": ["legacy/old.py"]
        }
        res = generate_incremental_proposal(base_graph, "rev_old", "rev_new", facts_diff)
        self.assertEqual(res["status"], "ok")
        ops = res["operations"]
        op_types = [o["op"] for o in ops]
        self.assertIn("add_node", op_types)
        self.assertIn("update_node", op_types)
        self.assertIn("remove_node", op_types)

    def test_incremental_proposal_stale_context(self):
        """验证代码版本不一致时返回 STALE_CONTEXT。"""
        base_graph = {"mapRevision": "map_v1", "codeRevision": "rev_conflict"}
        res = generate_incremental_proposal(base_graph, "rev_old", "rev_new", {})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["errorCode"], ERR_STALE_CONTEXT)

    def test_process_deviation_controllable_and_unknown(self):
        """验证过程偏差：缺少证据返回 UNKNOWN；存在绕过返回具体偏差。"""
        graph = {
            "codeRepoId": "repo-test",
            "codeRevision": "a" * 40,
            "nodes": [
                {
                    "nodeId": "node_order",
                    "expectedProcesses": ["validate", "deduct_stock", "send_notice"]
                }
            ]
        }
        # 1. 缺少追踪数据 -> 返回 UNKNOWN
        unknown_res = detect_process_deviations(graph, [])
        self.assertEqual(unknown_res["verdict"], "UNKNOWN")

        # 2. 真实追踪显示 deduct_stock 被绕过（轨迹声明的仓库/版本与图一致）
        trace = {"called_steps": ["validate", "other_step"],
                 "codeRepoId": "repo-test", "codeRevision": "a" * 40}
        dev_res = detect_process_deviations(graph, [trace])
        self.assertEqual(dev_res["verdict"], "DEVIATION_DETECTED")
        self.assertEqual(len(dev_res["deviations"]), 1)
        self.assertEqual(dev_res["deviations"][0]["type"], "bypassed_step")
        self.assertEqual(dev_res["deviations"][0]["expectedStep"], "deduct_stock")

        # 3. 图没有可核对的仓库/版本身份 -> 无身份观察不能判一致（UNKNOWN）
        no_identity_graph = {"nodes": [{"nodeId": "node_order",
                                        "expectedProcesses": ["validate", "deduct_stock", "send_notice"]}]}
        self.assertEqual(detect_process_deviations(
            no_identity_graph, [{"called_steps": ["validate", "deduct_stock", "send_notice"]}])["verdict"],
            "UNKNOWN")

        # 4. 完整链但缺身份 / 错版本 -> 不报告 ALIGNED
        self.assertEqual(detect_process_deviations(
            graph, [{"called_steps": ["validate", "deduct_stock", "send_notice"]}])["verdict"], "UNKNOWN")
        self.assertEqual(detect_process_deviations(
            graph, [{"called_steps": ["validate", "deduct_stock", "send_notice"],
                     "codeRepoId": "repo-test", "codeRevision": "b" * 40}])["verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
