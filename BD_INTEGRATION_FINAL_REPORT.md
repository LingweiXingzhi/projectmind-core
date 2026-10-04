# BD_INTEGRATION_FINAL_REPORT — B / Code Facts + D / Handoff+Continuity+Worklog

- 日期:2026-10-04(无人值守 overnight)
- 分支:`integration/bd-v1`;worktree `G:\jiagou\projectmind-integration-bd`

## 第一屏

```
CORE_BASE:        7484d44ddeac3c054ca3ba68f92293d965bb615c  (main,实时核验)
B_HEAD:           80e091acefd278fda03e188a125147b0aa5eedc5  (PR #31,OPEN draft)
D_HEAD:           8f00be38532f3f5e9823aec8cbf430038cc9ff4b  (PR #27,OPEN draft;含 #24/#26,ancestry 实证)
INTEGRATION_HEAD: 见 git log(集成 + Phase 2/4 报告与修复 commits,历史保留未 squash)
TESTS:            unittest 86 项:84 PASS / 2 ERROR(ENVIRONMENT_LIMITED,PR31 原树预先存在,非集成回归;含 6 项 Codex 审计后新增回归)
                  集成 harness 66/66 PASS × 3 轮(含 S21/S22 修复回归);unittest 3 轮失败集 md5 逐字节一致
SECURITY:         路径穿越/绝对路径/UNC/file:// 全部拒绝或按字面匹配 commit 树,零任意读;
                  XSS 静态扫描 0 命中(无 innerHTML/document.write/eval);subprocess 仅固定 git 查询 +
                  which 解析的 DOC 转换器(见 LIMITS);导入不执行任何指令;导入只新增不覆盖
BLOCKERS:         无(Codex r1 HIGH 带备注交接包导入失败已修复并回归,见 CODEX_BD_REVIEW.md)
HIGH:             无(r1 全部 1 HIGH + 4 MEDIUM + 1 LOW 已修复/加固)
LIMITS:           见下节
```

## STATUS: INTEGRATED_WITH_ISSUES_FIXED — GATE PENDING FINAL CODEX ROUND

- Codex r1 FAIL(1H+4M+1L)→ 已修复(`ccc30f0`);r2 FAIL(1H+2M+2L)→ 已修复(`c32d300`)。
- r3(gate 最终轮)因 Codex 用量额度耗尽未能执行(05:09 AM 重置),见 CODEX_UNAVAILABLE.md;按 §29 STOP BEFORE C。

判定依据:全量回归通过(除 2 项 Windows 环境限制)、57 项集成行为与安全验证 3 轮全过、零 merge 冲突、B/D 隔离与共存实证、无数据丢失/覆盖风险、无 BLOCKER/HIGH。

## 决策文档

- `B_SOURCE_DECISION.md` — B_DELIVERY_HEAD = PR31(PR22 非其祖先但内容为直接演进,证据齐全)
- `D_SOURCE_DECISION.md` — D_DELIVERY_HEAD = PR27(实测包含 PR24 与 PR26)
- `BD_INTEGRATION_BASELINE.md` — CORE_BASE = main 7484d44(PR21 纯文档且非 B/D 祖先,不纳入)
- `BD_MERGE_CONFLICTS.md` — 零冲突记录
- `BD_API_COMPATIBILITY.md` — API 面与冲突分析(无冲突)

## 测试明细

| 套件 | 结果 | 说明 |
|---|---|---|
| `python -m unittest discover -s tests` | 86 项,84 PASS,2 ERROR | 2 个 ERROR:`test_paths_are_exact_not_globs`(需创建字面 `*.py` 文件,Windows 保留字符)、`test_symlink_and_gitlink_are_skipped`(需符号链接特权)。**在 PR31 原始树上实测同样失败** → 分类 ENVIRONMENT_LIMITED(非 PREEXISTING_B 回归,更非 BD_INTEGRATION_REGRESSION),按指令不修 |
| `verification/verify_bd.py`(自研集成 harness,已入库) | 66/66 PASS × 3 轮 | S1 共载 / S2 B 功能×19 / S3 D 功能×17 / S13 零污染×2 / S14 隔离×4 / S15 API 面×3 / S18 XSS 静态 / S19 命令执行×2 / S20 导入隔离×2 |

## SECURITY 摘要

- **B**:revision 强制完整 SHA 直指 commit,无 HEAD 回退;`../`、绝对路径、UNC、`file://`、控制字符全部 400;合法但树中不存在的路径 → 显式 400;路径按字面匹配 pinned commit 树,**无任意文件读**;2000 文件/1MiB/16MiB 上限生效。
- **D**:malformed/超限输入 400;expectedRevision/expectedVersion 乐观锁(stale → 400/409);导入(packet/文件)一律**新建记录**(新 uuid/新 id + receiving 态),本地既有记录实测不动;清单/日志/runInstructions 等全部为数据,无任何执行路径。
- **XSS**:全部扩展页面无 innerHTML/insertAdjacentHTML/outerHTML/document.write/eval sink(静态扫描);含 `<script>`、`onerror=` 的输入原样存储为文本。
- **命令执行**:extensions 的 subprocess 仅 ①B/工作日志的固定 git 只读查询 ②旧版 DOC 预览的 `shutil.which('textutil'/'libreoffice'/'soffice')` 固定名解析 + list-args(无 shell);输入中注入 `git push`/`curl`/`$(rm -rf /)` 均被当文本存储,git 工作树零变化。

## LIMITS(已知边界,非缺陷)

1. 2 个 B 测试在 Windows 上环境受限跳败(见上);Linux/CI 下预期全绿。
2. worklog 旧版 DOC 预览依赖本机 LibreOffice/textutil;不存在时显式 400 提示另存 DOCX(优雅降级,已实测)。
3. handoff `comparisonMode: "main"` 只用本机已 fetch 的 origin/main,不联网。
4. continuity 与 worklog 是同一作者仓内的有意只读依赖(logs 动作),升级需联动回归(见 API 兼容文档 §5)。
5. 集成分支未包含 PR21(V1 文档)与 CA(PR29)——按计划 CA 在 C-base 阶段并入。
6. B 的 `skipped` 不作为事实来源(C 消费边界,handoff §8)。

## 无人值守运行记录

- 全程零 main 操作;B/D 原分支零修改;仅新建 `integration/bd-v1`。
- 日志:`G:\jiagou\overnight-logs\`(bd-integration-run1.log、verify-bd-run1.log、stability-*.log)。
- Checkpoint:`G:\jiagou\OVERNIGHT_BD_C_CHECKPOINT.json` 每阶段更新。
