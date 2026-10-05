你是 ProjectMind 的独立代码审计 reviewer（fresh 独立会话，与任何先前会话无关）。

## 硬性规则
- READ ONLY：不修改任何文件、不 commit、不 push、不 merge。允许运行只读命令与测试。
- 只审本 TRACK 指定的 SHA 区间，不要重审区间之前的历史，不要做整仓审计。

## 本次任务
TRACK = C
AUDIT_BASE_SHA = 4d1b3fc162f96be14d9aafc1f867880dd0a485cc
AUDIT_TARGET_SHA = 8c0c096ccb1593ff4fa6a4f366f25686271b1ccc
工作目录：G:\jiagou\projectmind-c-audit-fixes（分支 fix/c-independent-audit-v1，HEAD = AUDIT_TARGET_SHA）

背景：原始审计（G:\jiagou\PROJECTMIND_FINAL_INDEPENDENT_VERIFICATION.md）判定 C=FAIL（C-01/C-02/C-03/V-01 四 HIGH + V-02）。第一轮修复后独立 review（区间 4d1b3fc..db4349f，记录在 G:\jiagou\projectmind-audit-repair\reviews\codex_review1_c_track.last.md）判定 FAIL：C-01/C-02 CLOSED_WITH_RESERVATIONS；C-03/V-01/V-02 NOT_CLOSED，并给出 3 HIGH + 1 MEDIUM 新发现。此后 ZCode 提交了整改：7511701（C-03 精确键+global scope）、a93b7ca（V-02 反转标志+元测试）、8c0c096（V-01 S30 逐测试分类/零匹配 NOT_RUN/INPUT_HASH 身份/INVALID 枚举 + M3 锚点更新）。

## 必须逐项核验（优先真实执行复现）
1. **C-01**：多目标残留攻击（b.py 删 import、b2.py 保留 → 不得发布 RELATION_REMOVE_CANDIDATE；全部消失 → 发布）。
2. **C-02**：skipped 目标/辅助源/部分收集 → 不发布强候选 + 可见 HUMAN_REQUIRED；全 eligible → 正常发布（不过度阻断）。
3. **C-03（含 review-1 两项绕过）**：
   a. implementation.baseline.head（global）指向 base → 确认、conflict 仍压制候选；
   b. implementation.baseline_router.head（global，组件名撞前缀）→ foreign UNKNOWN，绝不矛盾；
   c. implementation.baseline.head scope=component:router → foreign UNKNOWN；
   d. target_head 错值 → 矛盾（同主体）。
4. **V-01（含 review-1 发现）**：
   a. SkipTest → SKIP（run_selection 与 S30 两条路径都要验证；S30 中被 skip 的 A30 测试退出码为 0，验证 runner 不再据此判 PASS）；
   b. 零匹配 selection（即使同组其他 selection 通过）→ NOT_RUN；
   c. 零匹配 selection 加入后 INPUT_HASH 改变；S30 INPUT_HASH 绑定真实测试源与名字；
   d. 枚举失败 → INVALID_TEST；S30 证据含逐测试结果（A30 测试运行时会输出 HTTP 日志，验证逐测试子进程分类对此免疫）。
5. **V-02（含 review-1 反转标志）**：
   a. 绿守卫 + 合法变异 → SEMANTIC_MISSED（绝不 CAUGHT）；
   b. 红守卫 → SEMANTIC_CAUGHT；锚点漂移 → ANCHOR_NOT_FOUND；非法 Python → INVALID_MUTATION；
   c. 6 个变异锚点在当前源唯一、替换后合法；可运行 python tests/mutation_runner.py（数分钟）验证 6/6。
6. **回归**：运行完整测试套件（python -m unittest discover -s tests -p "test_*.py"）；若你的沙箱禁止临时目录写入导致测试无法运行，请明确标注该项验证受限，不要把环境错误当作代码回归，也不要当作通过。

## 输出要求
- 逐 finding 给出 CLOSED / NOT_CLOSED / CLOSED_WITH_RESERVATIONS + 证据（实际运行的命令与观察）。
- 新发现按 BLOCKER/HIGH/MEDIUM/LOW 分级。
- 最后一行输出：`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`
