# B_SOURCE_DECISION — B / Code Facts 集成来源定案

- 定案时间:2026-10-04(无人值守 overnight,Phase 0)
- 证据方式:`git fetch origin` + `gh pr list/view`(实时)+ `git merge-base --is-ancestor` + 内容级 diff,全部实测
- 结论:**B_DELIVERY_HEAD = PR #31 head `80e091acefd278fda03e188a125147b0aa5eedc5`**(branch `feat/30-code-facts-integration`,OPEN draft,实测)

## 候选

| 候选 | branch | head(实测) | 状态(实测) |
|---|---|---|---|
| PR #22(首版原型) | `docs/b-first-version-wang-haining-2026-10-01` | `0c46747147f765260bf2033f6eae40189b58ca0c` | OPEN draft |
| PR #31(真实 Core 接入) | `feat/30-code-facts-integration` | `80e091acefd278fda03e188a125147b0aa5eedc5` | OPEN draft |

## Ancestry(实测)

- `merge-base --is-ancestor origin/docs/b-first-version-wang-haining-2026-10-01 origin/feat/30-code-facts-integration` → **NO**
- 两者均以 main `7484d44` 为基(main 是两者祖先;PR22 与 PR31 在 git 历史上是平行分支)
- 即:PR31 **不是** PR22 的 git 后代。handoff 所称"PR31 是 PR22 的后续集成演进"在 git 层面不成立,需靠内容比对定案(见下)。

## 内容比对(实测 diff)

PR22 的 B 代码位于 `collaboration/b/2026-10-01-wang-haining/`(沙盒原型结构),PR31 的 B 代码位于仓库根 `extensions/code_facts/`(真实 Core extension 位置)。

| 文件 | PR22 | PR31 | 内容差异 |
|---|---|---|---|
| `facts.py` | 158 行 | 162 行 | 仅 3 处硬化:①环境加 `GIT_NO_LAZY_FETCH=1` 且 git 命令加 `--no-lazy-fetch`;②对象不在本地时显式报错(不自动抓取,partial-clone 显式报错);③旧版 git 不支持 `--no-lazy-fetch` 时给出升级提示。其余逻辑逐行一致 |
| `extension.py` | 23 行 | 23 行 | 仅 1 处:GET paths 的 CRLF 归一(`\r\n`→`\n`) |
| `index.html` | 330 行 | 332 行 | ±2 行 |
| 测试 | 311 行 | 535 行 | PR31 新增 SHA-256 仓库测试等 |
| README | `collaboration/b/.../README.md`(原型契约) | `extensions/code_facts/README.md`(122 行,重写版契约) | PR31 携带演进后的正式契约 |

## why(定案理由)

1. **功能超集**:PR31 相对 PR22 只有安全硬化(禁懒抓取、显式 partial-clone 报错)与 CRLF 修复,无任何行为删除——是 PR22 的直接演进实现。
2. **真实 Core 集成**:PR31 位于 Core ExtensionHost 实际发现的 `extensions/code_facts/`;PR22 的副本在 `collaboration/b/` 沙盒下,真实 Core 不会加载。commit message 亦自述 "integrate committed code facts into real Core (#30)"。
3. **契约以 PR31 为准**:PR31 携带重写后的 `extensions/code_facts/README.md` 与 535 行测试(含 SHA-256 仓库测试);PR22 的 `SELF_CHECK.md`/`VERIFICATION.md`/`examples/` 属原型验证记录,已被 PR31 测试套取代,不随集成携带(保留在 PR22 分支上,未丢弃)。
4. **边界提示(给 C)**:Context Authority 的 B 契约 claim 钉在 PR22 README(CA RULE-12 已知 drift);B 实际契约以 PR31 README 为准,消费时须按 PR31 现状核验。

## 结果

- **B_DELIVERY_HEAD = `80e091acefd278fda03e188a125147b0aa5eedc5`**(PR #31 head)
- PR22 分支不 merge、不修改、不删除。
