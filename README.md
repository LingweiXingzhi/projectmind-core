# projectmind-core
面向复杂项目的HUMAN-AI协同认知与管理平台

## 本地运行第一条演示主线

需要 Python 3.10+ 和 Git。在本仓库根目录运行：

```powershell
python app.py
```

然后打开 <http://127.0.0.1:8765>。无需安装 Python 包或配置 API Key。

页面显示 ProjectMind 自身的一张**人工整理的演示功能图**。点击节点可以查看职责、关系、关键入口，并读取固定 Git 提交中的真实文件内容。顶部显示此次证据所对应的完整提交 ID；若来源文件不在该提交中，页面会标记“此版本缺失”。“导出当前摘要”会生成带提交 ID 的 Markdown 文件，方便交接。

这一步只验证“图 → 详情 → Git 来源 → 导出”的运行路径。演示图不代表自动识别出的架构，也不代表团队批准的正式 Project Model；Git 变化比较与 AI 解释仍是后续任务。

运行核心验证：

```powershell
python -m unittest discover -s tests -v
```
