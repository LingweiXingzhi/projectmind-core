# 阶段二界面迁移清单（PR #56 基准）

迁移时间：2026-10-08。阶段二分支 `integration/abcd-pr56-ui-ZCODE-ABCD-20261008-0115`，
从阶段一 checkpoint `85c18e7de7e056de52aae20e2daf4bb764df0d07` 创建。
依据：**以阶段一真实功能为行为依据，以 PR #56 为界面依据**
（PR #56 = `2ef017917feb0308f2c477610630ab72d6b7a3e3`，其 base 是旧 v1 `b75ad82`）。

## 1. 文件级迁移

| PR #56 文件 | 处理 |
| --- | --- |
| `web/index.html`、`web/styles.css`、`web/view.js`、`web/explorer.js`、`web/review.js` | 整体采用（新外壳：侧栏页面、全局搜索 ⌘K、状态栏、页面历史、Inspector 折叠） |
| `docs/ui-redesign/**`（说明、截图、浏览器报告）、`tests/browser/workspace.cjs` | 整体采用，作为界面基准与作者场景记录 |
| 7 个扩展页 `index.html`（code_facts、context_authority、continuity、continuity_github、handoff、team_footprints、worklog） | 采用其外壳化改动 |
| `web/archworkbench.js` | **合并**：以 PR #56 版为界面骨架，逐项接回阶段一真实功能（见第 3 节），未用 v1 版本覆盖 |
| `README.md` | 保留阶段一的工作台说明并更新能力描述 |

## 2. 页面/区域迁移清单

| PR #56 页面 | 阶段一旧入口 | 迁移后真实后端 | 验证 | 例外 |
| --- | --- | --- | --- | --- |
| Overview | 首页 `/api/snapshot` 摘要 | 快照 / 工作区历史 / 日志 / AI 配置并行读取 | 浏览器逐页检查（0 JS 异常） | 无 |
| Architecture（创建） | 架构工作台 STEP 1 | `POST /api/archloop/workspaces`（身份来自 origin URL） | 浏览器故事 1/2 创建工作区 | 无 |
| Architecture（画布/Inspector） | STEP 2/3 画布与节点详情 | 草稿 CAS（`apply-ops`）、证据跳转固定 SHA | 编辑职责与过程后刷新仍在 | 无 |
| Architecture（生成） | 生成候选 / 规则候选 | 真实 AI（未配置 `NOT_RUN`）与 C 规则引擎 | 规则候选生成 + 应用（浏览器） | 真实 AI 未配置 |
| Architecture（偏差处理） | STEP 4 三件事 | 保存草稿到版本服务 → 人审预览 → 确认/拒绝 → 发布（B 版本服务）；版本历史；导出同版交接包 | 两条故事完整走通（含架构 Git 提交） | 无 |
| Architecture（修正任务） | 创建开发任务 | D 权威 `FixTaskService`（创建/接手/开始/回挂/实测核验） | 浏览器完成 queued→received→in_progress→verification_pending→verified | 无 |
| Architecture（纠正/增量/偏差） | 自然语言纠正、增量候选、偏差检查 | C 规则引擎（错误来源/版本返回 UNKNOWN） | 页面入口存在并可调用 | 无 |
| Changes | 变更审查页 | `compare_commits` + 证据变化 | 页面渲染当前提交 | 无 |
| Decisions | 关键决策（worklog 分类） | 原 worklog 扩展 | 页面渲染并声明未独立核实 | 无 |
| Handoff | 协作交接页 | 原 handoff/continuity/worklog 扩展 | 三个页签可打开 | 无 |
| Worklog | 工作日志页 | 原 worklog 扩展 | 页面渲染 | 无 |
| Repository | 仓库浏览页 | Repo Explorer（open/symbols/relations/changes/file） | 页面渲染；HTTP 边界由回归覆盖 | 无 |
| 全局导航/搜索 | 侧栏（旧） | hash 路由、⌘K 搜索、页面历史、状态栏 | 六页逐一切换，0 JS 异常 | 无 |

## 3. 合并进 `archworkbench.js` 的阶段一功能（行为依据）

1. **写会话与防伪**：`ensureSession()` + `api()` 附带 `X-CSRF-Token`，`FORBIDDEN_SESSION/FORBIDDEN_CSRF` 时自动重建一次（D-A-02 的浏览器侧）。
2. **人审三步**：`arch-sync-button` / `arch-review-preview-button` / `arch-review-confirm-button` / `arch-review-reject-button` / `arch-publish-button`（PR #56 的单步“复核并保存”被真实三步流程取代；对话框收集操作者与理由并绑定会话）。
3. **版本与交接**：`arch-versions-button`、`arch-handover-button`（不可变版本历史、同版交接包）。
4. **修正任务**：`arch-fixtask-button` 用选中节点的证据路径、期望过程与生命周期真实创建 D 任务；`arch-fixtasks-button` 提供接手/开始/回挂/实测核验入口。
5. **C 引擎入口**：`arch-rulegen-button`（规则候选，覆盖与 planning 文案如实）、`arch-deviations-button`、`arch-incremental-button`。
6. **过程编辑**：`input` + `change` 双事件提交（仅 `change` 会在不触发 blur 的宿主里丢文本）。
7. **响应字段**：发布响应按 `published.version/provenance` 读取；工作区刷新用 `openEnvelope(await api("GET", …))`（PR #56 没有 `refreshEnvelope`）。

## 4. UI_PENDING_OWNER（本轮保留原样，交给 UI 队友）

| 路由 | 页面 | 负责模块 | 功能验证 | 建议归属 | 依赖 |
| --- | --- | --- | --- | --- | --- |
| `/ext/architecture_workspace` | B 的架构工作区控制台（草稿/人审/版本；PR #56 未覆盖） | `extensions/architecture_workspace`（B） | HTTP 200；页面读 `/api/extensions/architecture_workspace`；截图 `snapshots/ui-pending-architecture_workspace.png` | UI 队友 + B 作者 | 需要把 B 的草稿/人审/版本控制台并入新外壳的 Architecture 页面或独立页 |
| `/ext/map_proposal` | C 的提案控制台（六类提案；PR #56 未覆盖） | `extensions/map_proposal`（C） | HTTP 200；页面读同一扩展接口；截图 `snapshots/ui-pending-map_proposal.png` | UI 队友 + C 作者 | 与 `arch-incremental-button` 的候选入口统一 |
| `/ext/project_summary` | 扩展样例页 | `extensions/project_summary`（示例） | HTTP 200；截图（同目录，未单列） | UI 队友 | 低优先；样例性质 |

以上页面在新外壳中通过侧栏「Extensions」入口可达，**保留可用原样**：本轮只做了外壳可达性（PR #56 已为其中 7 个页面加上统一外壳），没有重新设计它们的布局、风格或交互。

## 5. 样式作用域

- PR #56 的 `web/styles.css` 是全局样式表，被主页与扩展页共同引用；本轮**没有新增**会改变未迁移页面的全局规则（只沿用 PR #56 已生效的类）。
- 迁移后对未覆盖页面逐一截图核对（见第 4 节与 `snapshots/`），无横向溢出、无脚本异常。
- 新页面（B/C 控制台）保持原有布局；如后续统一风格，由 UI 队友按本清单接管。