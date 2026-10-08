# 域名前部署准备交付（Issue #69）

## Result

固定起点：PR #68 / `5be9af307ef1f631af3301e5f2521dfea3f4d436`。
独立分支：`feat/69-host-readiness-20261008`。
最终运行源码远端提交：`2fa41db622efde036fde0ef2c5a5b4d701319afc`，tree `3d2745d415f64d700b7ee1babd56bf713ad516fe`。
该提交为第一轮运行源码基线。用户要求继续后追加维护失败路径与主机盘点，
最新运行版本以PR #70最新完整HEAD为准；续作证据见 `verification/host-maintenance-20261008/`。

已补齐可执行的域名前准备包、保留既有源的域名切换、固定SHA发布安装、只读预检、
排他维护/停机备份、来源绑定的新目录恢复、显式代码回退及HTTPS登录检查。
运行和接入操作见 [HOST_READINESS.md](HOST_READINESS.md)。正式图、main及队友分支未修改。

## Files Changed

- `deployment/host.py`、`host_smoke.py`：准备、精确版本/权限预检、来源绑定备份恢复、可信TLS登录检查。
- `deployment/host_templates/`：安装、备份、激活脚本，独立systemd/Caddy服务配置。
- `tests/test_deployment_host*.py` 与 `verification/rehearse_host_user.py`：真实Git、TLS、拒绝路径和服务用户演练。
- 本手册及 `verification/host-ready-20261008/`：机器报告、日志、源码与证据哈希。

## Verification

| 检查 | 实际结果 |
|---|---|
| 全仓源码快照回归 | 1027项，1012通过、15跳过，139.572秒；在最终标准端口检查之前运行 |
| 最终部署专项 | 25项全通过，4.048秒；包含新增端口拒绝、实际Caddy TLS与可信CA/错误SNI边界 |
| Waitress CLI + Caddy 2.11.7 TLS | 40个真实请求：已有项目和planning、两会话、模拟人审/真实架构Git发布、D任务、共享日志和CAS拒绝 |
| 新HTTPS入口检查 | 14项通过，包含两次登录、CSRF/跨会话令牌拒绝、退出失效；未保存任何密码/授权令牌 |
| 新来源绑定冷恢复 | 2工作区、1任务、2记录及历史/版本一致，登录和D授权会话未恢复 |
| 安装准备/源版本工具 | 真实临时Git发布副本保留完整夹具历史，已存在/脏源拒绝；域名前准备包生成成功 |
| 配置/语法 | Caddy真实validate、Bash语法、Python编译、diff检查通过 |
| systemd单元 | 替换为本runner可用可执行路径后，systemd-analyze verify通过；原生产路径尚不存在的报错不冒充通过 |
| 普通用户/实机systemd | NOT_RUN：UID/GID只映射root、PID1不是systemd；提供可在真实服务器运行的明确演练工具 |

两次早期广回归缺少上游已存在的JSON/JSONL夹具，读取精确blob补齐后重新运行并通过；
没有伪造新夹具或把失败日志当作通过。最终端口边界之后只重跑相关25项，没有声称重跑整仓。
本地无法认证Git CLI，实际读取了260个精确上游源码/夹具blob；本地为源码快照，不是完整上游历史clone。
运行源码/模板13个远端blob已逐一与本地核对一致，详见 CODE_MANIFEST.json。
所有夹具批准仅用于测试，不表示团队批准真实架构。公开证书未签发，没有公网部署。

证据入口：[SUMMARY.json](verification/host-ready-20261008/SUMMARY.json)、
[CODE_MANIFEST.json](verification/host-ready-20261008/CODE_MANIFEST.json)、
[SHA256.json](verification/host-ready-20261008/SHA256.json)。

## 用户要求继续后的补齐

修复升级备份后短暂恢复写入、启动失败仍可能自动重启、代理重启失败未停止应用、
固定临时链接遗留阻塞等维护失败路径。安装先检查systemd/Python/账号依赖且共用维护锁，
服务自身启动前也拒绝占位域名。新增只读 `deployment.machine` 和 [HOST_ACCEPTANCE.md](HOST_ACCEPTANCE.md)。

本次全仓源码快照回归1037项：1022通过、15跳过、0失败，143.224秒。
全仓运行期间的小幅模板/前置依赖检查调整另由最终部署专项覆盖：34项全通过，4.985秒。
专项再次执行真实Caddy/Waitress TLS与两会话14检查；维护故障测试的service/user控制明确为模拟。
当前容器主机盘点准确返回BLOCKED/5，不冒充实机已满足；新准备包生成成功，不启动服务。
新证据与精确代码SHA256见 [SUMMARY.json](verification/host-maintenance-20261008/SUMMARY.json)。

## Project Model Impact

MINOR。补齐已存在deployment模块内部的运维实现；不改变公共业务接口、架构确认权和模块职责。正式Model未修改。

## Risks / Follow-up

服务器/域名和访问条件到位后：实机安装与服务用户权限 → systemd启动/开机重启 → 云防火墙/DNS →
真实公开CA与持久化续期 → 公网HTTPS登录检查 → 不同网络第二设备/浏览器交互 → 真实模型与任务验证器/独立审计。
未配置验证器仍保持待验证，模型deadline/取消仍归队友；不替他们宣布完成。
备份收据是完整性和来源绑定，非签名来源证明；恢复要求相同代码路径/origin/HEAD，不自动跨机重绑。
代码回退需要对应旧版与当前数据兼容，不自动回滚/覆盖数据库。
保持Draft，目标为PR68分支供审查；没有合并main、采购云资源或发送队友消息。
