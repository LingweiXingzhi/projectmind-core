# ProjectMind 架构认知闭环 · 本轮最终报告（RUN ZCODE-CLOSE-20261007-1757-K7）

完成时间：2026-10-07（+08:00）；最终审查收口：2026-10-08 00:27（+08:00）。执行入口：`C:/Users/李则兴/Documents/Codex/2026-10-07/ni-x/outputs/ZCode_下一步集成闭环_无人值守完整指令_2026-10-07.txt`

> **本轮最终状态：`STOPPED_REQUIRES_DECISION`** — 自动审查循环按用户规则在 BATCH-4 终止；BATCH-4 返回 2 条 P1（1 条产品凭据过滤回归 + 1 条无人值守控制器运行崩溃），**未修复**，等待人工决定。当前版本本身可保存、可继续开发（工作区干净、远端同步、测试与验收记录完整）。分类明细见文末"最终状态与分类"节。

## Result

**用户现在能做什么（全部真实后端、真实 HTTP、浏览器实测）**

1. 「分析已有项目」或「规划新项目」两种入口；已有项目绑定固定提交的代码事实，规划项目允许没有代码 SHA。
2. 生成候选：真实 AI（未配置时如实 NOT_RUN）或 **C 规则引擎候选**（标注 `rule_based` 与读取覆盖）；候选可应用为草稿、可放弃。
3. 直接编辑草稿（职责/接口/关系/过程步骤与分支/允许失败路径，CAS 修订），刷新重开保留。
4. 自然语言纠正：规则路径由 C 引擎产生局部操作与前后差异；真实 AI 路径未配置模型时明确拒绝（NOT_RUN），预览绑定基准修订、草稿变化即作废。
5. **人审与正式版本**：草稿保存到 B 的真实版本服务 → 人审预览（真实会话、覆盖范围、限制、预览摘要）→ 确认接受/拒绝 → 发布产生**不可变认知版本**（架构 Git 提交 + 核查代码 SHA）。
6. 版本历史/单版本读取；同版交接包导出与第二副本导入（按 Git 字节核对 + 内容指纹比对）。
7. 代码变化复核（定位受影响节点）→ C 增量候选 → 创建**持久化修正任务**（带验收条件、目标代码 SHA、接手信息）→ 实施提交回挂 → 人确认核查结论后关闭。
8. 规划图确认产生 `confirmed_design` 版本（代码字段为 null），关联真实代码保留设计历史、不声称已实现。

**用户现在还不能做什么（诚实边界）**

1. **真实模型未验证**：本机没有 `OPENAI_API_KEY` / `PROJECTMIND_AI_MODEL`，AI 初图与 AI 自然语言纠正为 `NOT_RUN_AWAITING_CONFIGURATION`（代码路径与 UI 均已就位，配置后原样运行）。样例/规则候选不能冒充 AI 结果。
2. **D 的独立交付已在远端出现，但未接入**：`PR #54`（head `c8b942a8`，Draft、OPEN，base 为上一轮 v1 集成分支）含 D 的同版交接 / FixTask 回挂 / T01–T28 收集器与证据，其自述产品状态为 `INCOMPLETE_WITH_CONFIRMED_FAILURES`，并列有对 A 的 7 条修复清单（同源 clone 身份、A 新增写接口的 session/CSRF、adapter.registered 等）。本轮（BATCH-2/BATCH-3）**没有**合并它，也未按其清单改动主线：登记为后续独立集成事件。当前主线的同版交接、修正任务与 28 项验收仍是 A 侧兼容实现，不是 D 的独立验收。
3. **跨设备**：第二副本用两份独立 clone 实测（含 Git 版本读取与内容指纹），不是真实跨设备验收。
4. **正式架构内容仍由人确认**：本轮只产生候选/测试仓库的版本；ProjectMind 自身正式图保留给负责人在界面批准。


## 附：审查历史与当前状态（BATCH-4 为本轮最后一次自动审查）

