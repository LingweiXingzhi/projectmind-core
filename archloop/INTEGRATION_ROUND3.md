# 本轮集成说明（A 集成人，2026-10-08）

本文件登记本轮 ABCD 集成实际接入的来源、能力接线、修复与验证边界。它是工程记录，
不批准正式架构内容；正式认知仍由人在界面确认。

## 来源（实际选用 SHA）

| 来源 | 选用 SHA | 接入方式 |
| --- | --- | --- |
| 起点（上一轮 A/B/C 集成 + 历轮修复） | `803c6736d1ab01bee004a77c2d2b3b140b28cb12` | 本轮分支起点，保留全部既有接线 |
| B（PR #51） | `58a9ee8a25cb9b240cd1baa5bb674c0c0e528e89` | 指令固定来源 `8315c2e6` 之后的两个自有提交（`aa3ef94` 候选选择预览/绑定审阅会话、`58a9ee8` 文档）经检查后一并接入；`extensions/architecture_workspace/**` 与 `tests/test_archloop_b_*.py` 整体导入 |
| C（PR #53） | `55ea6466583d98e0f466e5d4055922ef4aeecb12` | 已存在于起点；本轮在 C 模块内做必要缺陷修复（保留下方记录） |
| D（PR #54） | `c8b942a8d724b1bd0509f61b2db6ec642a117181` | `extensions/continuity/{fix_tasks,fix_gateway}.py`、`extensions/handoff/{architecture.py,archloop_backend.py}`、`tests/architecture_loop_acceptance/**`、`tests/test_archloop_d_*.py` 与 D 的交付证据整体导入 |
| 问题包（PR #58） | `5ebc6c16b6456cafc26a70b0bec3273bced0214c` | 只读参考：BATCH-4 findings（GEN-01、ACCEPTANCE-01、G-02-*） |
| UI（PR #56） | `2ef017917feb0308f2c477610630ab72d6b7a3e3` | 第二阶段界面基准：页面结构、导航、布局、颜色、画布与 Inspector |

## 能力接线（用户动作 → 公共入口 → 真实后端）

| 用户动作 | 公共入口（HTTP） | 真实调用 | 持久化/验证 |
| --- | --- | --- | --- |
| 建工作区（已有/规划） | `POST /api/archloop/workspaces` | A 身份 + B `code_identity`（origin URL 决定） | A 工作区记录；planning 无代码 SHA |
| 生成候选（规则） | `POST …/generate {mode: rule_based}` | C `generate_bootstrap_proposal`（经注册的 `correction` 适配器） | 候选只写草稿，需人应用 |
| 生成候选（真实 AI） | `POST …/generate {mode: production}` | 服务端模型配置；未配置 → `NOT_RUN_AWAITING_CONFIGURATION` | 不冒充 AI |
| 应用候选/直接编辑 | `…/apply-candidate`、`…/apply-ops` | A 草稿 CAS（`expectedDraftRevision`） | 草稿持久化；冲突返回 `REVISION_CONFLICT` |
| 自然语言纠正 | `…/correction-preview` → `…/apply-correction` | C `generate_nl_correction_patch`（规则路径）或真实模型 | 预览绑定基准草稿修订 |
| 保存到版本服务 | `…/sync` | B `WorkspaceService`（草稿差分操作） | B SQLite 草稿 + 修订号 |
| 人审预览/确认 | `…/review-preview` / `…/review-confirm` | B `HumanReviewGateway`（真实 peer/Host/Origin 会话） | 确认令牌只在服务端；覆盖范围与限制随预览返回 |
| 发布不可变版本 | `…/publish` | B `publish_reviewed_graph` | 架构 Git 提交（`mapSourceRevision`）+ 不可变 `mapRevision` |
| 版本历史 | `GET …/versions`、`…/versions/<rev>` | B 版本读取 | 历史不可变 |
| 偏差检查 | `POST …/deviations` | C `detect_process_deviations`（携带工作区身份） | 无证据/错仓/错版本 → `UNKNOWN`，不误报 `ALIGNED` |
| 增量候选 | `POST …/incremental` | C `generate_incremental_proposal` → CONTRACT_V1 操作 | 候选不自动写入 |
| 修正实现任务 | `POST …/fix-tasks` | D `FixTaskService`（注册的 `handoff` 权威后端） | D SQLite 任务（CAS + 生命周期）；actor 来自服务端会话 |
| 任务接手/回挂/核验 | `POST …/fix-tasks/<id>` | D `transition` / `submit` / `run_verification` + `confirm_verification` | 实测命令退出码与输出摘要才算核查凭据 |
| 同版交接导出/导入 | `GET …/handover`、`POST …/import-handover`、`…/open-from-version` | B 版本导出 + Git 内容核对 | 内容指纹比对；不一致以 Git 为准 |
| 第二副本打开同一版本 | `POST …/open-from-version` | B 版本读取 + 架构 Git 提交 | `contentMatches` 真实比对 |

