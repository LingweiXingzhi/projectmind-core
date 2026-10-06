# D：独立仓库样例与验收

ROLE = D；STATUS = READY（工具交付）。产品验收 = NOT_RUN。任务依据：2026-10-05 的 `PROJECTMIND_REPO_EXPLORER_4_PERSON_PLAN.md` 共同约定与 D1–D3。

仅新增 `tests/repo_explorer_acceptance/**` 与本文。不改产品，不修改/推送/合并 main，不自动推送或建 PR。本轮新任务书的范围优先于旧规范中的历史任务和默认远端流程。

## 固定基线与实际工作区

- BASE_COMMIT = `1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d`
- BASE_BRANCH = `integration/bcd-audit-fixes-v1`
- ACTUAL_CHECKOUT = `/workspace/scratch/a24b13c320a5/repo-explorer-d`
- BRANCH = `feat/repo-explorer-acceptance-v1`
- 首个 D1 commit = `f0ef05200420e1fac4f4465b32a2bac203c64d29`
- 最终本地提交用 `git rev-parse HEAD` 获取，交付包附完整 SHA 和有序提交清单。

任务书中的 Windows checkout `G:\jiagou\projectmind-bcd-audit-fixes` 不在当前 Linux 执行环境，不能声称核查了那个现场。这里建立独立 Git checkout：经已授权 GitHub 只读接口读取基线，114 个 blob 与全部 tree 逐一按 Git SHA 校验，精确还原 BASE_COMMIT（包括父引用与提交元数据），没有替换成快照自造 SHA。本地历史在基线处为 shallow boundary，基线父历史未下载。交付 delta bundle 以该完整基线为 prerequisite，供 A 的真实仓库取入；不要求 A 使用这里的路径或浅历史。

该 checkout 起点干净；原 `/workspace/scratch/a24b13c320a5/projectmind-core` 与所有远端来源分支不修改。当前没有 A 本轮的确切集成路径、完整 HEAD、启动命令；共同基线和旧 PR 不能替代最终验收目标。

## 1. 一条命令重建独立样例

在含本工具的 checkout 根目录：

```bash
python3 tests/repo_explorer_acceptance/fixture.py
```

Windows 可将 `python3` 换成实际 Python 命令。生成器在系统临时目录独立创建两个 Git 仓库，不使用正式仓库的 worktree。输出两次提交和第二仓库的真实完整 SHA、仓库路径、受版本控制清单与实际 Git rename 检测结果；同样保存到输出的 `manifest.json`。固定内容、提交身份/日期，但仍实际调用 Git 取得 SHA；每次路径不同，提交相同。

样例不含地图 JSON；有 Python package、普通/异步/嵌套定义、中文、空文件、绝对和相对导入、别名、缺失与歧义目标；另有语法错误、非 Python 文本、二进制、非法编码、超 1 MiB 文件、symlink 和 gitlink。后两者直接写真实 Git mode，不依赖 Windows symlink 权限，不跟随目标。第二提交新增/修改/删除/移动；之后加入未跟踪文件和未提交文本。第二仓库故意同名但内容、SHA 和 `.git` 完全独立，用于检测缓存串仓库。

只生成源码，不 import 或执行它。`DO_NOT_EXECUTE.py` 是执行哨兵；目录外 canary 不能通过 symlink 读取。所有内容在独立样例下，不向正式 Worklog/Continuity 数据库写测试数据。生成器不安装依赖，也不 clone 外部项目。

本轮实测（SHA 是 Git 输出，不是预填）：

```text
FIXTURE_ROOT = /tmp/projectmind-d-fixture-849jr9ny
BASE = cbb97e25faa459c32e17e567a899d4761d3d0102
TARGET = fbbe597de0788e735b985c9627f4fed0127abd22
SECOND = 6cec9af7b433970eaa47eede3b7588507f5840d9
A pkg/new.py
D pkg/old.py
R pkg/moved.py -> pkg/relocated.py
M pkg/service.py
```

只能清理某次生成的根目录：

```bash
python3 tests/repo_explorer_acceptance/fixture.py --cleanup /tmp/projectmind-d-fixture-XXXX/manifest.json
```

清理验证独立生成标记、保存的完整 manifest 和根目录名称，拒绝任意路径/修改过的 manifest。`--parent` 仅用于指定现有临时父目录，并拒绝位于任何现有 Git checkout 内。不要以正式仓库作为样例。