- BATCH-2 目标 `a973d77`：attempt-001 真实额度耗尽 → attempt-002（22:11:56 发起，22:27:14 完成）**`CHANGES_REQUESTED`，9 条（1×P1 + 8×P2）**；判定与逐条证据 `receipts/BATCH-2/attempt-002/verdict.json`。
- BATCH-2 整批修复：提交 `c62b5c08`（父 `a973d77`，未改写任何已审查历史）。9 条要点：分支占位不遮蔽 B 编辑、显式畸形 coverage 一律拒绝、带引号字典键凭据过滤、纠正按当前绑定重建受控包、C 增量转 CONTRACT_V1 可应用操作、`verified` 需列明证据 + 仓库中真实存在的提交、T01/T21/T24 判据可测化；控制器侧 G-02 锁回收不覆盖新锁、G-03 队列写入互斥。回归 `tests/test_archloop_a_batch2_fixes.py`（20 例）。
- BATCH-3 目标 `c62b5c0`：attempt-001（23:18:49 发起，23:34:55 完成）**`CHANGES_REQUESTED`，6 条（全 P2）**：`receipts/BATCH-3/attempt-001/verdict.json`。
- BATCH-3 整批修复：提交 `803c6736`（父 `c62b5c0`）。6 条要点：
  - A-01 **旧格式载体**下填充值未知时一律以 B 当前值为准（不再回填旧占位）；
  - A-05 显式 `coverage: null` 视为畸形声明并拒绝（只有**省略**该键才用默认覆盖；service 只在调用方给出该键时转发）；
  - GEN-01 凭据判定改为**键名组件**规则（snake/kebab/camelCase 拆分后末组件为凭据词，或含 secret/password/credential 类词），`{"monkey": …}`、`service_name`、`token_cache` 不再被误排；
  - C-INCREMENTAL-01 同一节点多次变更**合并为一条** update；仍被关系引用的节点不产生删除（转 warning）；派生 ID 冲突唯一化；所有产出操作在累积图上**逐条验证**（新增 → 更新 → 删除），不可用者降级为 warning；
  - G-02 控制器加**租约围栏**：`lease_held` 校验 + `LeaseWatchdog` 在租约易主时**杀死正在执行的审计子进程**（`LEASE_LOST`，保持可重试），`release_lock` 只释放仍属于自己的锁；
  - ACCEPTANCE-01 T21 要求 `contentMatches=false` **且** `revisionMatches=true` **且** `mapIdMatches=true`；T24 要求绑定工作区版本是**真实存在的完整 SHA**，且 coverage 的 `trackedFiles`/`pythonFiles` **等于本仓库该提交的真实文件树计数**（运行器本地 git 计算）。
  - 回归 `tests/test_archloop_a_batch3_fixes.py`（13 例）+ 控制器自检新增 `lease_fencing_cases`（3 例，含"被顶替持有者被杀死"）。
- BATCH-4 目标 `803c6736`：**本轮最后一次自动审查**，00:01:15 发起。按用户 2026-10-08 00:0x 的规则：BATCH-4 返回后**只读判定、分类、更新报告、停止**；不再修 finding、不创建 commit、不创建 BATCH-5、不再次调用审查模型。
- 推送：`c62b5c0` 曾连续 6 次被 GitHub 服务端 HTTP 500 拒绝（探针分支同样失败、dry-run 正常），第 7 次成功；`803c6736` 首次即成功。`origin` 现为 `803c6736d1ab01bee004a77c2d2b3b140b28cb12`（`git ls-remote` 核实）。
- 本轮 `accepted_sha` 仍为 null：**没有取得 PASS 的批次**；最终结论由 BATCH-4 的分类结果给出（见文末"最终状态"节）。

## 验证矩阵（实际执行，逐项可查）

