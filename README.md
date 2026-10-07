# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平台

## 架构工作台（本轮新增主入口）

启动后默认进入 Overview：<http://127.0.0.1:8765>。左侧 Architecture 打开架构工作台，Repository 浏览仓库，Changes 审查变化，Handoff / Worklog / Decisions 进入协作记录。⌘K（Windows/Linux：Ctrl+K）搜索页面、工作区和节点；⌘J / Ctrl+J 聚焦节点纠正。详见 [UI 重构与验收说明](docs/ui-redesign/README.md)。架构工作台覆盖以下闭环：

1. **两种入口**：「分析已有项目」输入仓库路径与情况说明，绑定固定提交的代码事实；「规划新项目」输入目标与约束，允许没有代码 SHA（planning 工作区不伪造代码版本）。
2. **生成候选图**：已配置 AI 时调用模型起草功能候选（`ai_generated`，全部为待确认候选）；未配置时如实显示 `NOT_RUN_AWAITING_CONFIGURATION`，不会用规则结果冒充 AI。「载入演示候选（样例）」是明确标注的演示数据，只用于验证界面。
3. **纠正与编辑**：选中节点后可用自然语言描述纠正（生成预览，确认后才应用到草稿），或直接编辑职责、入口/接口、证据、关系与期望过程（步骤 ID 保持稳定）。删除有引用的节点先展示影响。
4. **诚实状态**：草稿用版本号做并发保护（冲突时明确报 `REVISION_CONFLICT`，显示新旧差异而非覆盖）；后端缺失的动作用机器码如实拒绝（`BACKEND_UNAVAILABLE` / `DEV_SAMPLE_DISABLED`），不假装成功。
5. **人审确认**：「确认并保存版本」需要输入复核人与理由。在真实的版本服务（B）接入前，决定只记录在草稿历史中，界面会如实说明"没有产生任何正式认知版本"。
6. **变化复核**：「检查代码变化」对比工作区绑定的提交与仓库当前 HEAD，列出声明证据发生变化的待复核节点；「修正实现：创建开发任务」导出结构化任务样例（真实交接后端接入前标注为演示）。改图不会自动修改程序。

接口约定（CONTRACT_V1）与 B/C/D 接线请求见 `team-deliveries/CONTRACT_V1_DRAFT.md` 的仓库内副本与 `archloop/` 包文档字符串；所有 `/api/archloop/*` 端点接受 loopback Host 与同源 Origin 校验。

工作区数据默认保存在 `data/archloop-workspaces/`（已加入 .gitignore）；可用 `--archloop-data` 指到实例外的目录，多实例互不共享。

## 本地运行第一条演示主线

需要 Python 3.10+ 和 Git。在本仓库根目录运行：

```powershell
python app.py
```

然后打开 <http://127.0.0.1:8765>。查看地图和 Git 变化无需安装 Python 包或配置 API Key。

唯一的运行期依赖是 **`tzdata`**（IANA 时区数据库），仅 Windows 需要：CPython 的 `zoneinfo` 读取操作系统的时区数据库，Windows 不自带，缺它时"团队足迹"按任何 IANA 时区（含默认的 `Asia/Shanghai`）都无法换算，会明确返回 503 部署缺口提示。

```powershell
python -m pip install tzdata
```

依赖声明见 `requirements.txt`。

页面显示 ProjectMind 自身的一张**人工整理的演示功能图**。点击节点可以查看职责、关系、关键入口，并读取固定 Git 提交中的真实文件内容。顶部显示此次证据所对应的完整提交 ID；若来源文件不在该提交中，页面会标记“此版本缺失”。“导出当前摘要”会生成带提交 ID 的 Markdown 文件，方便交接。

节点可拖动以调整查看布局；连线会跟随。点击“保存临时布局”后，位置只保存在当前浏览器本机，刷新页面可以恢复。若 Git 提交已变化，页面会提示复核旧布局。“恢复原位”会清除本机保存的位置。“导出图草稿 JSON”包含当前位置、节点说明、关系、来源路径和对应的完整 Git 提交 ID，可交给队友或 AI 审看。位置只代表查看布局，不表示新增依赖；导出文件明确标记为未确认草稿，不会写入正式 Project Model 或 model 仓库。

“对照两个真实提交”默认比较当前提交与它的父提交。也可以输入另一个**完整提交 ID**作为基准。变化文件来自 Git；若节点声明的来源文件出现在变化中，节点只会标记为“待复核”。导出的 Markdown 摘要包含这次比较。文件变化不能证明职责或架构一定改变。

可选的“让 AI 解释”按钮仅在配置后启用。在启动程序的同一个 PowerShell 窗口设置环境变量，再运行 `python app.py`：

```powershell
$env:OPENAI_API_KEY = "你的 API Key"
$env:PROJECTMIND_AI_MODEL = "你账户可使用的模型 ID"
python app.py
```

点击按钮后，只会向 OpenAI 发送选中节点的人工演示描述、直接关联的变化文件名和最多 12,000 个字符的 Git 差异。请求使用 `store: false`；密钥只留在本地服务端环境变量中，不进入地图文件或浏览器。页面把返回内容标为“AI 候选”，要求人对照来源复核。未配置时其它功能照常可用。API 调用可能产生费用；是否能成功取决于所用账户、模型和网络。

这一步验证“图 → 详情 → Git 来源 → 版本变化 → 待复核候选 → 可选 AI 解释 → 临时布局与导出”的运行路径。演示图不代表自动识别出的架构，也不代表团队批准的正式 Project Model。

## 团队独立扩展

新增功能放入 `extensions/<功能名>/extension.py`，定义标题、说明与 `handle(context, method, data)`。重启服务后，主页侧栏自动出现该功能的独立页面入口，数据接口为 `/api/extensions/<功能名>`；不需要为每个人的新功能修改 `app.py` 或共享页面。`extensions/project_summary/` 是可运行的样例。扩展只接入独立功能页，不会自动修改人工功能图；需要在主图展示的内容仍由团队复核并集成。

具体输入、错误和四人目录分工见 [独立扩展接口](docs/standards/EXTENSION_INTERFACE.md)。

## 查看另一个本地 Git 仓库

可以在启动时指定仓库及其**人工整理的地图 JSON**。这里不自动扫描代码，也不会在启动时读取未指定的其他项目：

```powershell
python app.py --repo "仓库完整路径" --map "地图 JSON 完整路径"
```

地图文件可参照 `data/project-map.json`：顶层需要 `note`、`nodes`、`edges`；每个节点需要 `id`、`title`、`summary`、`entryPoint`、`position`（`x`/`y` 数字）和 `evidence`（仓库内相对路径 `path` 及说明 `reason`）；每条关系需要已存在的节点 `from`、`to` 和 `label`。目前画布为 680×470，节点约为 185×140；为让节点完整显示，初始位置建议满足 `x` 在 0–495、`y` 在 0–330。程序会在启动时检查地图格式，并按目标仓库的 Git 提交核查来源文件。地图内容仍须人工复核。

运行核心验证：

```powershell
python -m unittest discover -s tests -v
```
