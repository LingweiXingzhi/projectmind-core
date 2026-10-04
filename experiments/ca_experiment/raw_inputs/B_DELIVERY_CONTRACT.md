# 10月1日B部分代码首版（王海宁）

日期：2026-10-01。负责人：王海宁。模块：B / Code Facts。

## 共享用途和当前状态

本目录放在独立共享分支 `docs/b-first-version-wang-haining-2026-10-01` 的 `collaboration/b/2026-10-01-wang-haining/`，供 C 查看 B 的实现、接口和样例。它是可独立运行的参考原型，**尚未接入团队主线，也未完成实际 Core 与 C 联调**。

目录内的 `extensions/`、`tests/` 和 `reference/` 属于这个原型。共享这些文件不等于将其接入仓库根目录的实际扩展、测试或公共宿主；正式接入需要与 A/C 确认。参考目录中的宿主副本也不应覆盖团队公共文件。

B 提供“指定提交中有哪些 Python 定义、位于哪个文件哪一行”的事实。C 可据此开展后续分析；这些结果不直接表示功能职责、运行时可达性或已确认的架构。

## 给 C 的接口和样例

```python
collect_code_facts(repo, revision, paths=None) -> dict
```

| 输入 | 含义 |
| --- | --- |
| `repo` | 本地 Git 仓库根目录，不能是其子目录 |
| `revision` | 直接指向 commit 的完整小写 SHA：40 位 SHA-1 或 64 位 SHA-256；短 SHA、HEAD、标签对象和非 commit 对象拒绝 |
| `paths=None` | 扫描该提交中的全部文件 |
| `paths=[]` | 明确不选任何文件 |
| `paths=["user.py"]` | 精确的仓库内相对文件路径；不支持目录或通配符，重复路径去重、结果按路径排序 |

返回值只有 `revision`、`files`、`skipped` 三个顶层字段：

```json
{
  "revision": "b0e7d56b1d148b9489c8330b1ed5718ad1f037a2",
  "files": [
    {
      "path": "user.py",
      "language": "python",
      "entries": [
        {"name": "login", "kind": "function", "line": 2},
        {"name": "UserService", "kind": "class", "line": 5},
        {"name": "UserService.save", "kind": "method", "line": 6},
        {"name": "UserService.fetch", "kind": "async_method", "line": 9}
      ]
    }
  ],
  "skipped": []
}
```

- `name` 是词法限定名，例如 `Class.method`、`outer.inner`。
- `kind` 可为 `function`、`async_function`、`class`、`method`、`async_method`。
- `line` 是 `def`、`async def` 或 `class` 的 1 起始行号，不是装饰器行号。
- 类体中的直接函数定义为方法；方法内的嵌套函数为函数。条件分支内的定义也会列出。
- 结果读取指定提交中的 Git 对象，不混入工作区未提交内容，不执行被分析的源码。
- 不存在的指定文件或无效输入使请求失败；存在但不支持或无法解析的文件进入 `skipped`，其他文件继续处理。
- 真实联调须获取同一仓库、同一 SHA 的 Snapshot 与 CodeFacts，并核对 `CodeFacts.revision == Snapshot.revision`。当前数据不含函数体、参数、调用关系或功能说明；增加公共字段前与 C/A 协调。

原型临时演示仓库的历史实际全量响应见 [examples/code-facts.json](examples/code-facts.json)；它不代表 `projectmind-core` 中存在 `user.py` 等文件，C 可用它设计固定样例，真实联调须获取同一仓库、同一 SHA 的 Snapshot 与 CodeFacts。错误响应见 [examples/errors.json](examples/errors.json)，HTTP 检查记录见 [examples/http-checks.json](examples/http-checks.json)。以上 JSON 中的提交 SHA 对应历史演示样本；新运行的临时演示仓库可能生成不同 SHA。

## 来源版本

- Core 兼容性参考提交：`7484d44ddeac3c054ca3ba68f92293d965bb615c`。`reference/extension_host.py` 为该提交的宿主源码副本，用于原型兼容性验证。
- 历史演示样本提交：`b0e7d56b1d148b9489c8330b1ed5718ad1f037a2`。
- 本次共享分支从当前 main `7484d44ddeac3c054ca3ba68f92293d965bb615c` 建立，仅用于存档共享。该提交同时是原型兼容性参考，**不表示团队已经批准正式共同开发基线**。

## 独立运行

需要 **Python 3.10+ 和 Git**，不需要第三方 Python 包或模型 API。

从仓库根目录进入这个参考包：

