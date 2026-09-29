# ProjectMind 四人协作约定（比赛版）

> 状态：2026-09-29 的**实施约定提案**，供团队审查。它约束比赛版协作方式，不批准长期产品架构或正式 Project Model。当前实现与提案的差别见 [接口约定](MVP_INTERFACES.md) 和 [本次审计](../audits/2026-09-29-mvp-audit.md)。负责人已确认的产品方向优先于本提案；代码是否存在以指定 Git 提交为准。

## 1. 共同交付物与信息可信度

比赛版保持一条每天可运行的路径：打开**人工整理的功能图**，并查看指定 Git 提交里的代码证据 → 点击功能看职责、入口、关系和证据 → 比较两次真实提交 → 标记需要复核的功能 → 可选 AI 候选解释 → 导出给另一位协同者。文件是证据，不占主图主要方框。当前人工地图从本地文件读取，尚未与代码提交一起固定版本；这是本次审计发现的缺口，界面上的代码提交号不能证明图已适用到该提交。拖动后的布局只是本机临时方案；正式架构图及其“核查适用到哪个代码提交”尚未实现。

每条对用户或 Agent 展示的信息要带上以下三种性质之一：

| 性质 | 允许的说法 | 成为正式事实的条件 |
|---|---|---|
| 代码事实 | “提交 X 中有这个文件/入口”“Git 显示文件已变化” | 能按提交和路径复查；不由 AI 猜测 |
| 候选解释 | “可能是某功能”“这个变化值得复核” | 始终保留候选标记、依据与未知项 |
| 团队决定 | “该功能负责什么”“接口如何承诺”“正式图适用到 X” | 按 `AGENT_STANDARD.md` 由人确认；批准人与版本要留痕 |

原始产品意图的整合稿在 `projectmind-model/docs/PROJECT_ANALYSIS.md`，其中早期 Master Spec 只是 AI 草稿。代码事实以本仓库指定提交为准。发现两者矛盾时在 Issue/PR 写出“原说法、代码位置、建议修订”，不要悄悄改写产品目标。

## 2. 开工前共同基线

1. 每人拿到一个 Issue：用户能看到的交付结果、验收步骤、责任人、依赖项、预计改动文件。没有 Issue 号的临时修复可先报告集成人，再补记。优先修复本次审计提出的“地图版本身份缺失”和“AI 结果未进入交接”两处缺口。
2. 四人确认相同的**基准提交完整 SHA**和共同运行入口。当前可运行实现位于连续的 PR #6、#8、#10、#12、#14、#16；`main` 目前还没有这些产品代码。本约定在 `docs/17-mvp-interface-contract` 分支上；**它并入 `feat/15-local-repo-input` 前，四人的新分支从本约定分支的同一提交建立，PR 暂以它为 base**。约定并入后，再把后续 PR 的 base 调整到 `feat/15-local-repo-input`；整条产品 PR 链合入 `main` 后，新任务才从 `main` 建分支。不要把“PR 已打开”说成“main 已有功能”。
3. 使用同一份 [接口约定](MVP_INTERFACES.md)。各自的 Codex 先读 `AGENTS.md`、相关 Issue、接口约定和任务涉及的文件；不需要每次全仓重新概括。
4. 明确会接触的文件。两人要改同一文件时先约定一个集成人。当前分支已有 [独立扩展入口](EXTENSION_INTERFACE.md)：B/C/D 各自提交 `extensions/<功能名>/` 及测试，重启服务后独立页面与数据接口自动出现，无须 A 修改 `app.py` 或共享前端。B/C/D 的业务函数仍只是下文的拟议交接点，必须各自实现；若要把输出嵌进现有功能图，才由 A 改共享主线。

## 3. 四人的任务与接口交接

这里的 A/B/C/D 是**责任位**，不是人员任命。每人可独立用 Codex 开一个任务分支；当天至少交付一个能运行或能用固定样例验证的纵向结果。负责人只需把姓名填到 Issue，不必重新讨论普通技术细节。

