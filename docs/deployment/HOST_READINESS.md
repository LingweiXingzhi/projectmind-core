# 域名前的服务器部署准备

本轮从 PR #68 固定提交 `5be9af307ef1f631af3301e5f2521dfea3f4d436` 接续。
目标是同一团队、同一服务器上的受保护共享工作台，后端仍只监听 127.0.0.1:8765。
域名可以最后购买，不阻碍准备和本机演练；没有服务器时不能完成真实 systemd 启动、云防火墙、公开证书及跨网络设备验收。
下面的命令都要求已经 checkout 包含本轮工具的固定提交，而非旧 main。

## 已补齐的工具

| 工具 | 行为与边界 |
|---|---|
| `deployment.host prepare` | 生成私有准备目录、runtime、Caddy、两个服务单元和三个运维脚本；不创建密码、不启动服务 |
| `deployment.host render-domain` | 保留现有仓库、数据、架构配置，生成匹配真实域名的 runtime/Caddy 新副本 |
| `deployment.host stage-release` | 从干净且非浅克隆的本地来源安装指定完整 SHA 的独立 Git 副本，保留历史、不激活、不覆盖 |
| `deployment.host preflight` | 检查私有权限、Git 完整性、代码来源、架构候选分支、精确应用提交；不启动服务、不初始化业务库 |
| `deployment.host backup/restore` | 复用原冷备，新增来源绑定收据；恢复到新目录，不自动重绑工作区、不恢复登录授权 |
| `install.sh` | 显式 root 安装独立版本/venv/服务文件，不启动服务，不覆盖账号或既有 runtime/Caddy |
| `activate.sh` | 实机预检、原版本冷备、停止服务、原子切换版本、检查真实后端401，再启动HTTPS；失败保持停止 |
| `backup.sh` | 排他维护锁，停机并持有数据租约后备份，校验成功才恢复原运行状态 |
| `deployment.host_smoke` | 验证证书链和主机名、登录边界、两会话CSRF与退出；不批准架构、不写项目业务数据 |

## 现在即可准备

```sh
# 必须是 Git 外的新目录；省略 domain 只生成离线准备包。
python3 -m deployment.host prepare --output /tmp/projectmind-host-ready
```

准备包使用 `projectmind.example.invalid`，公网激活预检会明确拒绝它。
准备包中没有账号或 API Key；不把实际配置、备份或服务日志加入 Git。
准备包是可重新生成的配置集合，最终应用固定版本以 PR 的完整提交为准。

## 服务器到位后安装（尚未实机验收）

选择支持 Python 3.10+、Git 和 systemd 的 Linux 主机。使用官方安装方式准备 Python/venv、Git、Caddy（本轮演练为2.11.7），不执行来源不明的远程脚本。
本工具不采购资源、不设置云账号、不修改云防火墙。

1. 通过正常 Git 授权获取完整私有仓库历史，凭据不写入 remote URL。checkout 本轮或后续审定提交，确认工作区干净。
2. 在该固定源码目录生成准备包。以 root 执行：

```sh
# 第二参数必须为该完整源码副本实际 HEAD，不是 PR 编号。
bash /tmp/projectmind-host-ready/install.sh /srv/projectmind/source 完整40位SHA /tmp/projectmind-host-ready
```

安装目录：`/opt/projectmind/releases/SHA/app` 和该发布独立的 `venv`。
`current` 在显式激活时才指向选定版本。升级不替换 state 或 architecture，不复用旧依赖环境。
安装需要真实 Caddy 账号及 `/usr/bin/caddy`，不停止其它站点的代理；激活前检查80/443是否被占用。
两个服务文件是独立的 `projectmind.service` 与 `projectmind-proxy.service`。
应用运行用户为 projectmind；应用/venv由root拥有，代码证据在服务沙箱中只读。

3. 用 projectmind 用户获取独立架构仓库到 `/var/lib/projectmind/architecture`，切换到 `architecture/candidates/team`，配置 Git 提交姓名和邮箱，保留origin且工作区干净。
   不在正式图分支上发布，不把代码仓库复用为架构仓库。已有正式架构只作为独立来源，不自动批准。
4. 把需要分析的完整代码副本放到 `/srv/projectmind/code/`，按来源只登记一份，保持干净并由 projectmind 用户可读。
   如代码副本由root拥有，在 `/var/lib/projectmind/home/.gitconfig` 只添加每个准确副本路径为safe.directory；不要用 `*`。
5. 编辑 `/etc/projectmind/runtime.json` 的 `codeRepositories`，填写明确路径。无代码规划允许为空。
   runtime与accounts权限0600、projectmind可读；state为0700。架构副本/代码副本/业务数据互不嵌套。
6. 在发布源码目录，通过交互式CLI创建账号，不用命令行参数传密码：

```sh
runuser -u projectmind -- /opt/projectmind/releases/完整40位SHA/venv/bin/python -m deployment.server create-account \
  --file /etc/projectmind/accounts.json --username 你的账号
# 其他队友使用 add-account，每人独立账号。
runuser -u projectmind -- /opt/projectmind/releases/完整40位SHA/venv/bin/python -m deployment.host preflight \
  --config /etc/projectmind/runtime.json \
  --source /opt/projectmind/releases/完整40位SHA/app --expected-sha 完整40位SHA
```

