# C_CONTEXT_SAFETY_RULES — C 消费 Context Pack 的行为规则(可执行版)

> 把验收 finding 转成 C 代码/流程必须执行的规则。C 不需要读红队长文;实现时逐条对照本文件。
> 每条:RISK(风险)→ C BEHAVIOR(必须的行为)→ FALLBACK(违规/异常时的动作)。

## RULE-1 校验失败 = 硬停止
- **RISK**:结构校验只保证一致性,不保证真伪;但校验**失败**的 pack 一定不可信(poisoning P02/P06 被抓)。
- **C BEHAVIOR**:使用 pack 前必须 `validate_context_pack(pack, expected_revision=<C 自己 pin 的完整 SHA>)`;抛出任何异常 → 该 pack 整体废弃,不降级消费、不部分采信。
- **FALLBACK**:无 pack 模式继续运行(diff + code_facts + 地图),输出 `limits` 注明 "context authority unavailable/unvalidated"。

## RULE-2 读 current_by_scope,不读 current
- **RISK**:multi-scope key(同 key 两个 scope 均现行)从 `current` 投影中静默消失,无任何告警(FINDING-02)。
- **C BEHAVIOR**:所有事实读取走 `current_state.current_by_scope`;`current` 只允许用作快速索引展示。
- **FALLBACK**:若发现 key 只在 `current` 出现而无 by_scope 行(非法状态),视为 pack 损坏 → 按 RULE-1 处理。

## RULE-3 部分 verified ≠ 全部 verified
- **RISK**:verifier 可能只验证 value 的部分字段(如 code_facts 只核 status/pr/head),其余字段随值透传且行级 `freshness=verified`(FINDING-03)。
- **C BEHAVIOR**:凡把 `implementation.*` claim 的值写进 proposal 依据,先打开 `evidence[].live_verification.verified_fields`;值中不在该列表的字段一律标 UNVERIFIED,不得作为 rationale 的事实支撑。
- **FALLBACK**:evidence 缺 `live_verification` → 整条按 `unverified` 处理(可引用但必须标注,且不得支撑强结论)。

## RULE-4 PR 状态三看:OPEN / draft / merged
- **RISK**:PR verifier 不读 GitHub draft 字段——`PR_OPEN` 可能是 Draft(FINDING-07;PR22 实例);"OPEN 何时合并"更不可由 pack 推断。
- **C BEHAVIOR**:凡涉及"PR 是否已合并/可否作为 main 内容/是否已交付"的判断,pack 只作起点,必须独立 `gh api pulls/<n>` 核对 state+merged+draft。
- **FALLBACK**:gh 不可用 → 结论降级为 UNKNOWN,不产出强 proposal。

## RULE-5 B 契约以实际扩展为准
- **RISK**:B 正由 PR #31 演进(移入正式目录、--no-lazy-fetch、SHA-256 测试),而 CA 的 contract claim 仍钉 PR22 README@0c46747。
- **C BEHAVIOR**:调用 B 时运行时行为以实际安装的扩展为准;契约 claim 用于理解参数与限额;唯一保留的运行时断言是 `CodeFacts.revision == target_revision`。
- **FALLBACK**:B 不可用 → C 只运行不依赖 code_facts 的阶段(diff↔地图),输出 limits 注明。

## RULE-6 校验与 digest 不证明外部事实
- **RISK**:相干伪造能通过 validator 并自带正确 digest(poisoning 5/10 穿过;P05/P10 曾被 PACK-ONLY agent 高置信度盲信)。
- **C BEHAVIOR**:对四类高影响事实——**revision 对应关系、PR status、contract shape、implementation 状态**——pack 是 authoritative starting point,不是不可质疑神谕;写进 proposal 前必须 evidence fallback(git/gh 只读核验)。
- **FALLBACK**:核验结果与 pack 矛盾 → 以独立证据为准,输出 limits 注明矛盾条目(claim_id + 双方值),该 pack 标记为"不再可信"。

## RULE-7 conflict 不可裁决
- **RISK**:CA 对无显式 supersedes 的冲突恒返回 HUMAN_REQUIRED;这是设计而非缺陷。
- **C BEHAVIOR**:`known_conflicts` 命中的 key 不得出现在任何 proposal 的依据中;相关差异落 `unresolved[]`,标注 HUMAN_REQUIRED。
- **FALLBACK**:无(不存在 C 自行选边的合法路径)。

## RULE-8 非现行分区永不入证据
- **RISK**:`proposals / research_notes / historical_sources / known_stale_sources / verification_unavailable` 中的条目代表非现行状态;混入会精确复刻 poisoning 场景。
- **C BEHAVIOR**:C 的 evidence 中 `context_claim` 条目只允许来自 `current_by_scope`(经 RULE-2/3 筛选)。
- **FALLBACK**:实现层用 allowlist 校验 evidence 来源分区,违规即断言失败。

## RULE-9 pack 覆盖 ≠ 全部事实
- **RISK**:registry 只登记 PR21/22;"pack 里没有"≠"不存在"(PR24/26/27/29/31 均不在;holdout h11–h13/h21 实证)。
- **C BEHAVIOR**:C 不得因 pack 缺失而输出"X 不存在/未发生";只能输出"pack 未覆盖,需独立确认"。
- **FALLBACK**:需要该事实时走独立查询;查不到 → UNKNOWN。

## RULE-10 do_not_assume 数字不可解析
- **RISK**:do_not_assume 计数文本与过滤后 sections 可能不一致,validator 不校验数字(FINDING-04)。
- **C BEHAVIOR**:解析 do_not_assume 只匹配固定禁令后缀(如 "OPEN does not mean merged");忽略所有数字。
- **FALLBACK**:无(纯解析约束)。

## 一览(实现为 C 内的 checklist)

| 规则 | 触发点 | 违规后果 |
|---|---|---|
| R1 | pack 载入 | 硬停止 |
| R2 | 事实读取 | 事实缺失 |
| R3 | evidence 组装 | UNVERIFIED 标注 |
| R4 | PR 状态引用 | UNKNOWN 降级 |
| R5 | 调用 B | 断言失败 |
| R6 | 高影响事实 | 证据为准 + 标记 pack 不可信 |
| R7 | conflict 命中 | 落 unresolved |
| R8 | evidence 组装 | 断言失败 |
| R9 | 缺失推断 | 只可说"未覆盖" |
| R10 | 解析 do_not_assume | 忽略数字 |