| 责任位 | 从现在能做的首个交付 | 主改位置 | 交给其他人的输入/输出 | 依赖 |
|---|---|---|---|---|
| A：集成与体验 | 保持现有图、详情、比较、导出同一入口可运行；核查扩展接入和主线体验 | `app.py`、`web/`、`README.md` | 消费 `Snapshot`、`Comparison`；负责现有功能图与公共路由改动 | 当前可运行分支；主图若消费 B/C/D 输出时才依赖它们 |
| B：代码事实 | 给选定 Git 提交提取一小组真实入口及路径，输出可核查 JSON，不断言功能职责 | `extensions/code_facts/`、`tests/test_code_facts.py` | `repo + revision + 可选路径` → `CodeFacts`；自己的扩展接口/页面；见接口文档 | 可立即用测试仓库开工；不等 C |
| C：候选功能结构 | 用固定样例的代码事实与人工图，提出少量功能节点/关系候选，显示依据和未知；不覆盖人工图 | `extensions/map_proposal/`、`tests/test_map_proposal.py` | `Snapshot + CodeFacts` → `MapProposal`；自己的扩展接口/页面 | 首日不等 B；真实接入等 B 的首个输出 |
| D：协同交接与验收 | 用当前 `Snapshot + Comparison` 生成可让另一位 Agent 复核的简短交接包，并由非作者复现演示 | `extensions/handoff/`、`tests/test_handoff.py` | `Snapshot + 来源 + Comparison? + AI 候选?` → `Handoff`；自己的扩展接口/页面 | 可立即用现有接口开工 |

**禁止把分工误解成四天后集成四个大块。** A 从第一天就保住运行主线；B/C/D 每天提交自己的可运行扩展或固定输入输出样例，A 每天验证新入口及原主线。某项接入失败时保留前一天可运行版本，Issue 写明卡在输入、输出还是运行环境。D 的首项交接功能应当可以只凭现有数据运行，不等新解析器。四人任务是下一步建议，具体 Issue 和姓名由团队填入；不是宣称 B/C/D 业务功能已经实现。

**可直接领取的四张任务卡（各自单独 Issue/PR）：**

1. **A｜地图来源能被看见并区分于代码提交。** 从第 2 节约定的共同基线开分支。启动现有自我演示，在同一代码 SHA 下改动一份人工地图副本后刷新：界面与导出都必须让非作者看出地图文件内容已变化、地图是否已被团队核查为 UNKNOWN；不能只显示代码 SHA。比较结果若依据另一份地图计算，提示重新获取快照。先写一个会失败的固定样例，再完成最小改动；公共文件 `app.py`、`web/`、`tests/test_app.py` 仅由 A 接线。交付一段从干净分支可复现的命令和两种输出。无前置任务。
2. **B｜真实提交中的入口事实。** 在 `extensions/code_facts/` 实现接口文档的 `collect_code_facts` 和自己的 `handle`/页面，测试只放 `tests/test_code_facts.py`。用临时 Git 仓库提交一份已知代码，传完整 SHA 后返回该提交中真实的路径、入口名和行号；再修改未提交工作区，输出仍保持原提交事实。未知语言进入 `skipped`，不猜功能职责。提交 HTTP 调用样例和错误样例，不改 `app.py`。无前置任务。
3. **C｜候选功能说明。** 在 `extensions/map_proposal/` 实现 `suggest_map` 和自己的 `handle`/页面，测试只放 `tests/test_map_proposal.py`；先使用 [固定合约样例](MVP_CONTRACT_EXAMPLE.json) 开发，输出一个带 `evidencePaths` 和 `unknowns` 的候选；版本不一致或无证据时返回明确失败或空结果，不改人工图。可用可控响应验证数据限制，真实模型调用需另行记录。开发无前置任务；联调真实代码事实时依赖 B 的首个结果。C 不碰 `app.py`、共享 `web/` 或 `data/project-map.json`。
4. **D｜另一位 Agent 能继续工作的交接包。** 在 `extensions/handoff/` 实现 `build_handoff` 和自己的 `handle`/页面，测试只放 `tests/test_handoff.py`；用 [固定合约样例](MVP_CONTRACT_EXAMPLE.json) 中的快照、调用者提供的仓库来源和比较结果，明确代码 SHA、地图版本 UNKNOWN、变化路径、待复核节点和证据；可选 AI 候选作为独立输入并保留未知项。另一个队友只看交接包，应能指出“仓库从哪取得、代码对应哪个提交、地图是否已核查、哪个节点待复核、下一步去哪核查”。D 不碰公共路由，可以在自己的页面提供下载。无前置任务。

任务 1 和 4 优先填补本次审计的实际缺口；任务 2 和 3 扩展自动整理能力。四张任务卡是当前基线的最小切片，下一位 Agent 应在各自 Issue 中记录提交与验收，不自行扩成全语言解析器、全量知识图谱或正式架构审查。

## 4. 分支、PR 和集成节奏