上述命令的当前目录应为该发布的 `app`。`runuser`继承工作目录，因此必须确保projectmind能进入该目录。
服务账号home为 `/var/lib/projectmind/home`，safe.directory由安装脚本准确登记发布副本。
没有默认管理员密码；当前全部账号共享团队工作区权限，不冒充多租户隔离。

## 最后接入域名

先在当前固定源码目录用现有配置生成最终域名版本，保留所有源与数据路径：

```sh
python3 -m deployment.host render-domain --config /etc/projectmind/runtime.json \
  --domain 你的真实域名 --output /tmp/projectmind-final-domain
```

由root核对后把生成的 runtime.json 安装到 `/etc/projectmind/runtime.json`（0600、projectmind拥有），
把 Caddyfile 安装到 `/etc/caddy/projectmind.Caddyfile`（0644、root拥有）。这一显式操作只变更域名；不要用初始空配置覆盖已登记仓库。
若服务已运行，先停止再替换两份配置；更换origin会使旧浏览器会话/人审预览失效。

- 域名 A 记录指向服务器公网 IPv4；只有服务器确实支持 IPv6 才设置 AAAA。
- 云安全组和主机防火墙开放80/443供证书和HTTPS，SSH入口按实际管理来源设置；8765不开放公网。
- `/var/lib/caddy`保存证书、续期状态和本机admin socket，caddy拥有且持久化。
- `/etc/projectmind/model.env`为可选私有服务端模型配置（root拥有0600），按 PROVIDER_AND_C.md 填写；systemd不把密钥传给浏览器。
- 定义真实任务验证器仍需对应实现与配置，不能把“回挂提交”当成已验证完成。

```sh
# 完成域名和目录检查后再激活；未配置真实域名会被拒绝。
sudo bash /opt/projectmind/activate.sh 完整40位SHA
python3 -m deployment.host_smoke --origin https://你的真实域名 \
  --username 测试账号 --output /tmp/projectmind-public-https-report.json
```

公网检查不使用 `--ca` 或 `--connect-ip`，默认验证公开CA、DNS与域名。
两参数仅用于明确标记的本地TLS演练，不跳过证书验证。
无 `--username` 时只检查匿名边界，不代表登录验收完成。
真实浏览器还要验证中文页面、下载、架构确认与共享日志，第二设备须经不同网络读取同版材料。

## 备份、恢复与回退

```sh
sudo bash /opt/projectmind/backup.sh /srv/projectmind-backups/你选择的新备份名
```

只保存私有state和完整architecture，伴随 `备份名.binding.json`。
收据记录代码路径、origin哈希和固定提交，校验完整性，不提供签名来源证明。
账号、runtime、model.env、Caddy证书应另作私有备份；内存登录/人审授权不恢复。
备份失败时应用保持停止，查看原因并修复后再启动，不能拿失败目录继续写数据。
停止短时间写入属于冷备约定，不能当作无停机热备。

恢复仅到新目录；原配置对应数据根运行时会拒绝恢复。保留同样的登记代码路径、来源和完整HEAD，工具不自动迁移旧工作区身份：

```sh
# 在固定发布源码目录，停止应用之后执行。
python3 -m deployment.host restore --backup /srv/projectmind-backups/备份名 \
  --config /etc/projectmind/runtime.json --output /var/lib/projectmind/recovered-你选择的新名称 \
  --runtime-output /etc/projectmind/recovered-runtime.json
```

输出与旧state/architecture、代码、备份互不包含。恢复保留旧数据，校验SQLite/Git/文件哈希后才生成新runtime。
root执行恢复后，须将恢复目录及新runtime交给projectmind拥有（runtime0600、数据根0700），
再以服务用户执行preflight和实际工作区读取。核对成功后显式采用新runtime并重启；不要自动删除原数据或备份。
如果换服务器时路径/来源/HEAD不一致，保留阻塞，不能修改收据绕过检查。跨机器身份迁移另开任务。

代码回退先确认该旧版本兼容当前数据格式，再 `activate.sh 旧完整SHA`，它同样在切换前冷备。
不自动把数据库回滚到旧时间，不声称任意版本均可兼容当前数据。
维护脚本使用同一排他锁，避免同时备份与切换。失败后查看 `systemctl status` 与 `journalctl -u projectmind -u projectmind-proxy`，运行日志不上传公共材料。

## 完成边界

本轮可完成：源码工具、生成包、真实临时Git/HTTP、本地可信CA与主机名验证、冷恢复、配置/脚本回归。
本轮不能凭空完成：真实云服务器开机、systemd重启/开机自启、云入站规则、DNS、公开CA签发与续期、不同网络第二设备。
模型整体超时/取消仍由队友对应工作线处理；真实厂商调用与任务验证器不因本轮运维工具存在而验收通过。
最终独立审计、两条开发线全部功能差异核对、共享日志附件等既有未收口项保留；本轮不合并main或批准正式Model。

官方参考：[Caddy 自动HTTPS](https://caddyserver.com/docs/automatic-https)、[Caddy systemd服务](https://caddyserver.com/docs/running#linux-service)。

Project Model Impact：MINOR。补齐既有deployment内部运维，不改变公共业务接口或认知批准权限。
