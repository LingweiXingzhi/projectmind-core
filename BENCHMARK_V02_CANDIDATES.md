# BENCHMARK_V02_CANDIDATES — Context Authority 引入的可测场景（提案，不改 frozen v0.1）

> 来源：Context Authority MVP（feat/context-authority-mvp）。以下为 ProjectMind Benchmark v0.2 候选族，待另立冻结流程；frozen v0.1 的 GT/verdict 不动。

## C-A：resolver 决定性族（synthetic registry，GT 可机械构造）

1. 同 registry → 逐字节相同 CURRENT_STATE（含 registry_hash）。
2. 行序重排 → 语义等价 CURRENT_STATE（T13/T14 已是雏形）。
3. supersedes 链（A→B→C 传递）→ 全链 SUPERSEDED、current 仅剩存活者。
4. 断链 supersedes → registry_problems 显式报告且不崩溃。
5. 同 (key,scope) 双 ACTIVE 异值 → CONFLICT/HUMAN_REQUIRED；任何时间戳翻转都不改变结局。
6. 三方同值 → 折叠为一条、claim_ids 并列。

## C-B：域授权族

7. team.* 下 PROPOSAL → 注册即拒绝（显式错误）。
8. implementation.* 下 HUMAN_DECISION → 拒绝（Git SHA 不由人决定）。
9. HISTORICAL 任意域可注册但永不进 current。

## C-C：stale 检测族（verifier 注入，离线可复现）

10. verifier 值≠存储值 → 旧 STALE + auto-claim ACTIVE；auto-claim id 确定。
11. verifier unavailable → verification_unavailable 显式列出；易变事实从 current 撤下、保留 STALE provenance；不伪造值。
12. 同 key 双 claim 都过期 → 各自 STALE，仅一个 auto-claim。

## C-D：Context Pack 族

13. do_not_assume 完整性：OPEN PR/proposals/research/historical/conflicts 每类存在时必出现对应禁令（T12 扩展）。
14. evidence 可溯源：pack 中每个条目的 claim_id 都能在 evidence[] 找到 source。
15. task→domain 路由确定性：同一 task 两次生成 pack 相同。

## C-E：真实漂移回归族（复用 ProjectMind 已发生漂移，F1–F5 扩展）

16. 未来 PR #21/#22 状态变化（merge/head 变更）→ live 验证自动 STALE 旧 claim——作为 periodic regression。
17. 文档行号类漂移（新增 doc 引用 vs 代码事实）。
18. 新 PROPOSAL 注册后不出现在 current（例如 C 的 suggest_map 一旦交付，升级 CONTRACT 需显式 supersedes）。

## C-F：负面输入族（对齐 Track M 风格）

19. claims.jsonl：非法 JSON 行/缺字段/未知 type/坏 key/坏 scope/重复 id → 显式错误定位到行号。
20. handle 层：超 65536B POST 由现有 host 拒绝；未知字段、坏 action 显式失败。

## 备注

- 全部场景 deterministic、离线可测（verifier 注入），无需网络；
- 与 frozen v0.1 的关系：v0.1 测 Code Facts 的**提取正确性**；v0.2 候选测 **Context Authority 的裁决正确性与决定性**——两者正交。
