你是 ProjectMind 的独立代码审计 reviewer（fresh 独立会话）。聚焦复核一个修复缺口，不做整仓审计。

## 硬性规则
- READ ONLY。不修改文件。沙箱受限项明确标注，不把环境错误当回归或当通过。

## 任务
背景：上一轮终审（G:\jiagou\projectmind-audit-repair\reviews\codex_final_review.last.md）唯一未决项为 C-06 的 MEDIUM 缺口：src-layout 检测只匹配 `<module>.py` 与 `<module>/__init__.py`，命名空间包（无 __init__.py）的 `import pkg` 仍静默。整改：C 分支 commit 65a7c48（relations.py 的 _repo_internal_unresolved 增加目录段匹配），并合并入 BCD（integration/bcd-audit-fixes-v1 @ 1cc2fd8）。

## 必须核验
1. 用你上一轮的同一内存复现方式重放：地图声明 src/entry.py、src/pkg/b.py（无 __init__.py），target 新增 `import pkg` → 现在必须出现 import resolution limit 与 HUMAN_REQUIRED，不得静默；`import pkg.b` 与直接/别名 import_module 的既有可见性不回退。
2. 不要过度扩大：外部/stdlib（如 import os、import json）不得被误报为 repo-internal；合法可解析 import 的行为不回退（test_w3_relations 既有断言）。
3. 运行 python -m unittest tests.test_c_medium tests.test_w3_relations（C worktree G:\jiagou\projectmind-c-audit-fixes @ 65a7c48）；受限则用内存夹具并标注。
4. BCD worktree G:\jiagou\projectmind-bcd-audit-fixes @ 1cc2fd8：确认 extensions/map_proposal 与 C 分支 65a7c48 逐字节一致（git diff --exit-code 65a7c48 1cc2fd8 -- extensions/map_proposal）。

## 输出要求
- C-06 终态判定（CLOSED / NOT_CLOSED / CLOSED_WITH_RESERVATIONS）+ 证据。
- 新发现（如有）按 BLOCKER/HIGH/MEDIUM/LOW 分级。
- 是否满足 BCD_READY_FOR_HUMAN_REVIEW（结论 + 依据）。
- 最后一行输出：`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`
