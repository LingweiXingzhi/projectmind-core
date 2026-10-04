# CODEX_C_REVIEW_COMPACT — C / Map Proposal 集中审计(紧凑输入)

你是 READ-ONLY INDEPENDENT REVIEWER(gpt-6.1-sol,normal reasoning)。
不修改/不 commit/不 push/不 merge。结尾必须输出 `CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`。

## 背景与基线

- 分支链:main `7484d44` → integration/bd-v1(B+D 集成,你的三轮审计最终 PASS_WITH_LIMITS @ a71c508)
  → integration/bd-ca-c-base(merge CA PR#29 @ 9ea2349)→ **feat/map-proposal-mvp @ dea111f(本轮对象)**。
- C 专项测试 38/38;全仓 284 项 = 282 PASS + 2 项 PR31 既有 Windows 环境限制(失败集 md5 与基线一致)。
- B/D/CA 的实现你此前已审过,本轮**不需要**重审它们;只在与 C 的接缝处必要时抽查。

## 范围纪律(只读以下内容,不全仓扫描)

1. `C_V0_1_RESOLVED_SEMANTICS.md` — 三处歧义定案(实现须与之相符)
2. `C_MVP_FINAL_REPORT.md` — 实现方声明
3. C 源(全部):`extensions/map_proposal/model.py`、`diff_model.py`、`facts_adapter.py`、
   `ca_adapter.py`、`engine.py`、`extension.py`、`index.html`
4. C 测试(全部):`tests/test_map_proposal.py`
5. 契约参照:`C_ACCEPTANCE_PLAN.md` 与 `C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md` 在
   `G:\jiagou\projectmind-validation-review\c-readiness\`(如沙箱内不可见,以仓库内
   `C_V0_1_RESOLVED_SEMANTICS.md` 与 `extension.py` 的 SCHEMA_DOC 为准)
6. 边界参照:与 B 的接缝 = `extensions/code_facts/facts.py` 的函数签名与 README;
   与 CA 的接缝 = `extensions/context_authority/context_pack.py` 的 build/validate 签名(仅在需要时抽查)
7. `git diff integration/bd-ca-c-base..HEAD --stat`

**不要读:** verification/logs 原始日志、其他扩展全文、benchmark、历史文档。

## 必答 10 问(来自任务规范)

1. C 是否越权修改地图(任何写入/position/自动 accept)?
2. C 是否重复实现 B(声明解析/依赖图)或充当 CA(事实仲裁)?
3. C 是否错误信任 CA(validate 绕过、current 误用、conflict 选边、digest 当真相)?
4. conflict 是否一律 HUMAN_REQUIRED 落 unresolved?
5. evidence 是否可追溯(每条 proposal ≥1 条 (revision,path) 可定位;context_claim 只作补充)?
6. false positive 防线是否真实(comment/format/helper/test-only/generated/同职责不建节点)?
7. acceptance 是否真正通过(F1–F20 与 C-A21..A30 的测试是否名实相符,有无造绿)?
8. 实现方是否通过改 expected/断言来造绿(测试与实现是否互相迁就)?
9. 是否破坏 B/D/CA/Core(接缝处回归面)?
10. 当前分支是否达到 `C_SAFE_FOR_HUMAN_REVIEW`?

## 输出

- 逐条结论(引用实际证据)。
- findings 按 BLOCKER/HIGH/MEDIUM/LOW 分级。
- 最后一行:`CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`
