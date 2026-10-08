# 生产操作者冷备与校验

## Result / 目标

补齐已有手册的可执行操作：只有服务停止并成功取得同一数据根的内核锁，才复制 state 与完整独立架构 Git。
命令不停止其他服务，不覆盖旧备份，不恢复覆盖现有数据，也不删除失败产物。
这不是云灾难恢复或热备 API。

## 操作

先用你已有的服务管理方式停止应用。选择源代码/Git 外的新私有备份位置：

```sh
python -m deployment.server backup \
  --config /etc/projectmind/runtime.json \
  --output /srv/projectmind-backups/新目录
python -m deployment.server inspect-backup \
  --directory /srv/projectmind-backups/新目录
```

数据根在使用时返回 DATA_ROOT_IN_USE；目录已存在返回 BACKUP_EXISTS。
全部检查成功才写 manifest.json 的 complete=true。失败目录保留，不把缺少清单的副本当作完成备份。
备份根 0700、清单 0600；内容仍为私有项目材料，不上传到产品仓库或公开下载。

## 范围与验证规则

- 复制 A/B/D/共享记录状态与架构 Git，包括架构 Git 对象/索引/当前文件，忽略仅有当前进程意义的 .serving.lock。
- 账号文件和部署 runtime 配置必须在数据根外，单独做私有备份；内存登录/确认授权不恢复。
- 校验 SQLite integrity_check、Git fsck/HEAD/branch、每个文件的 SHA256/长度；校验命令只读，不初始化应用存储。
- 输出不能嵌套在源数据/架构中，两份源也不能互相包含。
- 当前明确拒绝文件系统符号链接/特殊文件、架构 Git 工作树引用、commondir、external object alternates。
  遇到这些布局须先建立真正独立的可恢复 Git 副本，不能把可访问原机外部对象当作备份完整。
- 清单证明文件完整性，不是签名来源证明，也不替代恢复后工作区/代码仓库身份核验。
- 如需换机，保留对应代码历史、准备新的账号/配置、按手册重新绑定并验证。没有自动覆盖恢复命令。

## Files Changed / Verification

deployment/backup.py、server.py 命令接续及 tests/test_deployment_backup.py。
新增备份、占用/重用/嵌套目录拒绝、篡改与不完整清单、链接/外部对象/损坏 SQLite、账号混入数据根的边界检查。
固定提交的实际次数和真实数据冷备证据在对应交付记录中列明。

## Project Model Impact

MINOR：部署模块内的运维操作补齐，不改变模块职责或项目认知批准规则。正式 Model 未修改。

## Risks / Follow-up

磁盘容量、操作系统服务停止、备份介质保护由实际部署操作者负责；失败副本不得用于恢复。
云服务器/域名、原生浏览器、真实模型/任务验证器仍未完成。
新整合候选 #60 (ad119865a82f2faad0ebc8bdd47475e43c93a6e8) 与中文 UI #63
(27e779f3cf3924ad7930a6dcdd4fb7aa7d20c900) 尚未合 main，本候选不把其历史测试冒充本轮证据。
当前基于已验证 PR #64 树；后续另做新整合接口差异核对，保持当前可回退交付。
