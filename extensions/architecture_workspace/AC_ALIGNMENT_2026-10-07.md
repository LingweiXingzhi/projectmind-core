# 当前 A/C 合同对照与接线要求

历史记录：本文件保留 2026-10-07 比较。当日后的 A803c 已增加真实 B Gateway/版本接线
和 C 函数转换；最新核验见 CONTINUATION_DELIVERY_2026-10-08.md，不沿用旧的“未接线”结论。

只读核验来源：GitHub 固定树，均未截断；未改其他成员分支。
A/integration：b75ad820e0d31e3dadf842b414f6950b5aa46102。
C：55ea6466583d98e0f466e5d4055922ef4aeecb12。
main：7484d44ddeac3c054ca3ba68f92293d965bb615c；旧 integration：c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db。

[A 合同](https://github.com/LingweiXingzhi/projectmind-core/blob/b75ad820e0d31e3dadf842b414f6950b5aa46102/docs/standards/ARCHLOOP_CONTRACT_V1.md)
标为 CONTRACT_V1_DRAFT；
[C 候选样例](https://github.com/LingweiXingzhi/projectmind-core/blob/55ea6466583d98e0f466e5d4055922ef4aeecb12/extensions/map_proposal/CONTRACT_V1_SAMPLE.md)
待 A 登记。两者均不能当已批准的共同合同。

## 可见的新进度

现在已有 integration/architecture-loop-v1-ZCODE-ARCH-20261007-130829-60B 与 A 的工作台分支，
C 已新增 candidates.py。此前“33 refs/未发现新集成分支”的文档是当时核对记录，已不代表当前状态。
不据远端推断队友本机工作完成程度。

## 需要统一的字段

| 项目 | A 草案 | B 当前候选 | 处理要求 |
|---|---|---|---|
| 仓库身份 | root+remote 的摘要 | 登记 origin 身份（无 remote 为本机路径） | 克隆换路径后不能直接等同；统一来源登记 |
| 图版本 | maprev-40hex 图摘要 | sha256:64hex 正式包语义摘要 | A 草稿摘要可保留为候选 hash，不能替换 B 正式版本 |
| 草稿 CAS | 字符串修订 | 正整数 draftRevision | 由适配器持久对应，不从字符串推断 B 修订 |
| 节点 | summary/status/provenance/assumptions/entryPoints | responsibility/implementationStatus/稳定 interfaces/evidenceIds | 不能丢弃 provenance/假设，确认设计不等于实现完成 |
| 过程 | 节点内 process，字符串 branches/next | 全局 expected processes、结构化分支/condition/allowedFailures | 需明确无损映射，歧义内容拒绝 |
| 关系 | 无稳定 edge ID；expected_sequence | 稳定 ID；expected_order | 类型可对应，ID 必须生成后保留 |
| C 节点 | nodeId/role/expectedProcesses | id/responsibility/processes | 第三种形状，不能冒充相同 schema |
| C 操作 | update_node；可能只给 file+evidence_refresh | node.update +固定目标+typed changes | 没目标不可猜节点，按固定证据匹配后由 C/A 形成明确操作 |
| 错误 | BAD_REQUEST/VALIDATION_FAILED 等 | 稳定 WorkspaceError code/message | A 显式映射并保留原原因 |

C 函数为 rule_based，不证明真实模型推理。它未强制完整 SHA/登记 repo identity，B 必须独立核对。
C 自认知候选绑定旧 c3d 基线却声明新 candidates.py 的实现：不能把这个绑定当新文件已存在的证据。
目录路径如 extensions/handoff/ 不能直接当 B 的固定提交文件证据。

## A 的真实调用缺口

A app.py 探测 extension POST action=contract_info/contract=CONTRACT_V1，
收到精确合同名才注册；archloop/adapters.py 注册 {kind,call} 并传 call(action,payload)。
A archloop/service.py 当前自己保存草稿，只有发布调用 B publish_reviewed_graph，
传 workspaceId/mapRevision/graph/decision/actor/reason/proposalId。
缺少 B draftId、整数 CAS、baseMapRevision、coverage、预览摘要、有效会话与原授权。

A 的写 guard 校验 loopback Host，拒绝不匹配 Origin，但缺省 Origin 可通过；
当前没有 B 所需 session/CSRF 绑定。actor 是声明，不能单独作为 B 发布权。

A 需让真实 handler 取得 peer/Host/Origin/cookie/CSRF，再调用 UserWorkspaceAPI；
草稿实际治理统一委托 B 或先冻结明确的双存储/修订映射，不能直接把 A graph 标成 B 已发布。
B 原 extension 所有 POST 仍拒绝；本轮不伪造 contract_info=CONTRACT_V1 成功。

## C 的真实入口缺口

candidates.py 有 bootstrap/incremental/nl-correction/process-deviation 四个只读函数，
但 extension.py 仍分发旧 engine.suggest_map，未实现 A 期待的 archloop_contract_info/correction_preview。
C 需接自己 dispatch 并提交统一候选/context/typed operations，保留未知项。
B validateProposal 返回明确校验范围；patch 的引用/证据与选择后的整体图在原子保存时最终校验。
C 校验不创建草稿或正式版本。

## D 与负责人接手

D 从授权 CollaborationAPI 导出固定 version/provenance/coverage/limits；
由 A 受控导入实际登记的架构 Git 包，申请中的核查 SHA 不当事实。
B 的原候选完整离线追溯和跨会话发布恢复方案需共同冻结。
新 T01–T28、实际公共工作台与真实 C/D 联调尚未执行；不报告 INTEGRATED/D_VERIFIED/AUDIT PASS。

本文件是具体协调清单和证据，无自动群消息、无正式 Model 批准。
