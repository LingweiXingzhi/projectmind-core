# Role C: CONTRACT_V1 候选输入输出与错误样例

供 Role A 登记为全局 CONTRACT_V1 的候选提案与偏差分析规范。

## 1. 核心只读接口签名 (C 导出)
- generate_bootstrap_proposal(context: dict) -> dict
- generate_incremental_proposal(base_graph: dict, base_code_rev: str, target_code_rev: str, facts: dict) -> dict
- generate_nl_correction_patch(base_graph: dict, selection: dict, prompt: str) -> dict
- detect_process_deviations(graph: dict, observed_traces: list) -> dict

## 2. 统一 Canonical Operation Schema
所有返回均包含稳定的 proposalId、操作清单以及变更对比，严守 no_map_write 只读约束：

{
  "proposalId": "prop_20261007_001",
  "kind": "rule_based",
  "status": "ok",
  "baseMapRevision": "map_rev_001",
  "targetCodeRevision": "c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db",
  "operations": [
    {
      "op": "add_node",
      "nodeId": "node_auth_service",
      "data": {
        "title": "认证服务",
        "role": "处理用户登录与令牌签发",
        "status": "implemented",
        "evidence": [
          { "kind": "source_symbol", "path": "auth/service.py", "symbol": "login" }
        ]
      }
    }
  ],
  "confidence": 0.85,
  "warnings": []
}

## 3. Bootstrap 样例 (无代码 planning 模式)
在无代码规划模式下，codeRepoId 与 codeRevision 为 null，依据为需求 ID：

{
  "workspaceId": "ws_plan_001",
  "mode": "planning",
  "codeRepoId": null,
  "codeRevision": null,
  "graphCandidate": {
    "nodes": [
      {
        "nodeId": "plan_node_payment",
        "title": "支付网关接入",
        "role": "对接第三方收单",
        "status": "planned",
        "evidence": [
          { "kind": "user_requirement", "id": "req_01", "detail": "需支持微信与支付宝" }
        ]
      }
    ]
  }
}

## 4. 机器错误码字典 (Machine Error Codes)
- STALE_CONTEXT: 提供的 baseMapRevision 或 baseCodeRevision 已经过时或与当前分支不相容。
- EVIDENCE_MISMATCH: 候选关联的源码证据或符号在目标代码 SHA 中无法定位。
- REVISION_CONFLICT: 提交对比的基线与目标版本身份错误。
- UNCONFIGURED: 未配置外部大模型环境，已安全降级至规则引导。
