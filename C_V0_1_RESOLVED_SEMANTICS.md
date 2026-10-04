# C_V0_1_RESOLVED_SEMANTICS — C 开工前三处已知歧义的定案

- 定案时间:2026-10-04(无人值守 overnight,Phase 6;依据:OVERNIGHT_BD_C 指令 §34 + PR32 c-readiness 包)
- 效力:本文件是 C v0.1 实现与验收的行为规范;与 C_IMPLEMENTATION_SEQUENCE / C_ACCEPTANCE_PLAN 冲突处以本文为准。

## 歧义 1:无 B 里程碑 vs F1 要求 code_fact evidence

**原始矛盾**:C_IMPLEMENTATION_SEQUENCE 的最小闭环(Stage 0+1+4)声明 evidence 只用 git_diff kind、不依赖 B;而 C_ACCEPTANCE_PLAN F1 期望 evidence 含 git_diff+code_fact。

**定案**:
1. C 正式 MVP **不复制 B**:任何路径下都不创建自己的声明提取器,不伪造 code_fact evidence。
2. 完整 F1(带 code_fact)在 **B 可用时**验收(本次集成分支已含 B,完整 F1 为准)。
3. **无 B 降级路径**(B 扩展缺失/调用失败):C 继续运行,但
   - 相关 proposal 的 evidence 只允许 git_diff/map_node kind,并追加 uncertainty 条目 "code facts unavailable — declaration-level evidence missing";
   - limits 追加 "code facts unavailable";
   - 无法定位 (revision, path) 的候选一律落 unresolved(NEEDS_HUMAN_REVIEW),不生成强 NODE_ADD。
4. 该定案记为验收 fixture **F1'(无 B 降级形态)**,与完整 F1 并存。

## 歧义 2:P05 结构无效 vs 相干伪造必须分为两个 fixture

**原始矛盾**:poisoning 的 P05 是"过校验的相干伪造",与"被 validator 拒绝的包"是两类威胁;旧计划只有一个 P05 场景。

**定案**(两个独立 fixture,两套防线):
1. **C-A25(structural-invalid pack)**:pack 未通过 `validate_context_pack` → **整体拒绝该 pack** → C 进入 `DEGRADED_NO_CONTEXT` 继续运行(见歧义 3)。防线 = RULE-1 硬停止消费。
2. **C-A24(structurally valid but poisoned pack)**:参照 P05(契约形状整体回退)/P10(状态伪造成 MERGED)构造相干伪造包,validator 通过。防线 = RULE-6 evidence fallback:
   - C 对将写入 proposal 依据的 context_claim,凡涉高影响事实(revision 对应、PR status、contract shape、implementation state),必须与 C 自己的独立信号(Git diff、B facts、current map)交叉核对;
   - 矛盾 → 该 claim 不得进入 evidence,limits 记录矛盾(claim_id + 双方值),相关差异落 unresolved(HUMAN_REQUIRED);
   - C 的核心 rationale 恒为 git_diff/code_fact/map_node 三类可回放证据,context_claim 只作补充。

## 歧义 3:invalid context pack 的整体执行语义

**原始矛盾**:RULE-1 只说"硬停止",未定义停止范围。

**定案**(三句,实现与验收一致):
1. **该 pack 整体拒绝**:validate 失败的 pack 的任何字段都不得被 C 使用(不降级采信、不部分消费)。
2. **C 可以继续运行**:进入 `DEGRADED_NO_CONTEXT` 模式 —— 输出照常(proposals/unresolved/no_proposal/limits),但 evidence 中不得出现任何 context_claim,limits 必须注明 "context authority unavailable/unvalidated"。CA 是增强不是依赖锁死(C_CONTEXT_AUTHORITY_USAGE 降级路径)。
3. **缺必要 context/evidence 的高影响 proposal 一律 unresolved**:凡差异需要 CA 侧事实才能定案、而 pack 又被拒绝/缺失的,落 unresolved(NEEDS_HUMAN_REVIEW),不得凭其余信号编造强结论。

## 由此固化的 C v0.1 模式常量

| 模式 | 触发 | 行为 |
|---|---|---|
| `FULL` | pack 提供 + validate 通过 + expected_revision 匹配 | context_claim 可作补充 evidence(经 RULE-2/3/6/7/8 筛选) |
| `DEGRADED_NO_CONTEXT` | pack 缺失 / validate 失败 / CA 不可用 | 零 context_claim;limits 注明;高影响差异落 unresolved |
| pack 矛盾 | FULL 模式下 claim 与独立信号冲突 | 该 claim 剔除 + limits 矛盾记录 + 相关差异 unresolved;C 不中断 |

## 验收挂钩

- F1' 与 F1 并存(见歧义 1)。
- C-A24 / C-A25 拆分(见歧义 2)。
- 每个降级用例必须断言:limits 含 DEGRADED 原因、evidence 无 context_claim、输出仍确定可复现。
