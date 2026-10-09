# B / Code Facts：真实提交中的代码定义

责任人：王海宁；任务 [#30](https://github.com/LingweiXingzhi/projectmind-core/issues/30)。

## 目的与范围

B 从指定 Git 提交提取 Python 定义的名称、类型、行号，供 C 复核和消费。
这些是静态声明事实，不证明函数会被执行、属于某项功能，或关系已经团队确认。
本扩展不执行被分析的源码，不生成职责解释，不写人工地图或正式 Project Model。

开发候选基线是 `7484d44ddeac3c054ca3ba68f92293d965bb615c`，不声称团队已批准该 SHA。
来源为 [PR #22 的首版参考包](https://github.com/LingweiXingzhi/projectmind-core/pull/22)，
参考提交 `0c46747147f765260bf2033f6eae40189b58ca0c`。
本次只新增本目录及 `tests/test_code_facts.py`，通过真实 Extension Host 自动发现。

## 改进依据

| 依据 | 本次处理 |
| --- | --- |
| `MVP_INTERFACES.md` 的 B 交换约定与 `EXTENSION_INTERFACE.md` 的目录边界 | 接入实际 Core 的独立页面和数据路由，保持既有 CodeFacts 字段 |
| Model PR #1 的 `PROJECT_ANALYSIS.md`：代码事实与候选/团队决定分开 | 保持定义证据，不代替 C 或批准架构 |
| Core PR #21 的 V1 职责 | B 只修改自己的扩展和测试；公共文件由集成人协调 |
| 已复现页面修改空格路径、GET 拆开 Unicode 文件名 | 原样保留每条路径，只按 ASCII LF/CRLF 分隔 |
| 已复现部分克隆自动补取 blob 并写入对象库 | 禁止惰性取件；缺失对象明确失败，用户自行补全后重试 |

Model PR #1 与 Core PR #21 仍待审，本次未把它们当作新产品功能批准。
Context Authority PR #29 的消费实验也不改变 B 的公共输出。

## 运行与页面

需要 Python 3.10+ 和支持 `--no-lazy-fetch` 的 Git。本次实测 Git 2.50.1。
不支持该 Git 选项时明确失败，不退回可能自动取件的读取方式。
无新增 Python 包，无需配置 API Key。

在仓库根目录启动：

```sh
python3 app.py
```

打开 `http://127.0.0.1:8765/ext/code_facts`，或从主页扩展侧栏进入“代码事实”。
页面从真实 `/api/snapshot` 取得版本初值，点击后才扫描。文件和定义可搜索，
显示限定名称、中文类型及 1 起始行号；首尾有空格的路径用引号显示以区分不同文件，JSON 保留原始文件名。
下载包含完整结果，不受筛选影响。
更改输入或请求失败会清除旧结果并禁用旧下载，迟到响应不会覆盖新查询。

## Python 与 HTTP 接口

```python
from extensions.code_facts.facts import collect_code_facts

facts = collect_code_facts(repo, revision, paths=None)
```

- `repo`：已解析的本地 Git 仓库根目录，不接受子目录或裸仓库。
- `revision`：直接指向提交的完整 40 或 64 位小写 SHA。拒绝 `HEAD`、缩写、标签对象及缺失提交。
- `paths=None`：扫描该提交的所有路径；`paths=[]`：不选择任何文件。
- 路径为精确相对文件名，不是目录或 glob；使用 `/`，禁止路径穿越、反斜线和控制字符。
  首尾空格及其他合法 Unicode 字符保留。
- 定义类型为 `function / async_function / class / method / async_method`。
  `name` 用点号表示词法嵌套；`line` 指向 `def`、`async def` 或 `class`，不指装饰器。
  这五种类型不是调用图或稳定 API 承诺；消费者如需收窄类型，先与 B 协调。

响应固定为 `{revision, files, skipped}`。每个文件为 `{path, language:"python", entries}`，
每个定义为 `{name, kind, line}`，跳过项为 `{path, reason}`。
不支持的语言、符号链接、子模块、无法解析的编码/语法进入 `skipped`，不猜造定义。
缺失路径、坏输入、不可用对象使整个请求明确失败，不偷偷切换版本。

POST `/api/extensions/code_facts` 接收 JSON 对象：

```json
{"revision":"7484d44ddeac3c054ca3ba68f92293d965bb615c","paths":["app.py"]}
```

GET 同一路径接收 `revision` 与可选 `paths` 查询参数。
GET 的 `paths` 用 LF 或 CRLF 分隔，省略或空字符串表示扫描所有文件；
POST 的空列表保留“不选文件”含义。只接受 `revision` 与 `paths`，错误返回 HTTP 400 和 `{error}`。
空 GET 不自动扫描：调用者必须先提供完整提交 SHA。

限制：最多 2,000 文件；单 Python 文件 1 MiB，超限跳过；累计 Python 内容 16 MiB，超限拒绝；
每条 Git 命令 10 秒。真实宿主 POST 请求上限仍为 65,536 字节，未修改。
输出规模仍取决于静态定义数，首版不提供全语言解析或缓存增量分析。

## C 如何消费真实结果

首先明确仓库来源是 `https://github.com/LingweiXingzhi/projectmind-core.git`，
并让 Core 指向这个本地仓库；`Snapshot.repository` 的目录名本身不能证明仓库身份。
以下调用从同一个实际 Core 服务取得快照和事实：

```python
import json
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8765"
with urlopen(base + "/api/snapshot", timeout=10) as response:
    snapshot = json.load(response)
request = Request(base + "/api/extensions/code_facts",
    data=json.dumps({"revision": snapshot["revision"]}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
with urlopen(request, timeout=30) as response:
    facts = json.load(response)
assert facts["revision"] == snapshot["revision"]
```

C 的证据只能从这些真实 `files` 路径选择，不能把旧 `user.py` 演示结果与本项目快照混用。
SHA 相同不证明人工地图适用；当前地图为 `curated_demo`，核查适用版本仍 UNKNOWN。
本次可验证 Core/B 交换，C 的 `map_proposal/` 尚未实现，不声称正式 C 联调已完成。

## 验证与待协调事项

```sh
python3 -m unittest discover -s tests -v
```

B 测试直接使用实际 `app.make_handler` 与 `extension_host`，不导入原型 reference 宿主。
覆盖真实 Git SHA-1/SHA-256、历史/工作区隔离、静态名称和行号、输入和容量边界、
部分克隆缺对象、真实 HTTP、空格/Unicode 路径与原地图路由。
页面路径和下载还需按 PR 中的实际浏览器记录复核。

Project Model Impact：`UPDATE`（建议）。B 从参考原型变为实际扩展，建议人审后登记其实现状态和代码映射；
本次不修改正式模型、公共契约或主图。
仍需团队批准共同基线、C 真实消费及两位非作者的审核；GitHub 的 CLEAN/MERGEABLE 不构成合并授权。
