# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平台

## 团队 HTTPS 运行入口（部署准备）

新增登录、浏览器会话/CSRF、服务器仓库选择与 Waitress 接续。
本地生产服务和 HTTPS 闭环已经验证；服务器、真实域名与浏览器/跨设备验收仍未完成。
启动、账号配置、Caddy、持久化与验证限制见 [部署说明](docs/deployment/README.md)。
公网入口使用 `python -m deployment.server serve`；下方 `app.py` 保留为本地演示。

## 架构工作台（本轮新增主入口）

启动后默认进入「架构工作台」：<http://127.0.0.1:8765>。它覆盖一条完整闭环：

1. **两种入口**：「分析已有项目」输入仓库路径与情况说明，绑定固定提交的代码事实；「规划新项目」输入目标与约束，允许没有代码 SHA（planning 工作区不伪造代码版本）。
2. **生成候选图**：已配置 AI 时调用模型起草功能候选（`ai_generated`，全部为待确认候选）；未配置时如实显示 `NOT_RUN_AWAITING_CONFIGURATION`，不会用规则结果冒充 AI。「载入演示候选（样例）」是明确标注的演示数据，只用于验证界面。
3. **纠正与编辑**：选中节点后可用自然语言描述纠正（生成预览，确认后才应用到草稿），或直接编辑职责、入口/接口、证据、关系与期望过程（步骤 ID 保持稳定）。删除有引用的节点先展示影响。
4. **诚实状态**：草稿用版本号做并发保护（冲突时明确报 `REVISION_CONFLICT`，显示新旧差异而非覆盖）；后端缺失的动作用机器码如实拒绝（`BACKEND_UNAVAILABLE` / `DEV_SAMPLE_DISABLED`），不假装成功。
5. **人审三步**：「保存草稿到版本服务」→「人审预览（真实会话）」→「确认接受」→「发布不可变版本」。预览绑定真实请求会话与覆盖范围，确认授权只留在服务端；发布产生真实架构 Git 提交（`mapSourceRevision`）与不可变图版本（`mapRevision`）。本机操作者与审阅理由在页面字段中声明，绑定本机会话（不是身份认证）。后端缺失时如实拒绝，不产生版本。
6. **变化复核与修正任务**：「检查代码变化」对比工作区绑定的提交与仓库当前 HEAD，列出声明证据发生变化的待复核节点；「过程偏差检查（规则）」用 C 的规则引擎对照声明的期望步骤与提供的观察证据（错仓/错版本/无关证据返回 `UNKNOWN`）；「修正实现：创建开发任务」在已发布版本上创建 D 的权威修正任务（范围、证据、期望过程、验收条件都必填）；任务接手、提交回挂与实测核验由 D 的状态机接管，实测命令的退出码与输出摘要才是关闭偏差的凭据。改图不会自动修改程序。

**写入口保护**：所有 `POST /api/archloop/*` 都需要服务端签发的写会话（`GET /api/archloop/session`，HttpOnly Cookie）与配套的 `X-CSRF-Token` 头；缺失或不匹配时以 `FORBIDDEN_SESSION` / `FORBIDDEN_CSRF` 拒绝，跨站请求无法创建、修改或发布。

接口约定（CONTRACT_V1）、本轮来源与能力接线表见 `archloop/INTEGRATION_ROUND3.md`；所有 `/api/archloop/*` 端点接受 loopback Host 与同源 Origin 校验。

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

### 用什么厂商的 API（可选，国产与中转都能接）

传输层支持两种线协议，端点只从服务端环境变量读取；**任何 OpenAI 兼容的厂商都可直接使用，不需要改代码**：

| 变量 | 说明 |
| --- | --- |
| `PROJECTMIND_AI_API_KEY` 或 `OPENAI_API_KEY` | 密钥（只在服务端；日志与页面都不显示） |
| `PROJECTMIND_AI_MODEL` | 模型 ID，如 `deepseek-chat`、`qwen-plus`、`kimi-k2.6`、`glm-4-plus`、`gpt-4o-mini` |
| `PROJECTMIND_AI_BASE_URL` | 厂商端点，如 `https://api.deepseek.com/v1`；不设置则用 OpenAI 官方端点 |
| `PROJECTMIND_AI_PROTOCOL` | `auto`（默认）/ `responses` / `chat_completions`；`auto` 对 `api.openai.com` 用 Responses，其它端点用 `chat/completions` |

常见厂商（以各家控制台当前文档为准）：

```powershell
# DeepSeek
$env:PROJECTMIND_AI_API_KEY = "sk-..."; $env:PROJECTMIND_AI_MODEL = "deepseek-chat"
$env:PROJECTMIND_AI_BASE_URL = "https://api.deepseek.com/v1"
# 阿里云百炼 / 通义千问（OpenAI 兼容模式）
$env:PROJECTMIND_AI_API_KEY = "sk-..."; $env:PROJECTMIND_AI_MODEL = "qwen-plus"
$env:PROJECTMIND_AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# Moonshot / Kimi
$env:PROJECTMIND_AI_API_KEY = "sk-..."; $env:PROJECTMIND_AI_MODEL = "kimi-k2.6"
$env:PROJECTMIND_AI_BASE_URL = "https://api.moonshot.cn/v1"
# 智谱 GLM
$env:PROJECTMIND_AI_API_KEY = "...."; $env:PROJECTMIND_AI_MODEL = "glm-4-plus"
$env:PROJECTMIND_AI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
# 本地/自建（vLLM、Ollama、LM Studio、LiteLLM 代理等）
$env:PROJECTMIND_AI_API_KEY = "not-needed"; $env:PROJECTMIND_AI_MODEL = "本地模型名"
$env:PROJECTMIND_AI_BASE_URL = "http://127.0.0.1:11434/v1"
```

配置生效后打开 `/api/ai-status`（或在架构工作台看生成区提示）可确认：会显示模型、厂商主机与协议。
兼容端点里的 JSON 结构由本程序在服务端再校验一次——厂商不遵守 `response_format` 也不会把不合结构的图写进草稿。
不想自己拼厂商差异的话，也可以本地跑 [LiteLLM](https://github.com/BerriAI/litellm)（`litellm --model ...`）或其它 OpenAI 兼容网关，
然后把 `PROJECTMIND_AI_BASE_URL` 指向它。

点击按钮后，只会向配置的端点发送选中节点的人工演示描述、直接关联的变化文件名和最多 12,000 个字符的 Git 差异。请求使用 `store: false`；密钥只留在本地服务端环境变量中，不进入地图文件或浏览器。页面把返回内容标为“AI 候选”，要求人对照来源复核。未配置时其它功能照常可用。API 调用可能产生费用；是否能成功取决于所用账户、模型和网络。

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
