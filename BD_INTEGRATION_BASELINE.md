# BD_INTEGRATION_BASELINE — B+D 集成基线定案

- 定案时间:2026-10-04(无人值守 overnight,Phase 0)
- 证据方式:`git fetch origin` + `git ls-remote`(实时)+ ancestry 实测

## CORE_BASE_SHA

**`7484d44ddeac3c054ca3ba68f92293d965bb615c`**(main tip,实测 commit:"Merge pull request #20 from LingweiXingzhi/feat/19-extension-seams")

### 定案理由(最小、可解释)

1. B(PR31 head `80e091ac`)与 D(PR27 head `8f00be38`)的 merge-base 均为 main `7484d44`——两支都直接基于 main,集成分支从 main 出发即覆盖两支的共同祖先。
2. PR21(`docs/v1-source-of-truth-cleanup` @ `ff22b76`)是 main + **1 个纯文档 commit**(README/standards/audit 文档,43 行增量;实测 `--stat`),且实测**不是** B31/D27 的祖先(NO/NO)。按"只使用真正需要的产品 baseline,不重复 merge"原则,B+D 功能集成不需要 PR21;PR21 独立走自己的 PR,不随本集成携带。
3. 不把当前 worktree 检出分支(`feat/handoff-continuity`)当 baseline——baseline 一律以 SHA 表达。

## 集成分支与顺序

- worktree:`G:\jiagou\projectmind-integration-bd`(新建,不污染既有 worktree)
- branch:`integration/bd-v1`(创建前实测本地/远端均不存在,无覆盖)
- 顺序:从 `7484d44` 建分支 → **先 merge B_DELIVERY_HEAD(PR31 `80e091ac`)→ 再 merge D_DELIVERY_HEAD(PR27 `8f00be38`)**。两支改动集实测零交集(见下),B 先 D 后与反向等价,按指令默认顺序执行;不 squash,保留历史。
- 改动集交集实测(comm -12):**空**。B31 只新增 `extensions/code_facts/*` + `tests/test_code_facts.py`;D27 只新增 `extensions/handoff|continuity|worklog/*` + 3 个测试文件。预期零冲突。

## 基线 SHA 速查(全部 2026-10-04 实测)

| 角色 | ref | SHA |
|---|---|---|
| CORE_BASE | main | `7484d44ddeac3c054ca3ba68f92293d965bb615c` |
| B_HEAD | PR #31 | `80e091acefd278fda03e188a125147b0aa5eedc5` |
| D_HEAD | PR #27 | `8f00be38532f3f5e9823aec8cbf430038cc9ff4b` |
| CA(后续 C base 用) | PR #29 | `9ea23491d1849f21bad9f60c1c1ca8df55bb5936` |
| (不纳入)PR #21 | docs | `ff22b76966e6198b062c60fa9f0f4dbb987b027e` |

## Git 安全约束(全程有效)

NO MAIN MERGE / 不 push main / 不 force push / 不 rebase-reset 共享分支 / 不改 PR22、24、26、27、29、31 原分支 / 只在 `integration/bd-v1` 及后续新建分支上提交。