| 通道 | 结果 | 证据位置 |
|---|---|---|
| 真实 Codex 握手 | HANDSHAKE_PASS（随机值/提交/README 对象/文件读取全部一致，7 个真实工具事件） | `receipts/HANDSHAKE_RECEIPT.json`、`logs/handshake_codex_stdout.jsonl` |
| Codex 审查（真实调用） | BATCH-1 CHANGES_REQUESTED(13) → 修复；BATCH-1B CHANGES_REQUESTED(9) → 修复；BATCH-1C CHANGES_REQUESTED(8) → 修复；BATCH-2 CHANGES_REQUESTED(9) → 修复；BATCH-3 CHANGES_REQUESTED(6) → 修复；BATCH-4（本轮最后一次自动审查）见下节 | `packages/`、`receipts/*/attempt-*/` |
| A 专项测试 | 144 项通过（1 跳过：规则候选无过程步骤；111 原有 + 20 条 BATCH-2 回归 + 13 条 BATCH-3 回归） | `test-results/archloop-a-batch3repair.log` |
| 全量回归（UTF-8） | 800 项，3 项已知环境错误（`*` 文件名 1 项 + 符号链接权限 2 项，与起点基线**逐条相同**），1 跳过 | `test-results/full-suite-batch3repair.log` |
| A 侧 28 项主线验收（真实 HTTP，最终修复后实跑） | 35 PASS / 2 NOT_RUN（T01/T23 真实 AI 未配置）；T21 由完整内容比对支撑（contentMatches=false 且 revision/mapId 匹配）、T24 与本仓库真实文件树一致（trackedFiles=248、pythonFiles=139） | `test-results/acceptance-a-side-batch3repair.json/.md` |
| 真实浏览器观察（参与者观察） | 已有项目故事：规则候选→应用→同步→人审预览→确认→发布（`confirmed_cognition`，真实 Git 来源与核查 SHA）；规划故事：设计候选→同步→设计确认→发布（`confirmed_design`，代码字段 null） | `snapshots/ui_workbench_published_version.png`、`ui_workbench_review_flow.png`、`ui_planning_confirmed_design.png` |
| 旧本地草稿导入 | 上一轮 `dev_sample` 草稿导入本轮独立数据根，标记保留，源数据根字节未变 | `test-results/legacy_import_result.json` |
| 无人值守机制 | 控制器自检 ok=true（21 判定 + 12 归属 + **2 条锁回收竞态 + 2 条队列并发**）；Windows 计划任务 `PM-Arch-Close-ZCODE-CLOSE-20261007-1757-K7` 每 30 分钟、真实触发 LastTaskResult=0 | `state/controller_selfcheck.json`、`logs/scheduler.log` |

## 实际接入的队友提交与复用范围

| 角色 | 来源 | 固定提交 | 本轮接入 |
|---|---|---|---|
| B | PR #51 | `bba8e84`（运行时 `b58fee7`） | 全量接入：`archloop/backend_b.py` 单适配层驱动 `WorkspaceService`/`HumanReviewGateway`；草稿/人审/发布/版本/第二副本导入全部真实调用 |
| C | PR #53 | `55ea6466` | 接入（A 适配）：`archloop/backend_c.py` 调用其 bootstrap/纠正/偏差/增量函数，投影为 CONTRACT_V1，标 `rule_based`，只读 |
| D | PR #54（Draft、OPEN，head `c8b942a8`） | `c8b942a8d724b1bd0509f61b2db6ec642a117181` | **未接入**（登记为后续独立集成事件）：其自述产品 INCOMPLETE 并列有对 A 的 7 条清单；主线仍用 A 侧 `fix_tasks.py`、交接导出/导入与 28 项验收作为兼容 seam |

## Files Changed（本批 c62b5c0，BATCH-2 修复）

- 修复：`archloop/backend_b.py`（A-01 分支占位值、A-05 coverage 拒绝）、`archloop/context_pack.py`（GEN-01 凭据模式）、`archloop/service.py` + `archloop/correction.py`（CORRECTION-01 受控包与缓存刷新）、`archloop/backend_c.py`（C-INCREMENTAL-01 转换）、`archloop/fix_tasks.py`（FIX-01 证据与提交存在性）、`archloop/acceptance.py`（ACCEPTANCE-01 判据谓词与 T21/T24 流程）
- 新增测试：`tests/test_archloop_a_batch2_fixes.py`（20 例）；`tests/test_archloop_a_stage23.py` 的 verified 载荷改为列明证据
- 控制目录：`controller.py`（G-02 锁回收、G-03 队列互斥、4 条新自检用例）、`packages/BATCH-3/`、`state/`、`test-results/`、`logs/push-retry-batch2repair.log`、`team-deliveries/`

## Files Changed（累计 b75ad82 → c62b5c0）

