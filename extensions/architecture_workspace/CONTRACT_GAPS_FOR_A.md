# 给 A 的合同差异与协调清单

来源：2026-10-07 的 GitHub refs/打开 PR 只读核对，加上固定基线
c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db 的实际代码。

截至本次核对：33 个公开可访问 branch refs；未发现 integration/architecture-loop-v1-*。
打开 PR 中最新为 B #51，未发现 A/C/D 本轮新架构闭环 PR。
这不证明队友没有本地开发；也不把旧 PR 开着当作旧功能未集成。
公共标准里现有 MVP 格式不是 10 月 7 日 CONTRACT_V1。以下是需 A 登记的差异，不是 B 宣布合同冻结。

| 项目 | 既有接口事实 | B 已有能力 / 样例 | 所需协调及 owner |
|---|---|---|---|
| 请求上下文 | ExtensionContext 只有 repo/map_path/snapshot/compare | Gateway 校验真实 peer/Host/Origin/session/CSRF；旧 POST 禁用 | A 登记新受保护 seam/route 和会话配置，不将 JSON 自报值作为真实元数据 |
| 图数据 | legacy 节点 summary/entryPoint/position，关系 from/to/label | 职责/interfaces/evidenceIds、类型化关系、expected process/steps | A 冻结新图显示与操作合同；旧图仅显式 legacy 导入，保留旧模式 |
| 身份与版本 | 旧 Snapshot.revision 是代码 SHA；目录名不是稳定身份 | codeRepoId/mapId/workspaceId 与 codeRevision/mapRevision/mapSourceRevision/verifiedCodeRevision 分离 | A/C/D 共用字段含义和 null 规则，不把 code SHA 填成图版本 |
| C 输入 | engine.suggest_map 要求 current_map，并消费固定代码事实/CA | B graph_snapshot 的完整版本及覆盖限制 | C 完成新 bootstrap/incremental 适配；不由 B 更改 C 引擎 |
| C 输出 | 现有 canonical/legacy 候选是只读分析结果 | B 的 typed operations、CAS 与 proposalId；consumer fixture 展示选择 | C/A 登记候选 ID→多操作、局部修改及拒绝记录映射；不把夹具当实际 C 输出 |
| D 版本 | 现有 handoff.build_handoff 写 mapRevision=UNKNOWN | 不可变 version/provenance 和真实 Git 导入 | D 为新工作区增加同版包消费，保留旧 API 的 UNKNOWN；不改 handoff 现有接口 |
| 无代码规划 | 旧公共启动/扩展仍依赖人工 map | planning null SHA，confirmed_design，显式 associate_code | A 开放无地图/规划入口，C 生成设计候选，D 消费规划包 |
| 错误与命名 | 旧扩展 error:string；公共 HTTP 路由未定新 casing | WorkspaceError.as_dict 的 code/message；Python kwargs snake_case | A 冻结 JSON/HTTP 状态映射；不同入口不强行混作同一已实现合同 |
| 发布恢复 | 公共 UI 尚无新发布恢复路径 | publishing 冻结、原授权恢复、Git/数据库收口 | A 登记失败显示与令牌生命周期；不暴露私有 intent/permit/journal，不发明清库恢复 |

## A 可以直接复用的交付

- B 实现、B_CONTRACT_CANDIDATE_V1.md、A_C_D_INTEGRATION_GUIDE.md。
- `python -m extensions.architecture_workspace.smoke --test-fixture-only --output <new-absolute-directory>`。
- 生成的 CONSUMER_CONTRACT.json：17 次实际调用、四种失败、选择结果、第二 clone。
- examples/consumer-contract-fixture.json；tests/test_archloop_b_consumers.py。

## 冻结后 B 执行

1. 核对 A 指定的固定集成 SHA 和 CONTRACT_V1，登记对应差异。
2. 在 B 目录做必要适配、保留兼容说明；不修改 A/C/D owner 文件。
3. 配合实际 HTTP/UI 和 C/D 调用复验，记录新 SHA 的结果。
4. 汇总缺陷与证据给 A，维持 Draft PR，不合 main 或旧 integration。

公共文件仍由 A 独占；这个包不发群消息、不修改公共接口或正式 Model。