沿用 [TEAM_SOP](TEAM_SOP.md) 的 Issue → 独立分支 → 自检 → PR → 另一人检查。每个 PR 只交一个能验证的行为，连同必要的测试或固定样例；若仍在开发，用 Draft PR 让其他人早看。一个人的任务不要直接改另一人的分支或重写其历史。

每天固定一次集成检查：记录共同基准 SHA；依次接入已通过验收的 PR；由非作者从运行说明启动、走通上述主线；把实际通过/失败的步骤、提交和阻塞记在 PR。两人共同修改 `app.py`、地图 JSON 或同一前端文件时由 A 决定合并顺序，先在各自分支更新 base 再解决冲突，不能用“保留我的版本”覆盖另一人的功能。PR 在依赖分支合入后重新指定 base，避免叠加 PR 的差异混淆。

建议给 `main` 启用 PR 审查与最低测试检查；仓库管理员实际设置前，这只是建议，不声称规则已启用。四人短赛程建议至少**一位非作者**审阅涉及共享接口、正式图或演示主线的 PR；单纯文案也需核对实现状态。失败的检查、未核对的 AI 结果和无法复现的演示不能当作已验收。小 PR 便于及时审查和集成。[GitHub 受保护分支](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)、[Google 的小改动评审建议](https://google.github.io/eng-practices/review/developer/small-cls.html)。

## 5. 接口变更办法

现有接口事实以 [MVP_INTERFACES](MVP_INTERFACES.md) 的 `IMPLEMENTED` 小节和对应代码为准；`PROPOSED` 小节是供四人并行的最小交换约定，尚非现有功能。接口包含字段、来源提交、可空条件、错误方式、调用限制，不只是函数名。

更改已经被别人消费的字段/含义时，先在 Issue/PR 写：旧输入输出、新输入输出、受影响调用者、迁移样例。先给旧调用者可兼容的过渡，再由 A 更新接线和测试；所有消费者通过同一固定样例后才移除旧形式。扩展可选字段也要说明默认值。`nodeId` 在一张图内唯一且稳定，证据路径是仓库内相对路径，版本身份用完整 Git 提交 SHA；不同提交的数据不可悄悄混用。不能把候选解释写回已确认图。

## 6. 检查、交接与保密

- 每个交付至少有一条用户路径或固定样例能被**非作者**复现；关键错误路径要可理解地失败。B 的代码事实用真实临时 Git 仓库与已知提交核对；C 的候选必须保留证据和未知项；D 的交接包必须让别人找到同一提交。
- 每个 PR 写明目标、实际变更、验证命令和结果、Project Model 影响 `NONE/MINOR/UPDATE/UNCERTAIN`、未解决问题、所依赖的 PR 和对接口的改动。若影响职责/关系/正式适用版本，只提人审建议，不由 Agent 直接定稿。
- 每日交接最少写：Issue/责任位、分支和完整**代码**提交 SHA、所用地图文件及其当前版本状态（目前未固定时写 UNKNOWN）、现在可演示什么、按什么步骤复现、接口是否变化、失败/未知/下一位接手入口。不要只写“完成 80%”或复制整仓总结。
- API Key、Token 和密码只放本机环境变量；PR、地图、日志和导出包不带秘密。AI 请求只给当前任务必要的证据；对外部模型发送新资料前按团队既有规则检查是否允许。当前 `/api/explain` 是按选中节点的有限差异调用，并非自动全仓理解。
- 比赛演示素材必须来自实际运行：保留对应提交、真实截图、可复现步骤及 AI 调用配置状态。Unity 仓库只留给最终外部可用性验证，现在不读取。

## 7. 不用等待负责人逐项投票的事项

函数内部组织、测试临时仓库、图初始坐标、错误文案等由任务责任人决定并在 PR 说明。只有会改变**产品承诺、团队正式架构决定或谁有批准权**的事项，才提交负责人/团队；现有待讨论清单在 `projectmind-model/docs/TEAM_REVIEW_QUESTIONS.md`。把发现的歧义写成具体例子和建议，不让四个人分别凭 AI 猜一套答案。

## 依据与适用范围

本约定把现有 [TEAM_SOP](TEAM_SOP.md) 落到比赛版四人协作。外部做法只用于补齐操作细节：[GitHub 的 PR 与 Issue 关联](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)、[PR 模板](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates)、[代码负责人](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)。四人姓名和 GitHub 权限尚未核实，因此暂不写 `CODEOWNERS` 或假称已设置分支保护。
