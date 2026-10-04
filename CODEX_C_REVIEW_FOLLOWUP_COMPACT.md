# CODEX_C_REVIEW_FOLLOWUP_COMPACT — C 审计复审(仅限修复复核)

READ-ONLY reviewer(gpt-6.1-sol)。不修改/不 commit/不 push。结尾必须输出 `CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`。

## 背景

你上一轮审计 `dea111f` 给出 FAIL(2 HIGH + 5 MEDIUM)。修复 commit:**`5286697`**(当前 HEAD)。
本轮**只复核修复**——不重审 C 全量、不重读上轮已给结论的部分。

## 只读以下内容

1. 修复 diff:`git show 5286697`(含 engine/facts_adapter/diff_model 修改与新测试)
2. 现状文件(仅与 findings 对应的部分):
   - `extensions/map_proposal/engine.py` 的 `_is_high_impact_claim` 与 `_apply_context_claims`(H1/H2)
   - `extensions/map_proposal/engine.py` 的 `_handle_renamed`/`_handle_removals`/`_handle_relations`(M1/M2/M3)
   - `extensions/map_proposal/facts_adapter.py` 的 `_normalize`(M4)
   - `extensions/map_proposal/diff_model.py` 的 `static_import_count`(M3)
3. 新增测试:`tests/test_map_proposal.py` 的 `CodexRound1FixTests` 类(7 项)与更新后的 A22/A24
4. `C_V0_1_RESOLVED_SEMANTICS.md`(语义基准)

**不要读:** 其他扩展、verification/logs、README/docs、全仓扫描。

## 复核点(逐条)

1. H1:你的 validator-passing 伪造探针(implementation.code_facts,status=MERGED,bogus head,verified_fields 齐全)现在是否被拒绝附加并落入 unresolved HUMAN_REQUIRED?是否存在仍能绕过的 claim 形态(如字符串值、其他键前缀)?
2. H2:conflict 相关路由是否不再仅依赖路径子串?node-id 命中时相关 proposal 是否被移出 proposals?有无新的误伤面?
3. M1:renamed/removal 证据的 revision 绑定是否正确(旧路径绑 base,新路径绑 target)?
4. M2/M3:声明未变文件被排除;churn 不产候选;移除候选经 git show 复核(base 有/target 无)。是否有残留误报路径?
5. M4:部分 B entry(kind/line 缺失)是否已容忍?
6. M5:新增 7 项测试是否名实相符?
7. 修复是否引入新问题?

## 输出

分级 findings(仅新问题或未修复项)+ 最后一行 `CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`。
gate:无 BLOCKER/HIGH 未决 → 放行 `C_SAFE_FOR_HUMAN_REVIEW`。
