# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平台

## 本地运行第一条演示主线

需要 Python 3.10+ 和 Git。在本仓库根目录运行：

```powershell
python app.py
```

然后打开 <http://127.0.0.1:8765>。查看地图和 Git 变化无需安装 Python 包或配置 API Key。

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

具体输入和错误见 [独立扩展接口](docs/standards/EXTENSION_INTERFACE.md)；四人职责与目录分工见 [协作约定](docs/standards/COLLABORATION_CONTRACT.md)。

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
