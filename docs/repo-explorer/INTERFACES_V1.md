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

当前能力：`files=true`、`symbols=true`（`legacy_code_facts` 过渡解析器）、`imports=false`、`changes=true`。
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
- 空文件：`startLine=0, endLine=0, totalLines=0, content="", truncated=false`。
- 非空文件 `startLine > totalLines` → 400 `LINE_RANGE_INVALID`。
- 路径校验：仅接受 `/` 分隔的仓库内相对路径；绝对路径、反斜杠、`:`、空/`.`/`..` 段、控制字符一律 400 `PATH_INVALID`；不在清单 → 404 `PATH_NOT_IN_REVISION`；在清单但被跳过 → 403 `FILE_SKIPPED`（message 为 open 时的原因）。

## 4. GET /api/repo-explorer/symbols?projectId&revision&path

当前 `parser="legacy_code_facts"`（过渡，来自现有公开接口 `collect_code_facts`）：

- `status="ok"`：文件被解析器成功处理（含 0 符号的空文件）；`symbols[]` 每项 `{name, qualified_name, kind, start_line, end_line=null, docstring=null}`；`warnings` 固定含"legacy_code_facts 不提供结束行，源码范围不完整"。
- `status="parse_error"`：收集器 skipped 记录中因编码/语法解析失败（如语法错误文件）；`symbols=[]`，warnings 含原因。
- `status="unsupported"`：非 `.py` 文件或其他不支持类型。
- B（`repo_index/symbols.py` 的 `parse_symbols`）交付接入后：`parser="python_ast_v1"`，补齐 `end_line` 与 `docstring`，本节的 null/警告约定随之撤销。
- 准入与 file 相同（404 / 403 `FILE_SKIPPED`）。

## 5. GET /api/repo-explorer/relations?projectId&revision&path

当前 C（`repo_index/imports.py` 的 `parse_imports`）尚未交付：响应恒为 `status="unavailable"`、`imports=[]`、`dependents=[]`，warnings 说明"静态导入关系尚未接入解析器"。不伪装成成功空结果。

C 交付并核查后将按任务书 §6.5 实现：imports 保留 C 原始字段并附 `resolution{status: resolved|unresolved|ambiguous, targetPath, candidates}`；相对导入按"搜索根 + 包层级"解析，`1 ≤ level ≤ 包深度 d`，越出顶层包/无包语境/无候选 → `unresolved`，多候选 → `ambiguous`；`dependents` 仅统计 resolved 且目标为当前文件的记录；部分解析覆盖时界面注明"已解析范围内未发现"。

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
