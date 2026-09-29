# 比赛版独立扩展接口

> 状态：`feat/19-extension-seams` 已实现的本地扩展入口。此接口供四人并行接入首版 Demo，不代表正式 Project Model 或长期插件标准。

## 新增一个功能

1. 在 `extensions/` 下新建自己的目录，例如 `extensions/code_facts/`。目录名以小写字母开头，后面只能用小写字母、数字或下划线，最多 40 个字符。各负责人只改自己的扩展目录和对应测试。
2. 放入 `extension.py`，定义 `EXTENSION = {"title": "显示名称", "description": "一句话说明"}` 和 `handle(context, method, data) -> dict`。`method` 为 `GET` 或 `POST`；`data` 是查询参数或请求 JSON 对象。返回值必须能编码为 JSON 对象。
3. 可选放入自包含的 `index.html` 作为功能页面。暂不提供扩展目录内其他静态资源的路由；页面需要的脚本和样式请写在该页面里。不提供页面时使用内置通用结果页，它只调用 GET。
4. 重启本地服务。启动时发现扩展，主页侧栏自动显示可用扩展入口；无须修改 `app.py`、`web/index.html` 或 `web/app.js`。可以参考已交付的 `extensions/project_summary/extension.py`。

如果功能需要拆成多个 Python 文件，可在自己的目录加入 `__init__.py`，再用 `from extensions.code_facts.facts import ...` 这类绝对导入引用自己的文件。

扩展运行在本地服务的同一个 Python 进程中，因此只接收团队审查过的代码。服务使用多线程处理请求；扩展不要依赖未经保护的全局可变状态。扩展增加的是独立功能页和数据接口，**不会自动变成人工功能图中的节点**；主图职责和关系仍按团队的人审流程调整。

最小样例：

```python
EXTENSION = {"title": "代码事实", "description": "展示指定提交的真实代码入口"}

def handle(context, method, data):
    if method != "GET":
        from extension_host import ExtensionError
        from http import HTTPStatus
        raise ExtensionError(HTTPStatus.BAD_REQUEST, "只支持 GET")
    snapshot = context.snapshot()
    return {"revision": snapshot["revision"], "files": []}
```

此样例仅说明接入形状；`files: []` 不是已实现的代码事实提取。

## 服务与数据约定

| 入口 | 行为 |
|---|---|
| `GET /api/extensions` | 列出扩展 ID、标题、说明、状态、页面和数据入口；加载失败的目录标为 `unavailable`。 |
| `GET /ext/<id>` | 打开扩展自己的页面，或内置通用结果页。 |
| `GET /api/extensions/<id>?key=value` | 调用 `handle(context, "GET", data)`；查询参数同名多值只取第一项。 |
| `POST /api/extensions/<id>` | 接收不超过 65,536 字节的 JSON 对象，调用 `handle(context, "POST", data)`。 |

`context.repo` 是已解析的 Git 仓库根目录，`context.map_path` 是当前人工地图文件路径，`context.snapshot()` 返回现有快照，`context.compare(base, target)` 返回现有比较结果。扩展若读取代码，必须明确指定 Git 提交；不要把工作区文件误报为提交事实。地图目前仍没有独立版本身份，不能因为拿到了 `snapshot.revision` 就说地图已核查适用该代码提交。

处理可预期的输入错误时抛 `ExtensionError(HTTPStatus.BAD_REQUEST, "说明")` 等；返回 `{"error": "说明"}` 并配合相应 HTTP 状态。未知扩展为 404，加载失败为 503，扩展内部意外异常为不暴露细节的 500。扩展自行决定业务字段，但跨人交换的字段须按 [接口约定](MVP_INTERFACES.md) 固定样例及错误方式。修改已被其他功能使用的字段前，按 [协作约定](COLLABORATION_CONTRACT.md#5-接口变更办法) 通知消费者。

## 四人接入位置

- A 负责现有主图、共同运行入口和公共接口；只有要把结果**嵌进主图**时才需改共享前端或主图数据。
- B 可在 `extensions/code_facts/` 实现代码事实页面和数据接口。
- C 可在 `extensions/map_proposal/` 实现候选结构页面和数据接口。
- D 可在 `extensions/handoff/` 实现交接页面和数据接口。若要独立下载，可在自己的页面实现。

各扩展分别开 Issue 和 PR，附固定输入、输出、错误样例及验收步骤。先在同一基线各自开发，再按团队 SOP 集成。扩展路由和入口自动生成并不消除业务依赖：例如 C 真正消费 B 的代码事实时，仍需核对同一个完整 Git SHA、字段含义和错误行为。