## 2. 无 A 服务时的接口交付

```bash
python3 tests/repo_explorer_acceptance/acceptance.py \
  --fixture /tmp/projectmind-d-fixture-XXXX/manifest.json \
  --report /tmp/projectmind-d-initial.json
```

不指定服务，不发送 HTTP。D01–D08 与解析器未接入分支均输出 NOT_RUN，六项 UI 也为 NOT_RUN。退出码 2 表示验收未完整执行，不能当绿灯。

> 本仓库**不携带** D 早期那份 `reports/initial-not-run.json`（它是当时的 Linux 路径与旧 SHA 绑定，属于历史 D 交付记录，不随本次集成）。本节记录的是该 runner 的用法，不是当前集成状态；当前集成状态的 SHA 绑定报告见下面的 §3。

运行本 runner 时所有文本读写都是显式 UTF-8（`-X utf8=0` / cp936 下同样可读可写），因此报告在非 UTF-8 默认编码的 Windows 上也可以直接用 UTF-8 读取。

## 3. 收到 A 完整交付后的实际接口验收

先阅读 A 在目标 checkout 的 `docs/repo-explorer/INTERFACES_V1.md` 和启动说明，核对本计划 schemaVersion=1。必要接口差异应明确记录并经交付说明确认，不改产品来追测试、不静默换协议。

A 应给：实际 checkout、完整 HEAD、干净状态、包含 B/C 的集成情况与启动命令。仅在那个干净固定版本启动隔离实例；使用自己的独立端口，比如 8876，避免其他服务冲突。下列启动形式需 A 确认它的实现支持后才运行：

```bash
python3 app.py --repo /tmp/projectmind-d-fixture-XXXX/first/sample --port 8876
```

**不传地图 JSON**。不要用正式仓库作为目标项目；服务读取/记录均围绕独立样例。脚本不启动服务、不检出、不修改源码，只请求公共 HTTP 入口与读取样例 Git 内容。

```bash
python3 tests/repo_explorer_acceptance/acceptance.py \
  --fixture /tmp/projectmind-d-fixture-XXXX/manifest.json \
  --base-url http://127.0.0.1:8876 \
  --target-checkout /absolute/path/to/A-checkout \
  --target-head FULL_A_COMMIT_SHA \
  --launch-command 'python3 app.py --repo /tmp/projectmind-d-fixture-XXXX/first/sample --port 8876' \
  --report /tmp/projectmind-d-live.json
```

Windows 可将命令写成一行，替换实际路径和 Python 命令；不要照搬占位 SHA。脚本验证该 checkout 确为所给完整 SHA 且干净，并在结束时再次检查。服务身份不能仅凭 HTTP 回包证明；操作者应确认记录的命令确实启动了该实例，没有连接旧端口。报告保留 HEAD、路径、服务地址、命令、逐组状态、请求/响应和失败复现入口。高风险失败优先为身份、版本、读取边界、串项目与旧索引；其余失败标 MEDIUM，供 A 按实际影响复核。

| ID | 核查内容 / 独立预期 |
| --- | --- |
| D01 | 无地图打开；open 的 SHA 等于实际 Git；schema 与覆盖字段类型正确 |
| D02 | 目录和 tracked 文件精确匹配 Git；读取提交原文而非脏工作区；中文/空文件/分段/500 行上限；未跟踪路径拒绝 |
| D03 | 手工固定的函数/class/method/async/嵌套身份、docstring、起止行；parser 必须为 python_ast_v1，legacy 的 null 结束行失败 |
| D04 | 手工固定的 import 顺序、别名、相对层级；pkg/utils 和 src 布局明确定位；缺失 unresolved；dual.py 与 dual/__init__.py 歧义不任择；反向只收 resolved |
| D05 | HEAD 新版本、增加函数、删除文件不可读；A/M/D/R 对齐实际 git diff -M；旧/新移动文件按各自版本读取；反向关系刷新 |
| D06 | 同名第二仓库独立 ID、原文、符号和关系；切回第一仓库不残留 |
| D07 | 绝对/越界/反斜杠/特殊 Git 语法路径、非法行号、无效及外项目 SHA、未知 ID 受控 4xx；原地图 evidence 不允许未授权路径 |
| D08 | 二进制/编码/超限/symlink/gitlink 受控拒绝；语法错误 parse_error 和非 Python unsupported 带原因；限额 partial/skipped 可见；哨兵未执行、没有日志数据库写入 |
| D08-PARSER | A 提供解析器未接入实例时，symbols/relations 显示 unavailable 和原因；没有该实例就 NOT_RUN |

