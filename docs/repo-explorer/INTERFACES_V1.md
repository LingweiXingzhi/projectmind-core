# Repo Explorer 接口文档 · schemaVersion 1

状态：与提交 939cb59082f90bc30f6a2d30fa439b3a424bec1a（feat/repo-explorer-main-v1 HEAD）一致。其中 `capabilities.changes=true` 自提交 4f2d3da30cd16b7790c33b346f997f63debd71d5 起生效（此前该值为 false 且 changes 接口尚未交付）。
本文档是任务书《PROJECTMIND_REPO_EXPLORER_4_PERSON_PLAN.md》§6 的落地版本。所有新接口都在 `/api/repo-explorer/` 前缀下；现有 `/api/snapshot`、`/api/evidence`、`/api/compare`、`/api/export`、`/api/explain`、`/api/extensions*` 的语义不变。

## 通用约定

- 成功响应带 `schemaVersion: 1`。
- 错误响应：相应 HTTP 状态码 + `{"error": {"code": "...", "message": "..."}}`。
- HTTP 来源边界（仅新接口）：`Host` 必须是 `127.0.0.1:<port>` 或 `localhost:<port>`；`Origin` 头若存在，必须是本服务来源；`Origin: null` 与外部来源一律 403 `FORBIDDEN_ORIGIN`；不发送任何 CORS 头。旧接口未加此校验（避免变更既有行为）——这是当前暴露面的一项已知限制。
- 上下文：`POST open` 由服务端生成 `projectId`，绑定 `(仓库根 realpath, 完整 SHA, 该提交清单)`。上下文不可变；注册表为容量 4 的 LRU，命中即刷新新近度；淘汰后的 projectId 返回 410 `CONTEXT_EVICTED`；带 `revision` 参数的接口要求 `revision == 该 projectId 绑定 SHA`，否则 400 `REVISION_MISMATCH`。同一 `(repo, SHA)` 重复 open 幂等返回同一 projectId。
- 内容准入（R2-Q5）：`tree`/`file`/`symbols`/`relations` 一律以 open 时建立的 allowed 集合与 skipped 清单为准；被跳过的文件在树中保留入口并附 `skippedReason`（`kind` 枚举仍只有 `directory|file`）；任何内容接口都不绕过 open 时的累计预算。
- 预算（open 时执行，顺序固定）：单文件 1 MiB 先行 → 其余按路径字典序累计 16 MiB → 内容索引最多 2000 个文件。预算按实际读取的 blob 字节计费，包括最终解码失败的文件。被跳过文件的原因文案固定；任一跳过发生即 `coverage.partial = true`。
- 仓库准入：`repoPath` 必须是本机绝对路径，且 `git rev-parse --show-toplevel` 的 realpath 与之相等。Git 读取统一使用强化运行器：参数数组、`--no-lazy-fetch`、`--no-replace-objects`、剥离继承 `GIT_*`、30 秒超时；不安装依赖、不执行目标项目代码、不为读取内容联网。

## 1. POST /api/repo-explorer/open

请求：`{"repoPath": "本机绝对路径", "revision": "HEAD" | "完整SHA"}`（revision 缺省 HEAD）。

响应：`schemaVersion`、`projectId`、`repositoryName`、`revision`（完整 SHA）、`capabilities{files, symbols, imports, changes}`、`coverage{trackedFileCount, indexedFileCount, skipped[{path, reason}], partial}`。

当前能力：`files=true`、`symbols=true`（`python_ast_v1`）、`imports=true`、`changes=true`。
能力值**表达该部署实际能提供的能力**（r02 Q6）：解析器未接入的部署里对应的 `symbols`/`imports` 为 `false`，其端点随后返回 `status="unavailable"`，`open` 不会声明一个自己的端点会拒绝的能力。
`trackedFileCount` 只统计普通 blob（100644/100755）且文件名可 UTF-8 解码的条目；`indexedFileCount` 是实际完成编码处理的文件数（两者都不是"成功解析符号"的计数）。

错误：`REPO_INVALID`（路径无效/非绝对/非仓库根）、`REVISION_INVALID`（非 HEAD/完整 SHA、无法解析、标签对象）。

## 2. GET /api/repo-explorer/tree?projectId&revision

响应：`schemaVersion`、`projectId`、`revision`、`entries[{path, parentPath, kind, language}]`、`coverage`。

- 条目仅来自该提交清单：目录为文件路径的祖先目录派生，无合成空根节点；顶层 `parentPath` 为 `""`；按 path 字典序稳定排序。
- `language`：`.py`/`.pyi` 为 `"python"`，其余为 null；目录恒为 null。
- 被跳过文件保留条目并附加 `skippedReason`（symlink="符号链接，首版不读取"、submodule="子模块，首版不读取"、超 1 MiB、二进制内容、编码不支持、文件名非 UTF-8、2000 文件上限、16 MiB 总量超限）。

