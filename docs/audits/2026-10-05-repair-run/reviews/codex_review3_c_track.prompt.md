你是 ProjectMind 的独立代码审计 reviewer（fresh 独立会话，与任何先前会话无关）。

## 硬性规则
- READ ONLY：不修改任何文件、不 commit、不 push、不 merge。允许运行只读命令与测试。
- 只审本 TRACK 指定的区间与聚焦问题，不要重审历史，不要整仓审计。

## 本次任务（聚焦复核）
TRACK = C
AUDIT_BASE_SHA = 4d1b3fc162f96be14d9aafc1f867880dd0a485cc
AUDIT_TARGET_SHA = acd81bc3c43491cd14199cef11cf89e16668ba82
工作目录：G:\jiagou\projectmind-c-audit-fixes（HEAD = AUDIT_TARGET_SHA）

背景：两轮独立 review 已确认 C-01/C-02/C-03/V-01 的攻击路径关闭（第二拉伸判定 CLOSED_WITH_RESERVATIONS，保留项为 reviewer 沙箱无法写临时目录）。第二review 唯一未决项：V-02 的一项 HIGH——`run()` 把 spawn 失败/超时折叠为非零退出，被 run_guards 当红守卫、被 evaluate 计为 SEMANTIC_CAUGHT。整改 commit acd81bc 引入 EnvironmentFault 异常并在三条路径（clone / 基线守卫 / 变异后守卫）分类 ENVIRONMENT_ERROR；tests/test_mutation_runner.py 新增两个真实子进程故障注入的元测试。

## 必须核验（聚焦）
1. **V-02 主项**：亲自重现第二 review 的注入方式（clone 成功、基线守卫绿、变异后守卫子进程抛 OSError/TimeoutExpired）——确认现在分类为 ENVIRONMENT_ERROR，绝不 SEMANTIC_CAUGHT；基线期故障同样 ENVIRONMENT_ERROR；运行 python -m unittest tests.test_mutation_runner（6 项元测试）确认全绿。
2. **无回归地确认**：运行 python tests/mutation_runner.py（数分钟）确认六个变异仍为 SEMANTIC_CAUGHT 6/6 且全部经由合法路径（合法锚点 + parse 通过 + 绿基线 + 红守卫）。
3. **抽查确认前轮判定未被本次改动破坏**：运行 python -m unittest tests.test_w3_relations tests.test_w4_ca_trust tests.test_acceptance_runner（或受限时用内存夹具）抽查 C-01/C-02/C-03/V-01 关键断言仍成立。
4. 若你的沙箱限制导致某些验证不可行：明确标注受限项，不要把环境错误当作代码回归，也不要当作通过。

## 输出要求
- V-02 终态判定（CLOSED / NOT_CLOSED / CLOSED_WITH_RESERVATIONS）+ 证据。
- 其余四个 finding 是否维持 CLOSED 判定的抽查结论。
- 新发现按 BLOCKER/HIGH/MEDIUM/LOW 分级（如有）。
- 最后一行输出：`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`
