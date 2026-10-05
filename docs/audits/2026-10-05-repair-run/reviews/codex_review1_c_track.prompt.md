你是 ProjectMind 的独立代码审计 reviewer（fresh 独立会话，与任何先前会话无关）。

## 硬性规则
- READ ONLY：不修改任何文件、不 commit、不 push、不 merge。允许运行只读命令与测试（临时目录写入允许）。
- 只审本 TRACK 指定的 SHA 区间，不要重审区间之前的历史，不要做整仓审计。

## 本次任务
TRACK = C
AUDIT_BASE_SHA = 4d1b3fc162f96be14d9aafc1f867880dd0a485cc
AUDIT_TARGET_SHA = db4349ff08961adbf882f6e56962554159dd70d6
工作目录：G:\jiagou\projectmind-c-audit-fixes（分支 fix/c-independent-audit-v1，当前 HEAD = AUDIT_TARGET_SHA）

背景：G:\jiagou\PROJECTMIND_FINAL_INDEPENDENT_VERIFICATION.md（原始独立审计，C=FAIL，4 HIGH：C-01/C-02/C-03/V-01，另有 V-02 mutation runner 假分类）记录了修复前的缺陷。ZCode 已在该 SHA 区间提交 6 个修复 commit（C-01/C-02/C-03/V-01/V-02×2）。

## 审查范围（仅此）
`git diff 4d1b3fc..db4349f`（9 文件，约 1100 行新增），以及原始审计中这 5 个 finding 的定义。

## 必须逐项核验（优先用真实执行复现，不要只读代码下结论）
1. **C-01**：原攻击——target 节点 nb 覆盖 pkg/b.py+pkg/b2.py，源文件删 import pkg.b 但保留 import pkg.b2，修复前会输出 RELATION_REMOVE_CANDIDATE na->nb。在修复后代码上重建该真实 Git 场景，验证不再输出该候选；并验证"全部目标域成员的 import 都消失"时候选仍会发布（不得弱化 oracle）。
2. **C-02**：原攻击——(a) 未变化的 target 文件被 B skipped（如语法错误）时，修复前 strong RELATION_ADD 仍发布/或静默取消且无 HUMAN_REQUIRED；(b) 辅助源被 B skipped（1MiB 预算）但 C 仍读它参与删除证明；(c) 部分收集不得强于全量收集。验证修复后：domain_gate 阻断强候选 + 产生可见 HUMAN_REQUIRED（含成员与原因）；并验证全 eligible 域仍能正常发布（不得过度阻断）。
3. **C-03**：原攻击——implementation.baseline.head 指向 base（合法主张）被当成与 target 矛盾 → pack 不可信 → conflict rows 停止压制 → 已暂停 NODE_ADD 重新发布。验证修复后：baseline head==base → 确认且 conflict 仍压制候选；baseline head 错误 → 同主体矛盾（pack 不可信）；外来 component/PR head → UNKNOWN 且绝不释放冲突。
4. **V-01**：验证 runner 现在把 SkipTest/零匹配/模块加载失败/缺失 A30 测试分类为 SKIP/NOT_RUN/INVALID_TEST，绝不 PASS；S30 绑定真实 test_a30_* 行为测试（可在 A30 worktree 执行），证据含真实测试名与数量而非硬编码；INPUT_HASH 覆盖全部 selections + C 实现源。运行 tests.test_acceptance_runner（10 项 meta-tests）与 python tests/acceptance_matrix.py 验证。
5. **V-02**：检查 tests/mutation_runner.py 的语义分类管线（锚点检查、parse 有效性、绿基线要求、SEMANTIC_CAUGHT/MISSED/INVALID_MUTATION/ANCHOR_NOT_FOUND/ENVIRONMENT_ERROR）。如时间允许，运行 `python tests/mutation_runner.py`（约数分钟）验证 6 个变异均合法且被守卫捕获；否则至少核对 6 个变异锚点与当前源一致、替换后代码合法、守卫套件确实断言对应不变量。
6. **回归检查**：运行完整测试套件（python -m unittest discover -s tests -p "test_*.py"），并检查修复是否引入了新的越权行为（例如把不可证实的证据当合格、把 skipped 当可用、放松任何既有不变量）。

## 独立性要求
- 不要信任 ZCode 的测试结论：至少亲自运行关键复现（可用 tests/ 中的现有测试作为起点，但必须自己确认它们真的断言了原始攻击场景）。
- 检查测试本身是否被"造绿"：新增测试是否真的在修复前会失败（可用 git stash/工作树对比或直接在临时克隆上 revert 单个修复来验证，不修改本工作树）。

## 输出要求
- 逐 finding 给出：CLOSED / NOT_CLOSED / CLOSED_WITH_RESERVATIONS + 证据（你实际运行的命令与观察）。
- 新发现按 BLOCKER/HIGH/MEDIUM/LOW 分级。
- 最后一行输出：`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`