## 3. GET /api/repo-explorer/file?projectId&revision&path&startLine&endLine

- `startLine` 缺省 1，`endLine` 缺省 200；单次最多 500 行（`LINE_RANGE_TOO_LARGE`）。
- 范围裁剪到文件范围；`truncated=true` 表示文件中仍有未返回的行（包括请求窗口之前的行）。
- 内容保留原始行尾（\r\n、\r、\n；U+2028 等字符不作为换行，行号与 Python AST 一致）。
- 解码范围：PEP 263 编码声明只对 `.py`/`.pyi`（大小写不敏感）生效；其它可浏览文本按 UTF-8 解码。仅首行"看起来像"编码声明的普通文本文件仍可正常浏览，不会因该行被判为编码失败（R48-08）。
- 空文件：`startLine=0, endLine=0, totalLines=0, content="", truncated=false`。
- 非空文件 `startLine > totalLines` → 400 `LINE_RANGE_INVALID`。
- 路径校验：仅接受 `/` 分隔的仓库内相对路径；绝对路径、反斜杠、`:`、空/`.`/`..` 段、控制字符一律 400 `PATH_INVALID`；不在清单 → 404 `PATH_NOT_IN_REVISION`；在清单但被跳过 → 403 `FILE_SKIPPED`（message 为 open 时的原因）。

## 4. GET /api/repo-explorer/symbols?projectId&revision&path

`parser="python_ast_v1"`（B 的 `repo_index/symbols.py` `parse_symbols` 已接入；`legacy_code_facts` 过渡及"结束行为 null + 范围不完整警告"的约定随之撤销）：

- 源码在上下文绑定的完整 SHA 上、经 A 的 Git 读取/解码层取得后交给纯函数解析器；解析器本身不读文件、不执行目标代码。
- `status="ok"`：文件被成功处理（含 0 符号的空文件）；`symbols[]` 每项 `{name, qualified_name, kind, start_line, end_line, docstring}`。`qualified_name` 按词法嵌套定义拼接，不推断运行时归属；`start_line`/`end_line` 为包含式源码范围（不含前置装饰器行）；`docstring` 经 `ast.get_docstring(clean=True)` 清理，最多保留 2000 字符，截断时在 warnings 提示。
- `status="parse_error"`：语法或解码失败；`symbols=[]`，warnings 含错误行号与简要原因，不含整份源码。
- `status="unsupported"`：非 `.py`/`.pyi` 文件。
- **无解析器部署**（B 尚未接入，例如只交付了浏览层的实例）：`status="unavailable"`、`parser=null`、`symbols=[]`，warnings 明确说明解析器未接入；**不**包装为成功空结果。
- 准入与 file 相同（404 / 403 `FILE_SKIPPED`）。读取时 Git 对象不可用仍按 F5 分类区分 `OBJECT_MISSING`（结构化探针确证缺失）与 `REPO_UNREADABLE`（其余 Git 失败），不伪装成成功空结果。

## 5. GET /api/repo-explorer/relations?projectId&revision&path

C 的 `repo_index/imports.py` `parse_imports` 已接入（`status="unavailable"` 占位行为撤销）：