正常完整解析实例不能证明缺失解析器时的分支；可用 `--degraded-base-url http://127.0.0.1:8877` 指向 A 明确提供的同一目标版本的降级实例。工具不卸载解析器，不改 B/C 文件。未提供则该项保留 NOT_RUN，不声称覆盖完成。

接口边界：trackedFileCount 按已接受契约（r02 Q5、`INTERFACES_V1.md` §1、Codex r08 确认）只统计普通 blob（100644/100755、文件名可 UTF-8 解码）——symlink 与 gitlink 保留树入口但不计数，因此本夹具（19 普通文件 + 1 symlink + 1 gitlink）必须为 **19**；接受 20/21 是 runner 侧的 R35-T1 缺陷，已在本轮修正。尾部行窗口若只省略前面的行，仅核查 truncated 为布尔值，不猜其含义；其余正常完整读取必须 false、后面还有未返行必须 true。

## 4. 界面实测与结果登记

必须在 A 的确切 HEAD 实际操作：展开目录 → 打开文件 → 点击函数看源码 → 从静态导入跳转 → 比较提交 → 切换第二仓库。每步保留实际操作、预期与实际、对应版本/行号及截图或浏览器记录。额外检查切换后异步旧结果没有盖住当前项目。

接口通过不代表 UI 通过。本次未获得 A 最终实例，因此六步均 NOT_RUN。可在真实操作后将人工观察记录为 JSON，用 `--ui-evidence <实际记录.json>` 加入报告；字段为 targetHead、baseUrl、observer、observedAt、steps。steps 必须按上面六个中文名称排序，每项含 step、status（PASS/FAIL/NOT_RUN）、detail（操作和实际结果）、evidence（实际截图/操作记录引用）。不得凭界面代码或 HTTP 结果填写 PASS。脚本检查身份与字段，但不能独立认证人工观察，将明确标为 participant_observation_not_independently_verified。

退出码：0 = 本轮所有 HTTP 项和实际 UI 记录均 PASS；1 = 任一 FAIL；2 = 有 NOT_RUN。没有 UI 或缺失解析器分支未验证时仍是 2，产品不宣称通过。READY 只表示 D 工具可交付。

## 5. 已运行与未运行

```bash
python3 -m unittest discover -s tests/repo_explorer_acceptance -p test_tools.py -v
python3 -m py_compile tests/repo_explorer_acceptance/fixture.py tests/repo_explorer_acceptance/acceptance.py tests/repo_explorer_acceptance/test_tools.py
git diff --check
```

12 项工具自检实际通过：真实 Git 提交/变化/重建/独立存储、固定行号、清理保护，以及 legacy/空结束行/错 SHA/伪符号/伪确定依赖/错 coverage/HTTP 500/错误 schema 的拒绝逻辑。HTTP 自检仅用自建标准库 responder 验证 urllib 和判定器，**不是 A 产品验收**。没有导入 B/C 私有函数，没有运行历史产品全套来冒充本轮结果。日志见 `reports/tool-selfcheck.txt`。

CHECKS_NOT_RUN：A 产品 HTTP、全部 UI、解析器缺失实例、Windows 现场；理由是未收到 A 本轮确切集成交付，本机为 Linux。产品不判 PASS。

Project Model Impact = NONE：新增测试工具与证据，无产品职责/正式地图变化。

## A 如何接入

在拥有固定基线的真实 A 仓库，按完整 SHA 应用两个 D 提交；或先 `git bundle verify <交付 bundle>`，再 `git fetch <交付 bundle> feat/repo-explorer-acceptance-v1:refs/remotes/d/repo-explorer-acceptance-v1`，然后按顺序 cherry-pick。bundle 只包含 D 交付差异且要求 BASE_COMMIT 已存在，不包含浅基线替代品。集成由 A 完成，不操作 main。

当前 D 可先交付；收到 A 集成报告后，D3 才开始。若发现失败，只报具体请求、结果与复现，交给 A 修；修复后仅复验失败项和受影响项。
