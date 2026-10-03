# CONTEXT_AUTHORITY_MVP_REPORT

> 分支:`feat/context-authority-mvp` @ `c6e5532`（独立 worktree `G:\jiagou\projectmind-context-authority`）。
> 这是 ProjectMind 产品能力，不是 Benchmark、不是 Skill、不是 AI 总结器。
> 人类决定（HUMAN_DECISION，用户 2026-10-02 指令）：先做 Context Authority，再继续 C/Map Proposal。V1 角色映射 A=Core/Integration、B=Code Facts、C=Map Proposal、D=Handoff 为唯一现行分工。

## 1. 问题是什么

不同 Agent 因读到不同材料（main 旧文档 vs 未合并 PR vs 新旧 benchmark 报告 vs research vs 历史 proposal），从任务开始时就持有**不同的项目基础事实**——Agent A 说"B 还是 proposed"，Agent B 说"B 已实现"。这不是思考差异，是**事实输入分叉（FACTUAL CONTEXT DIVERGENCE）**。

## 2. 为什么会事实分叉

材料天然多版本：main 落后于 PR；报告有时点性；研究≠契约；历史 proposal 仍躺在仓库里。而"哪个是真的"此前依赖每个 Agent 自行判断——判断依据（读到了什么）不同，结论就分叉。证据：本轮 Track T 文档一致性评审在 49 个文档里找到 25 条重要漂移（main 旧角色映射、行号 106 vs 109、"B NOT IMPLEMENTED" 等）；§23 的实验在 Raw Material 条件下实测了分叉率。

## 3. 数据模型

Append-only **claims.jsonl**（唯一人工可写入口）→ deterministic **resolver** → **CURRENT_STATE.json**（派生视图，禁止手工维护第二份）→ **Context Pack**（按任务选取）。不建 SUPER_MASTER_DOCUMENT——那只会产生新的漂移。

## 4. claim type / state

type 六种（注册表存储）：VERIFIED_FACT / HUMAN_DECISION / CONTRACT / PROPOSAL / RESEARCH / HISTORICAL。
state 四态（**resolver 派生**，不存储）：ACTIVE / STALE / SUPERSEDED / CONFLICTED。
RESEARCH 与 STALE 是正交维度（性质 vs 现行有效性），不混用。

## 5. resolver 规则（确定性，无 LLM，无时间戳优先）

1. supersedes 边 → 被引用者 SUPERSEDED（保留溯源）；断链 → registry_problems 显式报告；
2. 同 (key,scope) 组内存活 claim：value 全等 → 折叠一条 ACTIVE；不等 → 全体 CONFLICTED + HUMAN_REQUIRED，**绝不自动选赢家**；
3. 时间戳不参与任何比较（测试 T8 专门锁死"新时间戳不赢"）；
4. VERIFIED_FACT + 已注册 live verifier → 存储值≠实测值 → 旧 claim STALE + 确定性 auto-claim ACTIVE；verifier 不可用 → 显式列入 verification_unavailable，不伪造；
5. current 白名单：仅 VERIFIED_FACT / HUMAN_DECISION / CONTRACT；PROPOSAL→proposals、RESEARCH→research、HISTORICAL→historical，永不混入。

## 6. conflict 规则

见上 2。`{status:"CONFLICT", resolution:"HUMAN_REQUIRED"}`；Context Pack 的 do_not_assume 明确告知 Agent"不得自行选边"。

## 7. stale detection（轻量）

三个 live verifier（main_head=本地 git；pr_21/pr_22_head=gh api 只读）。存储的 PR head ≠ 实测 head → 旧 STALE + 新 ACTIVE。文档型 stale（如行号 106→109）以 HISTORICAL claim + VERIFIED_FACT 对比建模，不自动修改正式文档。

## 8. CURRENT_STATE.json / 9. Context Pack / 10. API

见 docs/standards/CONTEXT_AUTHORITY_SCHEMA.md（结构、白名单、严格键校验、≤65536B POST、GET state/claims/conflicts、POST resolve_state/context）。

## 11. UI inspector

`extensions/context_authority/index.html`：CURRENT 表 / CONFLICT ⚠ / STALE ⚠ / PROPOSALS ○ / RESEARCH ○ / HISTORICAL ○ / VERIFICATION UNAVAILABLE；点击字段看 claim_id+source。纯静态页，无拖图（架构图留给 Project Map）。

## 12. Agent Bootstrap

`AGENT_BOOTSTRAP.md`：8 条使用规则（load pack → current 为起点 → 不升级 PROPOSAL/RESEARCH → OPEN≠merged → 不用 stale/historical → conflict=HUMAN_REQUIRED → 沿 evidence 深挖 → 可不同意 proposal 但不得改写 verified facts）。

## 13. tests

`tests/test_context_authority.py`：**32 项全绿**（T1–T18 规格测试 + F1–F5 真实漂移 fixture + §28 冲突流 + §29 stale 流 + handle 层严格键校验）。回归：core 现有 12 测试 + 32 新增 = **44/44 PASS**；ExtensionHost 正常发现扩展。

## 14. real drift fixtures（F1–F5，全部来自本项目真实历史）

F1 旧角色映射 vs V1（supersedes 链）✓；F2 旧 B 接口形状 vs 交付契约（五 kind/限定名）✓；F3 "NOT IMPLEMENTED" vs PR #22 OPEN ✓；F4 行号 106 vs 109 ✓；F5 research 建议不得渗入 contract ✓。断言含"旧值不出现在 current 的 JSON 里"。

## 15–19. Agent 一致性实验

见 AGENT_CONTEXT_EXPERIMENT_REPORT.md（20 问 × Raw Material 3 agents × Context Authority 3 agents；指标：factual disagreement rate / ground-truth accuracy / unsupported assumptions / stale-source usage / conflict detection；原始数据 questions.jsonl、ground_truth.jsonl、raw_agent_runs/、context_agent_runs/、judgments.jsonl、metrics.json）。

## 20. 当前限制

1. live verifier 仅覆盖 3 个易变 key；其余 VERIFIED_FACT 依赖注册时的 verified_at；
2. 冲突检测按 (key,scope) 精确匹配——语义相同但 key 写法不同的漂移需人工归 key；
3. claims.jsonl 的人工追加无审核流（v0.2 可挂 PR 流程）；
4. 实验为单格 n=3 的缩比实验（方向性结论）；
5. task→domain 关键词路由是确定性的浅匹配（够 MVP；不做语义检索）。
