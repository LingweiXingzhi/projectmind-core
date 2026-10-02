# CONTEXT_AUTHORITY_AUDIT — Source Audit（只读）

> 2026-10-02。审计人:Context Authority MVP 会话。本文件只分类,不修改任何原文件。
> 验证方式:本地 git 只读 + gh api 只读 + 直接读文件。凡标 VERIFIED-NOW 的均有当日实测。

## CURRENT(当前真实状态,VERIFIED-NOW 2026-10-02)

| 事实 | 值 | 证据 |
|---|---|---|
| core main | `7484d44ddeac3c054ca3ba68f92293d965bb615c` | gh api commits/main（E1） |
| PR #21 | OPEN @ `ff22b76…`（docs/v1-source-of-truth-cleanup，携带 V1 角色文档） | gh api pulls/21（E1） |
| PR #22 | OPEN / MERGEABLE @ `0c46747147f7…`（B/Code Facts 交付） | gh api pulls/22（E1） |
| core 工作区 | 检出 PR #21 分支，clean | git status（E1） |
| V1 角色映射 | A=Core/Integration, B=Code Facts, C=Map Proposal, D=Handoff | 工作区 COLLABORATION_CONTRACT.md（已验证在文件内,负责人 2026-09-30 确认,HUMAN_DECISION） |
| main 可见扩展 | 仅 `extensions/__init__.py` + `extensions/project_summary/`；**B/C/D 业务目录不在 main** | git show main -- extensions/（E1） |
| 扩展接口 | 已实现（PR #20 合入 main）：extensions/<name>/extension.py + handle；GET/POST 路由；≤65536B POST；同进程多线程 | EXTENSION_INTERFACE.md + extension_host.py 代码（E1/E2） |
| main 测试 | tests/test_app.py(7) + tests/test_extensions.py(5) = 12 | 文件盘点（E2） |
| 地图版本身份 | 无（本地文件,无 digest/commit 身份）——文档已承认的缺口 | MVP_INTERFACES.md 共同词汇（E3） |
| B/Code Facts | PR #22 OPEN,**未 merge**;交付 README 内含 B 契约(五种 kind/词法限定名/行号语义/skipped 语义) | gh api + PR 树只读（E1/E3） |

## STALE(存在但已失真,不能当 current)

| 材料 | 失真点 | 证据 |
|---|---|---|
| main@7484d44 的 COLLABORATION_CONTRACT | 仍是旧角色映射(A=集成与体验…) | git show main:…(T3 reviewer CONFIRMED,E1) |
| MVP_INTERFACES PROPOSED CodeFacts 示例(main) | 裸名+单一 kind;build_snapshot 行号 106(实际 109) | T3 reviewer CONFIRMED（E1/E2） |
| FINAL_BENCHMARK_REPORT §11 "B/C/D NOT IMPLEMENTED" | PR #22 已存在并经 686 单元评测 | benchmark 仓库（E1/E2） |
| NEXT_STEPS.md 条目 1 | 实际已用专用适配器完成评测 | benchmark 仓库（E2） |
| AGENT_STANDARD/TEAM_SOP "门禁未配置"(as-of 2026-09-30) | 今日状态未复核(本地不可验) | 时效性未知,列 UNKNOWN-STATE |
| CLAIM_REGISTER "V3" | 无任何现存文档定义 V3 内容 | T2 reviewer（E2） |
| benchmark HOLDOUT_FINAL_REPORT 数字 | 60/22 已被 150/50 取代(本会话已产出新报告) | 新旧 JSON 对比（E1） |

## HISTORICAL(仅历史,禁当现行)

- V2 角色映射(MVP_PROPOSAL,已标 SUPERSEDED);V3(仅有引用,内容缺失)
- main 旧角色映射文本(合入 V1 前)
- 2026-09-29 mvp-audit(7/7 测试数、历史 SHA 3b9c8c6/8a6a19c/8bd8005)
- Master Spec v0.1 草稿(user.py/cache.py/database.py 虚构示例)
- PROJECT_ANALYSIS §4 的时点判断("没有产品代码")

## PROPOSED(提案,非现行)

- CodeFacts/MapProposal/Handoff 业务函数(MVP_INTERFACES PROPOSED 节);B 已以 PR #22 形态交付待审
- mapSource {kind, digest, confirmedForRevision} 地图身份补丁
- review_draft AI 审查接口
- 本任务:Context Authority MVP(用户指令,HUMAN_DECISION 已给出)

## CONFLICTING(同 key 无 supersedes 的 ACTIVE 对立)

本轮审计发现的真实冲突(全部有明确权威来源,无需猜测):
1. **roles.v1**:main 文本(旧) vs PR #21 文本(V1) vs 用户当前决定(V1)——用户指令已裁决 V1;旧文本属 HISTORICAL-stale,非未决冲突(有 HUMAN_DECISION supersedes)。
2. **B 交付状态**:"NOT IMPLEMENTED"(旧报告) vs "PR #22 OPEN"(实测)——VERIFIED_FACT 实测优先;旧报告 HISTORICAL。
3. **code_facts 形状**:MVP_INTERFACES PROPOSED 示例(裸名/单 kind) vs PR #22 交付契约(五 kind/限定名)——PR 为实现事实;接口文档待更新(团队决策,列 HUMAN_DECISIONS_REQUIRED)。
→ 结论:没有必须 NOW 由人裁决的未决冲突;但 #3 的**文档更新**需要团队决策(不自动修改正式文档)。

## UNKNOWN

- GitHub Ruleset/门禁今日是否已配置(本地不可验)
- model 侧 PR #1 状态(登记截至 09-30)
- 队友 PR 未来更新(PR watch 周期外)

## 审计对实现的三条约束

1. seed claims 必须区分:HUMAN_DECISION(用户已定)不得被 main 旧文本覆盖;VERIFIED_FACT(可变 Git/PR 状态)必须可被 live 校验刷新为 STALE+新 ACTIVE;
2. PROPOSAL/RESEARCH/HISTORICAL 永不进 current;
3. 形状冲突(#3)不自动裁决——进 HUMAN_DECISIONS_REQUIRED,等团队更新接口文档。