- 新增：`archloop/backend_b.py`、`context_pack.py`、`correction.py`、`backend_c.py`、`fix_tasks.py`、`legacy_import.py`、`acceptance.py`；`tests/test_archloop_a_backend_b.py`、`test_archloop_a_batch1_fixes.py`、`test_archloop_a_stage23.py`
- 扩展：`archloop/service.py`（绑定/同步/人审三步/版本/导入/交接/任务/偏差/增量/上下文包/规则路由）、`archloop/contract.py`（B 错误码与标识符规则）、`app.py`（archloop 路由与 CLI 配置）、`web/index.html` + `web/archworkbench.js`（真实版本服务与人审流）
- 控制目录：`controller.py`、`audit_schema.json`、`packages/BATCH-*`、`receipts/`、`test-results/`、`team-deliveries/`、`state/`

## Project Model Impact

**UPDATE（候选，待人批准）**：本轮新增职责（真实版本接入、受控上下文生成、规则/真实纠正、持久化修正任务、同版交接、无人值守控制器与验收工具）在 `extensions/map_proposal/PROJECTMIND_SELF_CANDIDATE.json` 与工作台内候选图中以证据形式存在；正式 ProjectModel 仍等负责人在界面批准，无人值守执行器未批准任何正式图。

## Risks-Follow-up

1. 真实 AI 未验证（见上）；配置后按 `team-deliveries/DEMO_PATH.md` 原样重跑 T01/T23。**BATCH-2 的 `unverified` 已原样保留在本节末尾**，不得改写成 PASS。
2. D 已有 Draft PR #54 但未接入：`fix_tasks`/`handover` 仍是 A 侧兼容实现；D 接入时应按 `TEAM_DELIVERIES.md` 流程登记、逐条处理其 7 条 A 侧清单，并重跑 T18–T28 与真实浏览器故事。**PR #54 不得因本轮修复而自动合并。**
3. UI PR #56（`2ef0179`，Draft/OPEN，base 为上一轮 v1 集成分支）与本轮真实后端 UI 在 `web/archworkbench.js`、`web/index.html` 上重叠：需先做页面结构决策（保留 A 的同步/人审/发布/版本/交接/任务处理函数），合并后**必须重跑两个浏览器故事**并冻结新提交再审。**本轮未合并，也不影响后端主线结论。**
4. 跨设备验收未做（第二副本已实测）。
5. 已知环境失败 3 项（`*` 文件名、符号链接权限）与本轮无关，起点对照一致，最终审查中按现状披露。
6. 无人值守恢复能力：调度器能重试审查与依赖检查，**不能**自动恢复已退出的 ZCode 开发会话；本轮保存了完整可接续状态（`state/dev_state.json`）。
7. 上一轮事故（误停他人进程）在本轮以严格归属核验替代：每次停止前核对 run_id/pid/创建时间/目录/端口，缺一即拒；本轮只停止了核实属于本轮的 8801 服务进程。
8. **外部阻塞已解除**：`c62b5c0` 的推送在第 7 次重试（23:16:48）成功，远端分支已在 `c62b5c0`（`git ls-remote` 核实）。

### BATCH-2 审查回复中的 `unverified`（原样保留，未改写）

1. 指定测试未完整通过运行：临时目录初始化受限，出现 `No usable temporary directory found`；未独立重跑提供方的 111 项及全量 767 项测试。
2. 未调用真实 AI；生成凭据过滤及纠正载荷检查使用合成输入和模拟传输。
3. 未独立启动真实 HTTP 服务或操作浏览器；三张截图属于提供方记录。
4. 未执行新发布、创建实体第二副本或跨设备验收；已独立读取现有真实 Git 版本并完成内存服务导入。同 origin 跨目录身份仅作纯函数核验。
5. 未核验发布事务极端中断、实际操作系统并发及真实进程停止；控制器竞态与归属检查使用内存或模拟系统接口。
6. `Get-ScheduledTask` 查询退出码 1（PermissionDenied），未确认半小时任务的实际注册与触发配置。
7. 实时 `controller.py` 路径读取返回 `FileNotFoundError`，未比较其与包内冻结副本。
8. D 的独立验收未提供，本轮未核验 D 模块或 GitHub issue #52 的当前交付状态。

（以上为 BATCH-2 判定所附的未验证项；BATCH-3 与 BATCH-4 的 `unverified` 原文分别见 `receipts/BATCH-3/attempt-001/verdict.json` 与 `receipts/BATCH-4/attempt-001/verdict.json`，各批次原话都保留，不得折叠成“全部已验证”。）

## 最终状态与分类（BATCH-4 之后，按用户规则只分类不修复）

### 字段

