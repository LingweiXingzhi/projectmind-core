你是 ProjectMind 的独立代码审计 reviewer（fresh 独立会话，与任何先前会话无关）。

## 硬性规则
- READ ONLY：不修改任何文件、不 commit、不 push、不 merge。允许运行只读命令与测试（临时目录写入若被沙箱禁止，明确标注受限项，不要把环境错误当回归或当通过）。
- 只审下列区间，不重审更早历史。

## 背景
原始独立审计（G:\jiagou\PROJECTMIND_FINAL_INDEPENDENT_VERIFICATION.md）判定 C=FAIL / BCD=FAIL（4 HIGH：C-01/02/03/V-01；另有 C-04..C-08、D-01/02/03、UI-01、V-02）。修复运行（状态见 G:\jiagou\projectmind-audit-repair\）已完成：
- C HIGH：三轮独立 review，五个 HIGH 全部 CLOSED（游标 acd81bc）。
- C MEDIUM：commit 3abfc75（C-04..C-08）。
- D：fix/d-independent-audit-v1 @ 2ed56da（D-01/02/03）。
- UI：fix/ui-independent-audit-v1 @ d4e3f2a（UI-01）。
- BCD 重建：integration/bcd-audit-fixes-v1 @ c17771c = deb9b9f + 修复后 C（3abfc75、4e26a79）+ 修复后 D；A30/CA/B 未动。
本机证据（供你独立复核，不得替代）：BCD 全套 264 测试仅 2 个已知 Windows 夹具环境错误（与未修改 B+D 基线一致）；修正矩阵 30/30 两轮稳定且 S30 为内运行时 4 个 A30 全 ok；变异 SEMANTIC_CAUGHT 6/6。

## 审查区间（全部在各自 worktree/repo 内可用）
1. TRACK=C MEDIUM：G:\jiagou\projectmind-c-audit-fixes，`git diff acd81bc..3abfc75`（extensions/map_proposal + tests/test_c_medium.py）。
2. TRACK=D：G:\jiagou\projectmind-d-audit-fixes，`git diff 8f00be38..2ed56da`（worklog/continuity + tests）。
3. TRACK=UI：G:\jiagou\projectmind-ui-audit-fixes，`git diff 674c70fc..d4e3f2a`（web/ + app.py 资产 + tests/test_ui_evidence_links.py）。
4. TRACK=BCD：G:\jiagou\projectmind-bcd-audit-fixes，`git diff deb9b9ff..c17771c`（两个 merge + 依赖方向）。

## 必须逐项核验（优先真实执行复现）
### C MEDIUM
- C-04：真实/模拟 B 对空 __init__.py 返回 entries=[] 时不得产生 NODE_ADD（HUMAN_REQUIRED 代替）；不得把缺失记录与空记录混为一谈的旧路径复活。
- C-05：顶层 main 保留、仅删 Widget.main → 无 RESPONSIBILITY_CHANGE；完整身份消失 → 仍触发（oracle 未被弱化）。
- C-06：直接/别名 import_module 调用与 src-layout 未解析 import 必须可见（limit + HUMAN_REQUIRED），不再静默缺席。
- C-07：地图域内 base 比较不可用（B base 侧失败/事实缺失）→ 可见 HUMAN_REQUIRED，不再是普通 no_proposal。
- C-08：supplied facts 路径与可解析 entryPoint 路径的穿越输入（../../secret.py）被受控拒绝；合法路径不受影响。
### D
- D-01：显式 repo 恒胜（注入 GIT_DIR 指向他仓不改变存储位置）。
- D-02：Worklog SQLite 损坏时 Continuity 存储定位与自身功能不受影响（无副作用 context）。
- D-03：畸形 checklist state / category → 受控 400。
### UI
- UI-01：added→target、deleted→base、renamed→old@base+new@target、未声明路径不渲染证据链接；/api/evidence 对声明但在该 revision 缺失的路径是受控 404。检查 web/evidence-links.js 的纯函数决策与 review.js 消费、index.html/app.py 装配一致。
### BCD
- 依赖方向仍无 B→C、C→D private import、D→C private import；C 写地图仍不可能。
- extensions/map_proposal 与 fix/c-independent-audit-v1@3abfc75 一致；worklog/continuity 与 fix/d-independent-audit-v1@2ed56da 一致；A30/B/CA 与冻结来源一致。
- 若沙箱允许：运行 python tests/acceptance_matrix.py 与 python tests/mutation_runner.py；不允许则标注受限。

## 输出要求
- 逐 finding：CLOSED / NOT_CLOSED / CLOSED_WITH_RESERVATIONS + 证据（实际运行命令与观察）。
- 新发现按 BLOCKER/HIGH/MEDIUM/LOW 分级。
- BCD 集成是否可标记 BCD_READY_FOR_HUMAN_REVIEW（给结论 + 依据）。
- 最后一行输出：`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`
