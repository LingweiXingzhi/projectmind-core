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

- 全量单元/集成回归、真实公共 HTTP 验收、真实浏览器核对、冷备/停机测试均在本分支
  执行；日志与报告在交付包 `test-results/`、`evidence/`。
- 未验收项如实记录：公网/域名、第二设备、真实 AI/任务验证器、Linux 守护与证书续期
  （NOT_RUN）。部署准备合入不等于授权发布公网。