| 字段 | 值 |
|---|---|
| `BATCH_4_VERDICT` | `CHANGES_REQUESTED`（6 条：2×P1 + 4×P2）。**离线恢复**：审计子进程正常完成并写下 `reply.md`，但控制器后处理在本机崩溃（见 G-02-RUNTIME），`result.json`/`verdict.json` 由控制目录内脚本用控制器自带 `parse_verdict` 从已记录回复恢复（**未再调用模型**）；退出码未落盘，按 `turn.completed` + 完整结构化回复推断为 0，推断过程写入 `receipts/BATCH-4/attempt-001/result.json` 的 `exit_code_source` |
| `CURRENT_HEAD` | `803c6736d1ab01bee004a77c2d2b3b140b28cb12` |
| `REMOTE_HEAD` | `803c6736d1ab01bee004a77c2d2b3b140b28cb12`（`git ls-remote` 核实） |
| `WORKTREE_CLEAN` | `YES`（`git status --porcelain` 空） |
| `A_SPECIAL_RESULT` | 144 OK（1 skipped）`test-results/archloop-a-batch3repair.log` |
| `FULL_SUITE_RESULT` | 800 ran / 3 errors（与基线逐条相同的环境错误）/ 1 skipped `test-results/full-suite-batch3repair.log` |
| `ACCEPTANCE_RESULT` | 35 PASS / 2 NOT_RUN `test-results/acceptance-a-side-batch3repair.json` |
| `CONTROLLER_SELFCHECK` | `ok=true`（21 判定 + 12 归属 + 2 锁回收 + 3 围栏 + 2 队列并发）。**注意**：自检未覆盖 `run_codex_audit` 的后处理路径，因此它通过并不反驳 G-02-RUNTIME |
| `BLOCKER_COUNT` | 2（均为 P1；无 P0） |
| `P1_COUNT` | 2 |
| `P2_COUNT` | 4 |
| `P3_COUNT` | 0 |
| `OUT_OF_SCOPE_COUNT` | 本轮新增 0（既有范围外项见下） |
| `NOT_RUN` | T01/T23（真实 AI 未配置）；真实浏览器证据为参与者观察；跨设备未做 |
| `KNOWN_ENVIRONMENT_FAILURES` | 3（`*` 文件名 1 + 符号链接权限 2，起点对照一致） |
| `PR_56_STATUS` | OPEN / Draft（`2ef0179`，纯前端重设计，base 为上一轮 v1 集成分支）；**未合并** |
| `D_DELIVERY_STATUS` | PR #54 OPEN / Draft（`c8b942a8`）；**未接入**，登记为后续独立集成事件 |
| `AI_REAL_PATH_STATUS` | `NOT_RUN_AWAITING_CONFIGURATION`（无 `OPENAI_API_KEY` / `PROJECTMIND_AI_MODEL`；不得用规则结果冒充） |

### MUST_FIX_BEFORE_NEXT_PHASE

1. **GEN-01（P1，产品代码，回归）**：`archloop/context_pack.py` 的键名组件规则漏掉"缩写 camelCase"（`clientAPIKey`、`APIKey` 这类：拆分后末组件为 `apikey` 而非 `key`）。本机独立复核：`_key_name_is_secret("clientAPIKey") → False`，含合成凭据的配置文本不被判定为凭据 → **凭据会进入上下文包**，在配置真实模型后随生成/纠正请求外发。c62b5c0 的旧实现能检出，属于 BATCH-3 修复引入的回归。修复方向：组件判定时把 `apikey/accesstoken/clientsecret/apisecret` 等连写形式纳入凭据词表（或先按大小写边界拆到字母级再判定末词）。
2. **G-02-RUNTIME（P1，无人值守控制器，回归）**：`controller.py` 后处理必然崩溃——`returncode = proc_returncode` 位于 schema 回退分支内部（约 828 行），正常路径在 840 行 `"exit_code": returncode` 抛 `UnboundLocalError`（本轮 BATCH-4 的判定落盘就是这么丢的）；同一 `LeaseWatchdog` 被 `with` 进入两次（正常路径 18 行、回退路径 47 行），回退时抛 `threads can only be started once`。影响：控制器无法记录任何判定、无法重试、无法作为无人值守机制使用。**注意**：BATCH-4 的判定内容本身未受影响（子进程与回复完整）；本报告已按离线恢复记录，未再调用模型。

