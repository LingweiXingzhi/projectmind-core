# HUMAN_DECISIONS_REQUIRED — Context Authority MVP 发现的待决事项

> 格式：Claim key / Source A / Source B / Why conflict / What decision is needed / Impact。
> 本轮 resolver 运行结果：**注册表内 0 个未决冲突**（conflicts=[]）。以下是审计发现的**文档级**待决事项——resolver 无法自动解决，因为它们需要团队更新正式文档或宣布决定。

## D1

- **Claim key**: `contract.code_facts_shape`（文档层）
- **Source A**: `docs/standards/MVP_INTERFACES.md` PROPOSED 示例（main@7484d44）：裸名 + 单一 kind:"function" + line 106
- **Source B**: PR #22 交付 README（0c46747）：五种 kind、词法限定名、line=def 行、skipped 语义
- **Why conflict**: 接口文档的交换形状与已交付实现契约不一致；实现者/验收者按文档走会违约
- **What decision is needed**: 团队确认把交付契约形状回写 MVP_INTERFACES（PROPOSED 节与实现对齐）
- **Impact**: 低-中（B 实现已交付且自洽；风险在后续 C/D 按旧文档开发）

## D2

- **Claim key**: `team.roles.v1`（发布状态）
- **Source A**: main@7484d44 的 COLLABORATION_CONTRACT（旧映射文本）
- **Source B**: PR #21（V1）+ 用户 2026-09-30 决定
- **Why conflict**: V1 只存在于未合并 PR；main 合并前，读 main 的 Agent 会看到旧映射
- **What decision is needed**: 审核并合并 PR #21（用户决定时机）
- **Impact**: 中（model 侧所有"现行职责"链接在合并前都读到旧文本）

## D3

- **Claim key**: `implementation.team_approval`
- **Source A**: 无（无正式基线宣布）
- **Source B**: COLLABORATION_CONTRACT："main 仅为候选基线，MERGED≠TEAM APPROVED"
- **Why conflict**: 团队尚未宣布正式基准 SHA；四个角色理论上仍应等待
- **What decision is needed**: 团队人工验收并宣布正式 main 基准完整 SHA
- **Impact**: 中（影响所有人开工基线与 Context Authority 的 baseline claim 更新）

## D4

- **Claim key**: `contract.mvp_interfaces_build_snapshot_line`（示例漂移）
- **Source A**: MVP_INTERFACES 示例写 106
- **Source B**: app.py 实际 109（工作区）
- **Why conflict**: 示例用真实标识符+已漂移行号，易被当可核查事实引用
- **What decision is needed**: 改合成名或更新行号（一行级修复）
- **Impact**: 低

## D5 — Benchmark 发布目标

- 本地 `projectmind-benchmark` 不是 Git repo，没有 configured remote。
- 用户需决定独立 GitHub repo 的归属、可见性和完整 URL；本轮按 case C 只准备 publication plan / manifest，未初始化或创建 repo。
- 不影响 CA 自有 feature branch 的验证与 Draft PR 发布。

## D6 — 来源认证与消费者接入

- `validate_context_pack` 证明结构与消费者 revision 一致，不能认证 coherent false claims 或被完整删除的冲突。
- C 接入必须先固定 revision、key/scope，再回查相关原始证据。完整 live seed 超过 65,536-byte POST cap，需使用 Python validator。
- 当前 default GitHub project identity 固定为本项目；多项目配置、并发 registry append 锁、语义别名等属于后续工作，未在本轮扩大实现范围。

## D7 — 正式接口边界仍需团队裁决

- B 原型的空 GET `paths`、路径边界行为等可从指定源码观察；正式跨团队接口没有因此被本轮修改。
- D 的远端 PR24/26/27 候选已出现。本轮只读；其存在不代表已合入 main、完成验收或已获团队批准。C/D 的 NOT_IMPLEMENTED claim 仅约束已记录的 main/PR21/PR22 树，其他分支 UNKNOWN。
- D1–D4 是待团队处理的文档/基线问题，不是本轮 registry 的 unresolved conflict，也不授权 CA 自动覆盖正式文档。

## D8 — Merge 许可

- 本轮仅允许自有 branch 的正常 push 与 Draft PR。所有 main merge 均等待用户明确说：**“已经人工审核通过，可以 merge 到 main。”**
- PR #21、PR #22 及本轮 Draft PR 的 mergeability 不构成该许可。本轮未 approve 或 merge 任何 PR。
