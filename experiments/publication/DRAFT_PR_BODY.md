## 本次要交付的行为

完成 Context Authority MVP 并修复独立红队发现的 scoped-current 静默丢失、坏 supersedes、失败 verifier 被当 current、pack/evidence/revision 不一致及消费校验缺口。现在冲突/坏图明确 HUMAN_REQUIRED，proposal/research/stale 不授权 current；提供版本化 Context Pack、Python/HTTP validator 与文本安全的 Inspector。

关联 Issue：本轮用户指定的无人值守验证/安全发布任务，无新增 Issue。
依赖的 PR / 基准提交：已有 feature branch 继承 PR #21 文档 @ff22b76966e6198b062c60fa9f0f4dbb987b027e；main @7484d44ddeac3c054ca3ba68f92293d965bb615c。PR diff 会包含该先前文档祖先，请先人工核对依赖；本轮没有更新或 merge PR21/22。B evidence 来自未合并 PR22 @0c46747147f765260bf2033f6eae40189b58ca0c，仅引用/只读，没有捆绑队友源码。

复现：python -m unittest discover -s tests -v；node experiments/validation/check_inspector.mjs；python experiments/validation/verify_frozen_inputs.py；python experiments/ca_experiment/compute_metrics.py --final。冻结 post-fix pack 固定产品提交3e12fdfebc507ff1755f9f8bcb01e67a0eac14d6；报告提交不改变该实验 revision。

## 接口和数据

C-CONSUMABLE STATUS：C_CONSUMABLE_WITH_LIMITS / YES_WITH_LIMITS。
C may consume：schema0.1、独立固定 project_revision、current_state.current_by_scope、typed current projections、known_conflicts/stale/unavailable/registry problems、非 current proposal/research/history、do_not_assume、per-claim evidence；具体 freeze/provisional/forbidden 字段见 C_CONSUMABLE_INTERFACE.md 与自有 CONTEXT_AUTHORITY_SCHEMA.md。

C must not assume：校验和/结构校验证明事实真实；cached origin/main 是实时 GitHub；OPEN/MERGEABLE 是 merged/approved；Snapshot SHA 证明地图适用；命名快照涵盖其他分支；候选可覆盖 curated/formal map。

必须按 AGENT_BOOTSTRAP 固定 repo/revision/key/scope、先校验，再回查相关原始证据/人工权限。最终完整 pack71,822B 超过既有 host POST65,536B；用 Python validator。未修改 shared app/host、MVP_INTERFACES 或正式 Project Model。C 实现、B/D 集成、统一 UI、Architecture Supervision 未在本轮实现。

## 自检结果

实际完整回归172/172 PASS ×3；55 resolver +60 pack 新 adversarial cases；100 resolve/reorder/20 pack 相同 captured-outcomes 决定性；Inspector injection/text smoke PASS。两名 fresh red-team reviewers 独立复现并修复20类 finding，原失败证据保留。

独立 judge：Raw 与修复后 CA 各60/60正确，分歧0%、unsupported/stale-as-current0；原 CA88.33% strict /3.33% disagreement 的失败 baseline 保留。冻结20问/GT不变，CDR N/A（无 unresolved-conflict 真值项）。投毒：10错误包均由独立证据纠正，6 guard rejection +4 coherent fallback；2 clean controls正确，零盲信/错误传播。15问充分性：pack-only6/8/1，证据 fallback补齐全部15问；9问必须 fallback。无统计/跨模型/任意攻击保证，允许表仅指令+read log隔离。没有把本地测试称为远端 CI。

## Project Model Impact

MINOR：只收紧 CA authority/consumer 边界，未更新正式项目模型或团队 Contract。团队需决定正式 B/C接口/empty GET约束与基准SHA；Benchmark 非 Git/no remote，独立 repo归属/可见性/URL需要人工决定，未创建 repo或塞入core。

## 交接

入口：CONTEXT_AUTHORITY_FINAL_REPORT.md、UNATTENDED_FINAL_REPORT.md、C_CONSUMABLE_INTERFACE.md、AGENT_BOOTSTRAP.md、独立 reviews 与所有冻结证据。

KNOWN LIMITS：coherent false claims/完全删掉的冲突仍需独立来源；cached main/fixed default GitHub identity；legacy缩写source要用exact live metadata/captures；task关键词路由/seedkeys/IDs provisional；append external locking未实现；快照不代表所有分支，D PR24/26/27候选未被集成/验收。无 unresolved product blocker，发布为 Draft供人工review。

HUMAN DECISIONS REQUIRED：HUMAN_DECISIONS_REQUIRED.md D1–D8。所有 main merge 等待用户明确：“已经人工审核通过，可以 merge 到 main。”

**DO NOT MERGE WITHOUT HUMAN REVIEW.** GitHub存在不等于merged，MERGEABLE不等于AUTHORIZED TO MERGE。本轮只正常push自有分支，没有approve/merge、force push、删除远端分支或改队友成果。
