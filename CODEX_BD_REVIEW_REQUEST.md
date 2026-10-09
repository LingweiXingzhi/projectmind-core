# CODEX_BD_REVIEW_REQUEST — 独立只读审核请求(第一轮)

致独立 reviewer(Codex):你是 REVIEW ONLY 角色。

## 硬性规则
- READ ONLY:不修改任何文件、不 commit、不 push、不 merge、不创建/删除任何文件。
- 允许读取:repo root、tests/、extensions/、docs/、verification/、git diff、git log、git status、worktree 元数据。
- 不要只相信报告文档——用 git 与源码独立核验 ZCode 的每一条声明。
- 结尾必须给出结论行:`CODEX_VERDICT: PASS` 或 `CODEX_VERDICT: PASS_WITH_LIMITS` 或 `CODEX_VERDICT: FAIL`(可另附分级 findings)。

## 背景(由实施方 ZCode 声明,须独立核验)
- 本分支 `integration/bd-v1` 从 main `7484d44` 出发,先 merge B(PR #31 head `80e091ac`),再 merge D(PR #27 head `8f00be38`),历史保留未 squash。
- 声称的 B_SOURCE:D 选择 PR31 而非 PR22(PR22 分支不是 PR31 祖先,但内容为直接演进,仅加 --no-lazy-fetch/partial-clone 显式报错/CRLF 处理,另有重写 README 与扩充测试)。
- 声称的 D_SOURCE:PR27 实测包含 PR24 与 PR26(merge-base --is-ancestor),单次 merge。
- 声称:两次 merge 零冲突(B/D 改动集与 main 相比零交集)。
- 声称:unittest 77 项中 2 个 ERROR 为 Windows 环境限制(字面 `*.py` 文件、symlink 特权),在 PR31 原树同样存在。
- 声称:57 项集成验证(verification/verify_bd.py)全过 ×3 轮。

## 必读文件(按序)
1. BD_INTEGRATION_BASELINE.md
2. B_SOURCE_DECISION.md
3. D_SOURCE_DECISION.md
4. BD_MERGE_CONFLICTS.md
5. BD_API_COMPATIBILITY.md
6. BD_INTEGRATION_FINAL_REPORT.md
7. extensions/code_facts/(B 实现 + README)
8. extensions/handoff/、extensions/continuity/、extensions/worklog/(D 实现)
9. tests/(全部测试)
10. verification/verify_bd.py(集成验证 harness)
11. `git log --graph main..HEAD`、`git diff 7484d44..HEAD --stat`

## 必须回答的 7 个问题
1. B+D 是否真实集成(代码真实存在、真实可加载、真实被 merge 进本分支)?
2. 是否有隐藏的 merge/ownership 错误(改了不该改的文件、丢失某方提交、squash/改写历史)?
3. ZCode 的测试是否足够(覆盖面、真实性、是否有造绿嫌疑)?
4. 是否存在 security blocker(路径穿越、任意读写、XSS、命令执行、数据覆盖)?
5. 是否修改了不该改的文件(main 现有文件是否被本分支触碰;PR22/24/26/27/31 原分支是否被改动)?
6. 是否有数据丢失风险(导入覆盖、存储碰撞、静默丢记录)?
7. 该集成结果是否适合作为后续 C / Map Proposal 的 development base?

## 输出格式
- 逐条核验结论(引用你实际看到的 git/文件证据)。
- findings 按 BLOCKER / HIGH / MEDIUM / LOW 分级。
- 最后一行:`CODEX_VERDICT: PASS|PASS_WITH_LIMITS|FAIL`
