# A 集成修复清单（真实 HTTP 复现）

来源：固定 A b75ad820e0d31e3dadf842b414f6950b5aa46102、B runtime b58fee7455bf8348f50e3863759e53bbd711dc6d 和 D 782968ccd7a14de3b1b4b41f99f2e032cb7ad42b 的隔离组合。不是 A 已验收分支。原始请求/响应见 evidence/public-http-probe.json。

| ID | 实际现象 | 预期 / 责任 |
| --- | --- | --- |
| D-A-01 HIGH / T20 FAIL | 对同一 origin、同一代码提交的两个独立 clone 调用 POST /api/archloop/workspaces，返回不同 codeRepoId/mapId | A/B 统一稳定来源身份，不把本地 clone 路径纳入跨客户端 ID。D 使用 B 的来源哈希规则。 |
| D-A-02 HIGH | POST /api/archloop/workspaces 不带 Origin、Cookie、CSRF 仍返回 200 并写入 | A 将所有新增写操作接到会话/CSRF 检查；仅拒绝显式跨 Origin 不足以满足任务要求。D 的 FixTaskGateway 已有真实 HTTP 保护用例。 |
| D-A-03 BLOCKER | GET /api/archloop 返回 adapter.registered={}，即使模块共存 | A 注册真实 B persistence、C correction 和 D handoff，提供可信 workspace/version/actor/scope 上下文与服务端验证器。不能用样例冒充生产。 |

正确行为也已观察：跨来源显式写入 403，演示图正式发布 403；AI 未配置返回 NOT_RUN；显式样例直接编辑可重开保留。它们不能替代完整生产闭环。

## 接口对接

D 入口为 extensions/handoff/archloop_backend.py 的 create_archloop_backend(service, workspace_provider)。provider 必须来自受保护的服务器配置，给出 B versionHandoff、actor、scope 和可选的 deviationId/日志引用。FixTaskGateway 从实际 peer/Host/Origin/Cookie/CSRF 建立 RequestContext，不能从 JSON 读取执行命令、身份或本地仓库路径。

A/B 目前 mapRevision、图节点/过程形状与 codeRepoId 仍不一致；B 新增 V2 文档为 DESIGN_CANDIDATE/NOT_IMPLEMENTED，不能当运行时契约。C 新闭环服务未交付，D fixture 的 C_TEST_DOUBLE 不是 C 再核验。请在 A 的新 integration 分支协调，勿写旧 integration/main。独立审计 AUDIT_PENDING；模型候选须人工确认。


接续已读取真实 C 55ea6466583d98e0f466e5d4055922ef4aeecb12 与 B 8315c2e67aef2fa532869595441e68c29ae1beb3。原三项 A finding 仍复现，新增 C 缺证/候选身份/固定证据及 B↔C 形状问题，共七项集中见 RESUME_DELIVERY.md，原始结果 evidence/resume/。之前“C 未交付”“V2 未实现”为首次交付时观察，不代表当前状态。