### SAFE_TO_BACKLOG

- **G-02-STOP（P2）**：看门狗已标记失租时，快速结束的子进程仍被报告为正常完成 → 极端竞态下可能重复记录一次判定；不触及产品数据/版本。
- **G-02-RETRY（P2）**：调用前围栏失败时包留在 `RUNNING`（应恢复可重试），后续 `newest_pending` 不再选中 → 审计停滞（本轮实际发生：BATCH-4 曾卡在 RUNNING）。
- **G-02-RELEASE（P2）**：`release_lock` 的"读租约—unlink"非原子，理论上可删掉第三方新锁；`mutate_queue` 未传 lease。
- **ACCEPTANCE-01（P2）**：T24 把**响应自带**的版本当作本地 HEAD 自我比较（`acceptance.py:542`），缺少独立的 `git rev-parse HEAD` 读取 → 旧提交理论上可被当作当前版本判 PASS。本轮记录本身仍然真实：验收运行时 HEAD 就是 `c62b5c0`，记录也是 `c62b5c0`，树计数 248/139 与当时真实树一致；此项是判据强度问题，不是已记录的 PASS 失真。
- 建议：上述 3 条 G-02-* 与 G-02-RUNTIME 属同一函数族，宜同批修复并加自检用例（含"正常路径退出码落盘"与"看门狗只进入一次"两条用例）。

### OUT_OF_SCOPE

- **PR #56**（UI 重设计）：页面结构决策（保留 A 的真实后端接入处理函数），合并后须重跑两个浏览器故事并重新冻结审查。
- **D PR #54**：按 `TEAM_DELIVERIES.md` 流程登记、逐条处理其 7 条 A 侧清单、重跑 T18–T28。
- **真实 AI 路径**：配置 `OPENAI_API_KEY`/`PROJECTMIND_AI_MODEL` 后重跑 T01/T23 与界面"真实 AI 生成/纠正"。
- **跨设备验收**、发布事务极端中断测试。
- 注意：GEN-01 的凭据过滤属**本轮已宣称的能力**（受控上下文包/凭据不外发），因此它**不属于**范围外，已列入 MUST_FIX。

### 是否足以作为下一阶段开发基线

是——但须带两个已知 P1：（1）产品侧凭据过滤对"缩写 camelCase"漏检（真实模型未配置时不会实际外发，配置前必须修）；（2）控制器后处理崩溃使其暂时不能作为无人值守审查机制使用（不影响产品本身）。产品主线的可运行性、可追踪性与测试/验收记录完整：HEAD 与远端一致、工作区干净、800 项回归与基线一致、35 PASS/2 NOT_RUN 验收与浏览器故事齐备。

### 本轮自动化边界

`AUTO_REVIEW_LOOP_STOPPED = YES`　`BATCH_5_CREATED = NO`　（BATCH-4 为本轮最后一次自动审查；其 findings 只做分类与汇报，未修改任何产品代码，未创建新提交；队列无 PENDING/RUNNING 包，计划任务 `PM-Arch-Close-ZCODE-CLOSE-20261007-1757-K7` 已按收尾规则**停用（保留历史）**。）

## 附：入口、调度与进程

- 唯一启动入口与最短演示：`team-deliveries/DEMO_PATH.md`
- 共享接口本轮补充：`team-deliveries/CONTRACT_V1_ROUND2_ADDENDUM.md`
- 队友交付登记：`team-deliveries/TEAM_DELIVERIES.md`
- 本轮调度：Windows 计划任务 `PM-Arch-Close-ZCODE-CLOSE-20261007-1757-K7` —— **已停用（未删除，历史保留）**，最后运行 2026-10-08 00:03:01（LastTaskResult=0）。队列中已无 PENDING 包，停用后不会再发起任何自动审查。
- 本轮进程：`127.0.0.1:8801` 工作台实例（pid `23044`，运行 BATCH-3 修复后的代码，已登记，`stop_decision=VERIFIED_OWNED`），**保持运行**以便负责人查看/演示；停止只用 `python controller.py proc-stop --name dev-server-8801`。
- 不动的现场：上一轮 8793（PID 27284）、旧 8765、原控制目录 `ZCODE-ARCH-20261007-130829-60B`、旧计划任务