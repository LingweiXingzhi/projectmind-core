# C Convergence — Contract Manifest (W0)

契约来源: `G:/jiagou/projectmind-validation-review` @ `e43203ba6cc678e9d7726eb897d51b3acfcb9baa`
规范入口: c-readiness/ 下 C_PRODUCT_BOUNDARY / C_INPUT_OUTPUT_CONTRACT_PROPOSAL / C_ACCEPTANCE_PLAN / C_B_CODEFACTS_USAGE / C_CONTEXT_SAFETY_RULES / C_CONSUMABLE_INTERFACE。

## 产品不变式（13 条）

1. 输入 = pinned Git diff + B 声明事实 + 当前人工 Project Map + 可选 CA；输出 = `proposals / unresolved / no_proposal / limits` + 请求与事实底座追踪。`UNKNOWN` 进 unresolved，不进强 proposal。
2. 六类候选: `NODE_ADD / RELATION_ADD / RELATION_REMOVE_CANDIDATE / IMPLEMENTATION_LINK_CHANGE / NODE_REMOVE_CANDIDATE / RESPONSIBILITY_CHANGE`。每项完整字段、非空可定位 revision/path evidence、confidence、uncertainty、`status=PROPOSED`、`human_required=true`。
3. C 不写正式地图、不建议 position、不自行 accept/reject、不仲裁 CA conflict、不复制 B 声明解析、不编辑 CA registry、不接管 D worklog。职责/架构归属/关系含义 = INFERENCE；声明/路径/diff = FACT。
4. base/target 必须完整 40/64 位小写 SHA。缺 pin、HEAD、短 SHA 一律拒绝；不得从 snapshot 偷补。地图无版本身份，target SHA 不能证明地图适用。
5. compare 来源是 A/caller 的 changed_paths。Core `baseRevision / targetRevision / changes[{code,path,oldPath?}]` 经显式适配映射；C 不另建文件差异口径。只读 pinned patch/blob，不从工作树补证据。
6. 地图按 Core `{note,nodes,edges}` 接收；非空 nodes 及 title/summary/entryPoint/position/evidence 约束不得被测试替身放宽。输入保留 position；候选 proposed_change 不含 position。
7. B 事实仅含 revision/files/skipped 与声明 name/kind/line；无 import/签名/调用图/职责。所有目标事实来源验证 revision == target（含安装 B 返回值、同版本比较、空 diff）。必要 base 声明证据由 B 独立 pinned base 收集并标 base 角色。
8. changed 文件被 B skipped → HUMAN_REQUIRED unresolved；不得继续作为节点/关系强候选的事实基础。B 不可用 → limits；可运行安全 diff↔map；需 B 的新增节点进 unresolved，不虚构 code_fact。
9. 依赖信号来自实际 pinned Git diff。允许 base/target import AST 验证信号、排除字符串/docstring；不得借此重做 B 声明解析。声明未变 ≠ import 未变。
10. Context Pack 先真实 `validate_context_pack(pack, expected_revision=C 独立 pin)`。失败整包弃用，显式 DEGRADED/limits 后可无 pack 运行；"硬停止"= 停止消费该 pack，不是终止 C 服务。
11. CA 只读 current_by_scope；verified_fields 按字段判定。非现行分区、conflict/unavailable key 不进 proposal context evidence。revision 对应/PR 状态/contract shape/implementation 状态须独立 git/gh 核验；state/merged/draft 分别核对；不可用 = UNKNOWN；矛盾以独立证据为准、记录 claim_id 与双方值、pack 不再可信。
12. 相关 conflict 进 unresolved HUMAN_REQUIRED；C 不选边。未覆盖 ≠ 不存在；不解析 do_not_assume 中的数字。相同固定输入 + 固定独立观察 = 相同输出；不嵌时间戳/随机值。
13. `base==target` 先完成必需输入/事实一致性校验，再返回零 proposal，并说明 map drift 不属于本次差异判断。人工 REJECTED、同 subject/kind 且理由未变的候选遵循 F20 抑制；无交叉信号不制造人工任务。

## 收敛后单一决策路径

请求/路径/pin 校验 → Core compare 适配 → B 与 CA 入口校验 → 独立收集声明变化/import 变化/地图路径映射/目标存在性 → 按候选来源统一检查 skipped、证据、冲突、CA 准入 → 四桶输出 → 兼容字段投影。

各信号通道独立运行；任何单一通道不得因"声明没变"结束整个文件分析。结果发布只有一个出口：不做两套引擎 union，不在未完成准入检查时向旧 candidates 字段写候选。
