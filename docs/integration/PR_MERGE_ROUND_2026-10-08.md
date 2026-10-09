# 新增 PR 原样合并集成记录（2026-10-08）

本轮把新增 PR #61–#68 用真实 Git 合并（`--no-ff`，固定来源 SHA）合入本分支，
产品起点为 PR #60 的固定提交 `ad119865a82f2faad0ebc8bdd47475e43c93a6e8`。
作者实现、接口、存储、页面与历史保留；本轮只做冲突解决、必要接线与一处已复现缺陷的
最小修复。逐文件冲突对照与证明见交付包（`MERGE_MANIFEST.json`、
`CONFLICT_RESOLUTION.md`、`LOCAL_FIXES.md`）。

## 来源与合并提交

| PR | 来源 SHA | 合并提交 | 冲突 | 说明 |
| --- | --- | --- | --- | --- |
| #60（起点） | `ad119865` | — | — | 产品基线（含模型协议提交） |
| #63 | `27e779f3` | `cfc3a43` | 0 | 中文界面（并行线） |
| #61 | `53024146` | `831a3a2` | 8 | HTTPS 部署准备 |
| #62 | `4f6083ad` | `b7cd762` | 15 | 共享工作台任务治理（双 adapter 并存） |
| #64 | `cc4cfa45` | `7f36d19` | 2 | 共享工作日志与决策候选 |
| #65 | `c481584a` | `4f5b393` | 0 | 私有冷备与完整性校验 |
| #66 | `d47b3c62` | `2b06f9d` | 6 | C 同版观察与模型协议接续 |
| #67 | `c65a6a09` | `616fb6b` | 1 | 中文工作台与原生交接包显示 |
| #68 | `5be9af30` | `e0bec10` | 0 | 异常模型协议形状控制（第七阶段前置） |

以上每个来源 SHA 都经 `git merge-base --is-ancestor` 证明为最终 HEAD 的祖先。

## 关键保留决定

- **双 adapter 并存（#62）**：本地入口（`app.py`）绑定 `BackendD`，共享服务器入口
  （`deployment/server.py`）绑定 `GovernedTasks`；两者原样保留在
  `archloop/backend_d.py`，`archloop/service.py` 增加最小的能力分派
  （`_governed_tasks()`），不改变任一 adapter 的请求/响应字段。
- **中文只影响显示**：按钮 ID、路由、请求字段、枚举、JSON、代码路径与导出数据保持原协议；
  未知技术标识保留原样（`web/` 与扩展页）。
- **等价改动不重复实现**：#61 的缩写切分（被本线复合凭据词修复覆盖）、#62 的 PR #56
  外壳工作（本线迁移版已含）、#66 与本线各自的 provider transport 延续（取 #66 硬化 +
  保留本线 `baseUrl` 显示）。

## 本轮修复

- **FIX-01（已复现）**：本地入口导出同版交接包在合并后 `AttributeError`
  （`BackendD` 没有 `handover`）→ 改为只对治理 adapter 调用 `handover`；
  复现与修复后证据见交付包 `LOCAL_FIXES.md` 与 `evidence/repro_handover_backendd.py`。

## 验证与边界

- 本机（Windows）执行并在交付包中留有记录的：全量单元/集成回归
  （`test-results/full-suite-*.log`，1046 项、failures=0、4 项平台 error 且与起点逐项比较）、
  本地入口的真实 HTTP 验收（`test-results/local-acceptance*.json`，21/21 PASS）、
  D 权威任务全生命周期含真实命令核验（`test-results/d-lifecycle-evidence.json`）、
  真实浏览器中文界面/任务列表/交接包下载/小屏布局（`snapshots/`）。
- 未在本机执行的（作者以 `skipUnless(os.name=='posix')` 显式门在 POSIX，本机无
  `fcntl` 与 0700/0600 语义）：公共 HTTPS 入口（Waitress+Caddy）、治理/共享记录端到端、
  单实例租约、停机冷备 CLI —— 记为 NOT_RUN，其 POSIX 证据见 #61–#67 各自交付文档。
- 未验收项：公网/域名、第二设备、真实 AI 模型、真实项目任务验证器、Linux 守护与证书续期
  （NOT_RUN）。部署准备合入不等于授权发布公网。

## 审计与复审

- 冻结版本 `51a119400ad74cc2163400c1bfc975b18233b08f` 交只读 Codex 审计，结论
  `CHANGES_REQUESTED`（F-01 治理 adapter 缺两个导入；F-02 C 偏差响应丢三个字段；F-03 ai_status
  的 baseUrl 放错分支）。三项均为本轮合并失误，已按下述方式最小修复：
  - F-01：补回 `from copy import deepcopy` / `from dataclasses import replace`（来源原文）。
  - F-02：按 #66 固定来源补回 `rejectedTraces` / `inconclusive` / `coveredNodes`。
  - F-03：未按审计建议把 baseUrl 补回已配置分支 —— 那会使来源 #66 的边界测试真实失败（公共状态
    不得回显可含凭据的端点）；最终两个分支都不再返回 baseUrl，并移除 generate 状态里的死字段。
- 修复后重跑全量回归与本地入口真实 HTTP 验收（21/21 PASS），提交固定新 SHA 后做一次完整复审；
  详细复现、根因与验证见交付包 `LOCAL_FIXES.md`、`SELF_CHECK.md` 与 `evidence/audit_fix_probes.py`。
