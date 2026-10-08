# 第四阶段交付：冷备操作

## Result

新增 `deployment.server backup` 与 `inspect-backup`，可停机冷备私有状态/架构 Git 并只读核验。
服务正在运行、目标已存在、路径嵌套、链接/外部 Git 对象引用、损坏数据库和篡改清单均拒绝。
失败副本保留且缺少完整标记；没有覆盖恢复或自动停止服务操作。

## Files Changed

deployment/backup.py、server.py、tests/test_deployment_backup.py、COLD_BACKUP.md 与部署手册。
依赖 PR #64 固定 cc4cfa45d628d1396bca37e9fbdd88fdca39d298。
运行本地 4f2d163b6b79fdf5760f321096eb97132946660f，对应远端
999c0d38a3e42ecf53f5fdf69ffd3eb6def69d7e，同树 d3d5d244b7aaa8f1a2f5359565491121d9508d70。
后续交付提交仅加摘要和本文件。

## Verification

- 固定提交新增备份测试 6 项 / 0.758 秒，全部通过。
- 公共部署/身份/版本/任务/记录回归 27 项 / 10.668 秒，全部通过。
- 使用第三阶段真实 TLS 服务已停机的私有夹具，实际 CLI backup 与 inspect-backup 退出均为 0；49 文件哈希核验，B/D/工作记录三库完整性通过，源状态与架构 HEAD 未改。
- 另实际启动 Waitress CLI，再执行 backup：退出 1 / DATA_ROOT_IN_USE，输出目录未创建，随后关闭本次夹具服务。
- 证据在 verification/phase4/；复现命令见 COLD_BACKUP.md。账号/runtime 配置不在副本，登录授权不恢复。

本阶段变更限定运维 CLI，没有重跑后端全量；前阶段 984 项结果只作为基线，未写成本阶段全量通过。
演练是同机合成项目，不是云恢复或真实团队正式认知批准。
自检发现 SQLite 原始异常和 Git 超时需要控制错误，已转换为可识别 BACKUP_INVALID 后按固定提交重验。

## Project Model Impact

MINOR：部署模块内部运维操作，未改正式 Model 或认知批准规则。

## Risks / Follow-up

此清单是完整性检查，不提供签名来源保证；换机恢复还需核对代码来源/版本和重新登录。
公网资源、原生浏览器、真实模型/验证器仍未完成。
仓库最新整合 #60 与中文 UI #63 未合 main；后续在新候选中对照接口差异，保持本轮已验证成果可回退。
保持独立 Draft PR，不合并 main。