- 响应：`schemaVersion`、`projectId`、`revision`、`path`、`status`、`imports`、`dependents`、`importScan`、`warnings`。
- `imports` 保留 C 的原始字段（`kind/module/level/name/alias/line/end_line`），并由 A 增加 `resolution{status, targetPath, candidates}`：`status` 为 `resolved`、`unresolved`、`ambiguous`；唯一明确目标才填 `targetPath`，否则为 null；`candidates` 为候选相对路径列表（字典序），每项都是清单中可打开的具体源码 blob（`x.py` 或 `x/__init__.py`）。
  - **搜索根与包深度（r04 R3-Q1）**：文件的包深度 `d` 按其**搜索根**度量——搜索根是包含该文件的最大连续包目录链之上的那一层（`src/core/mod.py` → 搜索根 `src`、包 `core`、`d=1`；`src/core/sub/mod.py` → 包 `core.sub`、`d=2`；直接位于搜索根下的 `.py`（如 `src/tool.py`）以及 `__init__.py` 缺失的命名空间包内文件都**没有包语境**）。
  - **相对导入**：仅允许 `1 ≤ level ≤ d`；解析 = 当前包上移 `level−1` 个包组件后拼接 module/name 组件。`level > d`（越出顶层包，**即使仓库根或搜索根内恰好存在同名文件也不命中**）、`d=0`（无包语境）、无候选 → `unresolved`。
  - **绝对导入**：在**仓库根与该文件自身搜索根**下查找，不跨其它搜索根匹配。
  - **`from M import name` 的判定顺序（r03 R2-Q7）**：
    1. `M/name` 若真实存在（`name.py` 或 `name/__init__.py`）→ 按名称读法连接（唯一 → `resolved`，多个 → `ambiguous`）。
    2. 否则该语句的依赖是**模块 `M` 自身**：`M.py` 与 `M/__init__.py` 只有一个是具体源码 blob 且是**普通模块文件** → `resolved` 到它（例如 `from .utils import helper` → `pkg/utils.py`）；两者同时存在 → `ambiguous` 并列出两者（同名文件与同名包并存）；都没有 → `unresolved`。
    3. **唯一不能确认的情形**：模块 `M` 的具体源码 blob 只有包 `__init__.py`。此时 `name` 可能是 `__init__` 内定义的属性或重导出，首版不做跨文件推断 → `unresolved`，原因"可能是包属性或重导出"，**不得**把 `__init__.py` 当作 `targetPath`。`import M` 与 `from M import *` 不受此限制（它们的目标就是模块本身）。
  - `ambiguous`：同一模块名下存在**多个真实源码 blob** 时保留全部候选并显式标注歧义——包括 `x.py` 与 `x/__init__.py` 并存，以及仅扩展名大小写不同的两个真实文件（如 `dup.py` 与 `dup.PY`）。候选按字典序稳定排序，结果**不依赖**进程哈希种子。
  - 候选指向目录但该目录没有 `__init__.py`（PEP 420 命名空间包形态）且**没有任何具体源码候选**时 → `unresolved`，warnings 注明"可能的命名空间包，无源码入口"。同名目录**不得**遮蔽旁边的真实 `helper.py`（存在具体候选时照常解析）。
  - 每个 `unresolved` 记录的原因（无包语境 / 越出顶层包 / 命名空间包 / 未找到候选）写入 `warnings`。
- `dependents` 每项 `{path, line, end_line}`，仅来自成功解析且 `resolution.status="resolved"` 到当前文件的导入记录；不确定的反向关系不展示成已确认依赖。空结果的界面文案固定为"已解析范围内未发现导入本文件的记录"。
- `importScan{scanned, parseFailed, total}`（r03 R2-Q8）：导入扫描自身的覆盖统计。分母 `total` 为 allowed 集合中扩展名（大小写不敏感）为 `.py`/`.pyi` 的文件数——与解析器支持范围一致，`consumer.PY` 同样计入并被扫描；`parseFailed` 为解析失败数。
- `status` 为当前文件的 C 解析结果：仅成功解析（含空结果）为 `ok`；语法/解码失败保留 `parse_error`。存在解析失败或未被 open 纳入内容索引（预算、编码或类型跳过）的 Python 文件时，warnings 如实写明**覆盖缺口**及其数量；任一缺口存在时**不得**表述为完整扫描结论。warnings 只陈述缺口本身——"已解析范围内未发现导入本文件的记录"只在 `dependents` 确实为空时由界面显示，不会与一个非空列表同时出现。
- **无解析器部署**（C 尚未接入）：`status="unavailable"`、`imports=[]`、`dependents=[]`、`importScan=null`，warnings 明确说明解析器未接入；**不**包装为成功空结果。
- 准入与 file 相同（404 / 403 `FILE_SKIPPED`）。

## 6. GET /api/repo-explorer/changes?projectId&base&target

- `base`、`target` 都必须是该 projectId 仓库内的完整 40/64 位提交 SHA（`HEAD`、短 SHA、分支名、标签 → 400 `REVISION_INVALID`；解析结果必须等于输入）。任务书签名即不含 revision 参数。
- 响应：`schemaVersion`、`projectId`、`baseRevision`、`targetRevision`（回传实际解析的完整 SHA）、`changes[{status, path, oldPath}]`。
- `status` 为 Git name-status 原始字母（`-M` 开启 rename 检测）：A/M/D/R 基础状态；R/C 携带 `oldPath`；其余字母（如 T）原样返回不丢弃。
- 打开相应版本源码：删除文件用 base 上下文读取，新增用 target 上下文；前端按需对 base/target 各自 open（幂等）。

## 启动模式（app.py）

- `python app.py --repo "<绝对路径>" --port 8765`：无地图启动，仓库浏览为主视图；旧地图接口返回 `MAP_REQUIRED`；扩展路由 503。
- `python app.py`：默认演示地图（旧功能保留并标记"演示"）+ 本 checkout 的仓库浏览入口。
- `python app.py --map <地图>`：旧地图模式逐字保留（含"外部仓库必须 --map"校验），仓库浏览关闭。
- 无地图实例不会在目标仓库创建 Worklog/Continuity 存储（扩展路由在任何 handler 之前阻断）。
