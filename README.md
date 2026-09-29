# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平台

## 本地运行第一条演示主线

需要 Python 3.10+ 和 Git。在本仓库根目录运行：

```powershell
python app.py
```

然后打开 <http://127.0.0.1:8765>。查看地图和 Git 变化无需安装 Python 包或配置 API Key。

页面显示 ProjectMind 自身的一张**人工整理的演示功能图**。点击节点可以查看职责、关系、关键入口，并读取固定 Git 提交中的真实文件内容。顶部显示此次证据所对应的完整提交 ID；若来源文件不在该提交中，页面会标记“此版本缺失”。“导出当前摘要”会生成带提交 ID 的 Markdown 文件，方便交接。

“对照两个真实提交”默认比较当前提交与它的父提交。也可以输入另一个**完整提交 ID**作为基准。变化文件来自 Git；若节点声明的来源文件出现在变化中，节点只会标记为“待复核”。导出的 Markdown 摘要包含这次比较。文件变化不能证明职责或架构一定改变。

可选的“让 AI 解释”按钮仅在配置后启用。在启动程序的同一个 PowerShell 窗口设置环境变量，再运行 `python app.py`：

```powershell
$env:OPENAI_API_KEY = "你的 API Key"
$env:PROJECTMIND_AI_MODEL = "你账户可使用的模型 ID"
python app.py
```

点击按钮后，只会向 OpenAI 发送选中节点的人工演示描述、直接关联的变化文件名和最多 12,000 个字符的 Git 差异。请求使用 `store: false`；密钥只留在本地服务端环境变量中，不进入地图文件或浏览器。页面把返回内容标为“AI 候选”，要求人对照来源复核。未配置时其它功能照常可用。API 调用可能产生费用；是否能成功取决于所用账户、模型和网络。

这一步验证“图 → 详情 → Git 来源 → 版本变化 → 待复核候选 → 可选 AI 解释 → 导出”的运行路径。演示图不代表自动识别出的架构，也不代表团队批准的正式 Project Model。

运行核心验证：

```powershell
python -m unittest discover -s tests -v
```
