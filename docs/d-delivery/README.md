# D 集成交付 · 2026-10-06

关联任务：[#44](https://github.com/LingweiXingzhi/projectmind-core/issues/44)。责任位 D；供 A 审核接入。本文是固定版本的实现与交付说明，不是正式架构批准或产品整体验收结论。

## A 先看这里

交接、日志、协同交接和今日体验改进已经在 `feat/42-continuity-usability` 汇合。要体验 D 最新产品，用该分支；不要切回 main 期待看到这些功能。另一个 PR #41 只交付 Repo Explorer 验收工具，需单独接入 A 的集成分支。

**建议接入顺序：核对 A 目标版本 → 接入 D 原交接及日志 → 接入协同交接 → 接入今日改进 → 单独接入验收工具 → 在 A 的实际版本回归。** 下面给出两种接入方式，选择一种，不重复应用相同代码。由 A 决定目标分支和合并方式；本次不自动合并、不更新旧分支或 main。

## 1. 固定版本与 PR

核查时间：2026-10-06（北京时间）；以下五个 PR 在本次核查时均为 OPEN、未合并，#24/#26/#27 为 Draft。移动分支之后，以完整 SHA 和 [manifest.json](manifest.json) 为核查依据。

| 交付 | 分支 / PR | 远端完整 HEAD | 当前 PR base |
| --- | --- | --- | --- |
| 原交接包 | `feat/23-handoff-draft` · [#24](https://github.com/LingweiXingzhi/projectmind-core/pull/24) | `731135bd87498db766070183455601247a29fbc6` | main |
| 工作日志 | `feat/25-worklog` · [#26](https://github.com/LingweiXingzhi/projectmind-core/pull/26) | `9b3d333dbd75ec7a246de646aa28a9d4b3d0ec80` | main |
| 协同交接 | `feat/handoff-continuity` · [#27](https://github.com/LingweiXingzhi/projectmind-core/pull/27) | `8f00be38532f3f5e9823aec8cbf430038cc9ff4b` | main |
| 今日体验改进 | `feat/42-continuity-usability` · [#43](https://github.com/LingweiXingzhi/projectmind-core/pull/43) | `86d1e2d8f2d27187e2e707eaa99f41643aaf1601` | feat/handoff-continuity |
| 独立验收工具 | `feat/repo-explorer-acceptance-v1` · [#41](https://github.com/LingweiXingzhi/projectmind-core/pull/41) | `caa26916e9ad255bfbae2a27d8863c96d028acde` | integration/bcd-audit-fixes-v1 |

main 本次核查为 `7484d44ddeac3c054ca3ba68f92293d965bb615c`；#41 基线为 `1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d`。main 不是本次功能验收目标，#41 基线也不等于 A 本轮最终产品。

### 已核对的包含关系

- #27 是 #24、#26 的后继汇合，并增加协同交接；Git compare 显示它分别领先两者，behind 均为 0。
- #43 是 #27 上的一条追加提交。其 `extensions/handoff/` Git tree 与 #24 完全相同，`extensions/worklog/` Git tree 与 #26 完全相同，对应测试 blob 也相同。原功能未被今日改进替换。
- #43 相对 #27 只改六个文件：协同交接 README、index.html、model.py、store.py、test_continuity.py，新增 check_continuity_ui.js。
- #41 相对其基线只有六个测试/说明文件，不提供 Repo Explorer 产品实现，不自动汇入 #43。

### 接入方式 A：沿现有 PR 链审查

先审查 #24 和 #26，再审查 #27 的新增部分，最后接入 #43。#24/#26 合入实际目标后，重新核查或调整 #27 的 base，避免把继承内容当新增功能再审核。#27 接入之后，重新核查 #43 的目标；其旧 base 是 `feat/handoff-continuity`，不代表点击合并就会进入 A 的新集成分支。

也可以一次审查 #27 所含基础功能，再追加 #43；此时需在 #24/#26 记录已由后继交付覆盖，避免再次应用。不要未经模块审核就把全部功能当作已验收。

### 接入方式 B：A 的新集成分支已经包含基础功能

先按路径比较 A 的现状。若原交接和工作日志已经接入，只应用协同交接增量与今日改进；若 A 已改动这些模块，逐项处理差异，不用旧目录覆盖。

在确认基础依赖就绪、没有相同提交的前提下，协同交接的有序非合并提交是：

1. `d2afd0d20674b786b0c905d234e9210bd29f783a`：新增协同交接。
2. `8f00be38532f3f5e9823aec8cbf430038cc9ff4b`：编辑及草稿保留改进。
3. `86d1e2d8f2d27187e2e707eaa99f41643aaf1601`：今日体验改进。

这份清单供审核后顺序 cherry-pick，不要求照单执行。合并提交 `c63eb7c75cf9fb9c89ad211170feba50f6483f9b` 只是汇合基础模块，不能当普通增量提交再次应用。不要把旧 `app.py`、`extension_host.py`、公共 `web/` 或地图覆盖到 A 已集成的新版本。

#41 独立工具的有序远端提交：`c7f4d859267522a017cac7b863f1ec34c2b4ef34` → `caa26916e9ad255bfbae2a27d8863c96d028acde`。只接入该 PR 六个文件；不要为了工具把旧集成基线重新覆盖到 A 分支。它们与先前本地 bundle/patch 内容相同、提交 SHA 不同，不能同时应用两套。

#41 的 ACCEPTANCE.md 中“不自动推送/建 PR”及本地 SHA 是上传前的历史说明；用户当日已明确授权上传，远端接入身份以 #41 PR 正文和本清单为准。

## 2. 已实现的职责和入口

| 模块 | 当前实现 | 页面 / API | 说明与测试 |
| --- | --- | --- | --- |
| handoff | 代码版本与来源、人工地图、提交比较、待复核证据、未覆盖变化、可选 AI 候选、工作备注；JSON/Markdown/AI 接手文本 | `/ext/handoff` · `/api/extensions/handoff` | `extensions/handoff/README.md` · `tests/test_handoff.py` |
| worklog | 四类日志、新建编辑、搜索、历史、版本冲突；MD/DOCX/DOC/PDF 导入与原件下载；JSON 备份 | `/ext/worklog` · `/api/extensions/worklog` | `extensions/worklog/README.md` · `tests/test_worklog.py` |
| continuity | 任务、目标、停止位置、下一步、阅读范围和清单；固定 Handoff 与日志版本；来源/代码/工作区核对；反馈、接续历史、导入导出 | `/ext/continuity` · `/api/extensions/continuity` | `extensions/continuity/README.md` · `tests/test_continuity.py` |
| repo-explorer acceptance | 独立真实仓库样例、HTTP 判定工具与结果记录，不含产品页面 | 命令行工具 | `docs/repo-explorer/ACCEPTANCE.md` · `tests/repo_explorer_acceptance/`（在 #41） |

交出者已有结构化准备能力：填写任务、停止位置、第一步、完成标准和清单，选择日志及优先阅读范围，固定资料后导出。不是任意文件上传箱。接手反馈不自动写回原日志；选中的日志后续编辑不会悄悄改变包内快照。需要更新材料时明确重新固定，旧版本保留。

### 今日变化（#43）

- 普通提示约五秒消失；连续新提示重新计时；失败原因仍在表单中，草稿保留。
- 日常入口简化为接手、记录进展、记录问题、结束。问题是否导致暂时无法继续，由同一入口中的选项表达。
- 新接手入口不要求先走多次状态切换；四项检查选填，未勾选不表示已验证。
- “结束本次接手”保存结果、停止位置和下一步，允许清单未完成；“整个任务已完成”仍需清单全部完成并填写结果与验证依据。
- 相同日志正文与原件预览不重复展示，原件仍可下载。

## 3. 接口、宿主与数据边界

continuity 直接复用 handoff 生成器和 worklog 存储，三个模块必须一起存在；单拷 `extensions/continuity/` 不能替代依赖。宿主须提供现有 ExtensionContext 的 repo、map_path、snapshot()、compare() 和独立扩展的页面/API 自动发现；若 A 调整了快照字段或上下文，需做明确兼容和回归，不猜测新协议。

原 Handoff 输出仍为 `status: handoff_draft`；接续外层格式仍为 `projectmind-continuity-v1`，内层保留原 Handoff。完整任务、日志和事件应使用接续 JSON；只导出内层 Handoff 会丢失这些外层资料。工作日志备份格式为 `projectmind-worklog-backup-v1`，首版无备份恢复页面。

#43 新增事件 `claim`、`finish_session`；原 ready/receive/start/block/resume/complete/question/note 继续支持，旧 start/resume 的四项检查约定未移除。finish_session 必须有 note、stopPoint、nextAction，将状态置为已有的 ready，清单不变，任务不变为 completed。所有更新使用 expectedVersion，冲突返回 409。旧 UI 无法呈现新操作，需同步页面与后端、重启服务。

| 数据 | 位置与范围 | 不代表什么 |
| --- | --- | --- |
| 日志 | 目标仓库 Git 公共目录下 `projectmind-worklog/records.sqlite3` | GitHub 自动同步、已认证作者或正式决定 |
| 接续记录 | 同一位置下 `projectmind-continuity/records.sqlite3` | 多人实时协作或已独立验收 |
| 包中的地图、日志、反馈 | 固定快照和参与者自行记录 | 地图已核查、AI 已确认、描述必然属实 |

同仓库 worktree 共用 Git 公共目录，不同仓库隔离。普通 Git 提交不会上传这两份数据库；切换分支不清空记录。克隆到新目录不会自动带入旧记录，需使用文件交换；接续包导入不覆盖本机日志库。导入历史的完成状态不是本机完成证明。

地图适用版本保持 UNKNOWN；AI 保持候选；人工日志与反馈保留未独立核实状态。命令和任务说明只展示为文本，不自动执行、切分支或 fetch。来源地址相符只是一条线索，不是认证。

日志原文件最多 10 MB；随接续包携带的单原件最多 5 MB、整包最多 12 MB。分片上传适配宿主 64 KiB JSON 限额。PDF 为原文预览，无 OCR；DOCX 为正文提取和原件，复杂版式不复现；DOC 依赖 macOS textutil 或已有 LibreOffice。continuity 的 Git 检查使用 `--no-lazy-fetch`，目标 Git 需支持该选项，不支持时提示升级。

## 4. 从最新 D 产品运行

在已有实际远端的仓库中，GitHub Desktop Fetch origin，切到 `feat/42-continuity-usability` 并取得最新版本。先核查工作区，保留未提交修改。关闭旧服务后，在该仓库根目录运行：

```bash
git rev-parse HEAD
python3 app.py --port 8765
```

HEAD 应与上面 #43 的完整 SHA 一致；若之后分支更新，记录实际 SHA，不声称运行旧固定版。Python 3.10+、Git；普通地图/交接/日志无需 API Key，产品不依赖 Node。打开 `http://127.0.0.1:8765/ext/continuity`，另外两个页面见上表。端口被占用时选择另一空闲端口，URL 同步修改。

本固定版读取其他本地仓库仍需 `--repo` 和人工 `--map`；A 的 Repo Explorer 无地图入口是另一项集成交付，不能因 #41 工具存在就宣称这里已支持。

接入 A 后，使用 A 给出的实际启动命令和完整 SHA；不能拿本分支运行成功代替 A 集成通过。

## 5. 实际验证与未验证

以下是已经发生的证据，不是本次文档修改后重跑产品的声明。

| 范围 | 实际证据 | 结论和限制 |
| --- | --- | --- |
| #43 固定内容 | 当日 `python3 -m unittest discover -s tests -v`，53 项通过；含新事件真实 HTTP、导出/重导入及原功能回归 | 自动化通过；本地 SHA `9d338c4dd0f6991a07db6a414a17122f1045ab7e` 与远端 #43 tree 同为 `1161b4dc5eb4b3e1b6f3bf92830d1d5d6389735c` |
| #43 页面逻辑 | `node tests/check_continuity_ui.js`、脚本语法及 diff 检查通过 | Node 执行实际页面函数，不是浏览器视觉验收 |
| 本次参与者体验 | 导出记录第 7 版含 finish_session；待做及遇到问题的清单保留，状态 ready | 说明参与者走过本次结束路径；练习文字和旧停止位置仍在，不是独立完整任务验收。原始私人练习包不上传到源码 |
| #27 历史验证 | 原 PR 报告 47 项及 Chromium 创建、接收、下载/重导入、证据阅读和窄屏检查 | 属于原 PR 历史报告，不冒充 #43 的浏览器验证或本轮重跑 |
| #41 工具 | 已保存 tool-selfcheck.txt：12 项通过；另一个干净仓库接入 bundle 后自检通过 | 只验证工具；自建 HTTP responder 不是 A 产品 |
| A Repo Explorer 产品 | initial-not-run.json 中目标未提供，HTTP/UI/解析器缺失实例未运行 | PRODUCT_ACCEPTANCE = NOT_RUN；Windows 现场未验收 |

仍待验证：A 实际集成版本的全套回归与页面；#43 全操作视觉/窄屏体验；目标设备 PDF 预览、旧 DOC 转换；非作者真实任务接续。#43 自动浏览器尝试因缺少本地 Chromium、云端隔离端口被 ERR_BLOCKED_BY_CLIENT 拒绝，没有将其记为通过。

## 6. A 接入后交回什么

给 D 一条明确的集成记录即可：目标分支、完整 HEAD、运行命令、包含的 D/B/C 版本、已解决冲突以及仍未通过的项目。D 然后按这个实际版本复验，不要求现在再重复练习交接。

产品回归入口（在 A 的集成 checkout）：

```bash
python3 -m unittest discover -s tests -v
node tests/check_continuity_ui.js
```

Node 只用于 UI 逻辑检查。接入 #41 后按其 ACCEPTANCE.md 生成独立仓库，再针对 A 真实服务跑 HTTP；六步真实界面观察另记，没有实例或 UI 证据则保留 NOT_RUN，不用模拟响应充数。

## 本次变更范围

本次只新增本文和固定版本清单，不改任何产品模块、数据库、公共路由或正式地图。Project Model Impact = NONE。原 handoff/worklog/continuity 新职责的 UPDATE 是历史待人审建议；今日 #43 内部体验变化为 MINOR，都不由这份文档自动批准。