```sh
cd collaboration/b/2026-10-01-wang-haining
python3 run_demo.py --port 8877
```

打开 <http://127.0.0.1:8877/ext/code_facts>。使用 8877 是为了便于与现有服务同时查看；如果被占用，选择其他空闲端口。

默认演示只会在新建的临时目录创建 Git 样本仓库，在终端按 Ctrl+C 停止后清理。启动无需修改团队工程。

只读分析已有本地仓库时，在上述参考包目录运行：

```sh
python3 run_demo.py --repo "/本地仓库的绝对路径" --port 8877
```

`--repo` 指向的现有仓库不会被初始化、提交或改写；提取仅读取其提交与 blob。浏览器不能切换任意仓库路径。

## 页面验收步骤

1. 点击“提取代码事实”：演示应得到 **3 个可解析文件、7 个定义、3 个跳过文件**，显示本次完整 SHA。
2. 查看 `user.py`：`login` 为函数第 2 行，`UserService` 为类第 5 行，`.save` 为方法第 6 行，`.fetch` 为异步方法第 9 行。
3. 搜索 `fetch`：只展示 `UserService.fetch`。下载 JSON 仍包含本次全部提取结果。
4. 文件路径输入 `missing.py`：旧结果清空、下载禁用；提取后提示该文件不在指定提交中。
5. 清空路径重新提取：结果恢复。

页面截图见 [preview.jpg](preview.jpg)，步骤证据保存在 `self-check/`。

## HTTP 适配

- 页面：`GET /ext/code_facts`。
- POST：`POST /api/extensions/code_facts`，请求头 `Content-Type: application/json`，请求体 `{ "revision": "完整小写SHA", "paths": ["user.py"] }`。省略 `paths` 则扫描全部。
- GET：`GET /api/extensions/code_facts?revision=完整小写SHA&paths=user.py`，多路径采用 URL 编码的换行分隔字符串；同名多值按 Core 规则只取第一项。
- 预期输入错误：HTTP 400 与 `{ "error": "说明" }`；仅支持 GET/POST，不建议消费者依赖错误文案逐字匹配。
- 适配器使用 `handle(context, method, data)`，仓库来自 `context.repo`。
- `run_demo.py` 是独立演示外壳；正式团队服务的路径、加载和 C 消费仍需接入时核验。

## 已有验证与边界

在参考包目录可运行原型测试：

```sh
python3 -m unittest discover -s tests -v
```

**21 项自动化测试通过、11 项实际 HTTP 检查通过**，以及浏览器操作和下载内容比对，均为原型期间已经完成的验证结果。这次共享打包核对文件完整性和源码一致性，没有以团队环境重新执行联调。

历史记录见 [VERIFICATION.md](VERIFICATION.md) 和 [SELF_CHECK.md](SELF_CHECK.md)。报告中“未修改团队仓库或 GitHub”等表述描述的是当时独立原型阶段；本次计划通过共享分支发布参考目录，不能将历史记录理解为当前 GitHub 状态。为便于共享，报告命令改为可移植写法，下载记录只保留文件名并注明隐去本机路径。

首版范围与限制：

- 仅 Python 静态函数、类、方法定义；不提取导入名称、lambda、动态生成函数、调用图或职责说明。
- 最多选择 2000 个文件；单个 Python 文件上限 1 MiB，单次解析 Python 内容上限 16 MiB，Git 命令超时 10 秒，POST 请求体上限 65,536 字节。
- 符号链接、子模块、非 UTF-8 文件名及当前 Python 解析器无法处理的语法会跳过；源码编码按声明检测。
- 64 位 SHA 输入形式已支持，但历史测试使用 SHA-1 仓库，实际 SHA-256 仓库尚未验收。
- 尚未完成团队实际 Core 服务、C 模块的真实消费和共同主线回归。

## 正式接入前的协作要求

1. A 确认共同开发基线、B 的 Issue 与可修改文件范围；C 确认字段、版本核对和失败处理。
2. 在 B 自己的开发分支接入并联调；如果涉及 `app.py`、公共宿主、共享页面、公共接口或主图数据，先在群里协调。
3. 完成后提交 PR，**至少两个人审查并明确确认没有问题，同时收到明确合并指令后，才可以合并**。
4. 测试通过、PR 为 CLEAN/MERGEABLE 或共享参考目录已经上传，都不构成自动合并 main 的授权。

当前参考原型不发布正式 Project Model；未来接入新增能力时，应提出模型更新建议并由团队确认。