适配器注册状态（`GET /api/archloop/backend`）反映真实调用：
`persistence: architecture_workspace_v1`（B）、`correction: extension:map_proposal`（C）、
`handoff: d_architecture_handoff_v1`（D）。

## 本轮修复（含来源与回归）

| 编号 | 内容 | 位置 | 回归 |
| --- | --- | --- | --- |
| GEN-01（BATCH-4 P1） | 凭据键名检测补充缩写驼峰边界（`clientAPIKey`/`APIKey`）与复合词（`APIKEY`）；普通配置（`monkey`/`APIEndpoint`）不误伤 | `archloop/context_pack.py` | `tests/test_archloop_a_batch4_fixes.py::GodKeyAcronymTests` |
| ACCEPTANCE-01（BATCH-4 P2） | T24 从被测 checkout 独立读取 `git rev-parse HEAD`，不再用响应版本自比 | `archloop/acceptance.py` | 同文件 `AcceptanceIndependentHeadTests` |
| D-A-02 | 公共写入口要求服务端会话 + CSRF 防伪头；缺失/不匹配以 `FORBIDDEN_SESSION`/`FORBIDDEN_CSRF` 拒绝；Cookie 为 HttpOnly | `archloop/web_session.py`、`app.py`、`web/archworkbench.js` | `WriteSessionRegistryTests`、`WriteSessionHTTPTests`、验收 T00 |
| D-A-03 | C 候选与 D 修正任务注册为真实适配器能力；A→D 适配层把简单请求转换为 D 的冻结包（服务端绑定 actor/scope/deviationId，版本包来自 B 导出） | `archloop/backend_c.py`、`archloop/backend_d.py`、`archloop/service.py`、`app.py` | `RegisteredBackendTests`、`AToDAdaptationTests`、验收 T18–T19 |
| D-BC-01 | 冻结 C→B 交换适配器 `to_b_proposal`（C→A 页图→B 严格图 + B 提案信封与内容摘要）；D 探针经它验证 B 真实接受 | `archloop/backend_c.py` | `FrozenCToBExchangeTests`；D `probe_candidates` findings=0 |
| D-C-01 | 偏差检测先核对轨迹身份（仓库/版本）与覆盖；错仓、错 SHA、无关轨迹、缺预期步骤 → `UNKNOWN`，不误报 `ALIGNED` | `extensions/map_proposal/candidates.py` | `CDeviationIdentityTests`；D 探针 |
| D-C-02 | `proposalId` 绑定候选语义内容（planning 与代码两类） | `extensions/map_proposal/candidates.py` | `CProposalIdentityTests`；D 探针 |
| D-C-03 | 自身候选图固定提交改为 `803c673…`（其列出的证据在该提交中都是真实 blob），目录引用改为入口模块文件 | `extensions/map_proposal/PROJECTMIND_SELF_CANDIDATE.json` | `SelfCandidateEvidenceTests`；D 探针 |
| 集成缺陷 | 既有项目人审覆盖纳入“步骤属于已覆盖节点”的期望过程（否则 D 修正任务无法绑定已覆盖过程） | `archloop/backend_b.py` | 验收 T10/T18 |
| 集成缺陷 | A→D 适配读取 A 页图 `process`、scope 使用 POSIX 相对路径、交接包显式给出架构/代码来源定位符 | `archloop/backend_d.py` | 验收 T18–T19 |
| UI 可用性 | 进程步骤编辑在 `input` 上即时提交（仅靠 `change` 会在不触发 blur 的宿主里丢文本）；`window.prompt` 全部替换为页面内声明字段并绑定会话操作者 | `web/archworkbench.js`、`web/index.html` | 浏览器故事（截图见运行目录 `snapshots/`） |

未处理（明确保留）：控制器 G-02-*（旧无人值守机制）不在本轮工程主线修复范围；
`state/controller_selfcheck.json` 属于上一轮运行目录，本轮不使用该调度器。
真实 AI（T01/T23）与物理跨设备仍 `NOT_RUN`，见验收报告。

## 验证入口

```sh
# 单元/集成测试（Windows 上有 3 项已知环境错误：符号链接权限 ×2、'*' 文件名 ×1）
python -m unittest discover -s tests -p "test_*.py"

# 真实 HTTP 主线验收（需要已启动的实例与已登记仓库）
python -m archloop.acceptance --base-url http://127.0.0.1:<port> --repo <验收仓库> --out <报告.json>

# D 的独立组件探针（在干净的检出副本上运行）
python -m tests.architecture_loop_acceptance.probe_candidates --source-checkout <clean-checkout> --output <dir>
python -m tests.architecture_loop_acceptance.probe_workbench --base-url <url> --fixture-code <clone1> --second-code <clone2> --output <file> --target-head <sha>
```

## Project Model Impact

UPDATE（候选）：本轮新增“受保护写会话”“D 权威修正任务”“冻结 C→B 交换适配器”
等职责有真实入口与证据；这些仍是有证据的图更新候选，等待人在界面批准，不自动写入正式模型。