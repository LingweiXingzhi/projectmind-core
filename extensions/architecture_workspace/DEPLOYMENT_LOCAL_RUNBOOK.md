# 部署准备：本机验证与交付步骤

状态：LOCAL_PREPARATION_ONLY；不是公网部署说明已验收。
适用源：A803c 完整项目 + 本 PR 的 B owner 增量；公共接线未修改。
旧 c3d checkout 的 `app.py` 没有这些新参数，不能直接使用下面的完整项目启动命令。

## 1. 固定完整应用与状态目录

负责人先在新的集成副本追加 B owner 增量，记录应用代码 SHA 和工作区是否干净。
代码证据 Git 与架构发布 Git 使用两个独立副本；B SQLite / A 记录放在源代码工作区之外。

| 资源 | 用途 | 后续服务器必须保存的内容 |
|---|---|---|
| 应用副本 | app.py、工作台、适配层、B/C/D 运行代码 | 固定版本、运行配置；升级不要覆盖状态 |
| 登记的代码 Git 副本 | 固定 SHA 的代码证据，只读 | Git 对象/来源；本轮历史测试还缺上游历史 |
| 独立架构 Git 副本 | B 发布认知版本 | .git 和版本内容、`architecture/candidates/*` 分支 |
| A 数据根 | workspace/draft/history JSON | workspace 记录与 B 绑定关系 |
| B 数据根 | workspace.sqlite3、事务/发布日志 | SQLite 状态，按一致性备份方式保存 |
| D 记录 | 接续、任务、足迹 | 当前旧 D 部分数据在代码 Git common dir 内，不能仅备份普通工作区文件 |

备份操作需停写或使用 SQLite backup API；不要单独复制仍在写入的数据库文件后称恢复通过。
跨客户端获取架构 Git 是版本共享，服务器内存人审授权不通过 Git 分享。
单实例是当前验证形态；A 记录使用进程内锁，浏览器人审会话也未实现跨进程共享。

## 2. 当前可复查的完整项目启动

在**包含当前 A 接线的整合应用目录**运行，替换明确的本机路径：

```sh
python app.py \
  --port 8765 \
  --repo "<登记的代码Git副本>" \
  --archloop-data "<源代码外的A数据根>" \
  --archloop-backend-data "<源代码外的B数据根>" \
  --archloop-architecture-repo "<独立架构Git副本>" \
  --archloop-architecture-branch "architecture/candidates/<自己的候选分支>" \
  --archloop-code-repo "<登记的代码Git副本>"
```

Python 3.10+ 与 Git 是前提；Windows 按 requirements 安装 tzdata，Linux 验证系统时区数据库。
架构候选分支要提前建立且工作区干净。候选分支发布不合并产品 main 或正式 model main。
`--repo` 不附人工地图时保留无地图浏览模式，架构工作台仍从说明开始。
AI 密钥如需配置只放服务端环境；本次探测没有模型调用。

## 3. 使用 B 预检

在同一完整应用目录运行。输出必须是新建的绝对路径，位于所有 Git 工作副本之外。
用未来的准确 HTTPS 域名作为参数；示例 `.invalid` 是夹具占位，不会做 DNS 查询。

```sh
python -m extensions.architecture_workspace.deployment_preflight \
  --base-url http://127.0.0.1:8765 \
  --public-origin https://demo.example.invalid \
  --output "<Git工作副本外的新绝对报告目录>"
```

程序仅向显式 loopback 地址发送 8 个 GET，不创建工作区或人审会话。
它分别检查本机来源、无 Origin、原样公网 Host/Origin、公网 Origin 加本机 Host，
目标 API 为 `/api/archloop` 和 `/api/archloop/backend`。

报告：`DEPLOYMENT_PREFLIGHT.json`。
退出码 **2** 表示诊断已完成，但仍为 `NOT_READY_FOR_PUBLIC_DEPLOYMENT`；
退出码 1 是输入/报告存储错误。即使 8 项都返回 200，也不能用此工具证明登录、TLS 或远程发布安全。
当前真实 A 的公网头返回 403，是需要协调的边界，不通过改写头消除。

## 4. 当前实际运行结果

本轮在 A803c + 新 B + 固定 D 组件的独立程序集里，使用 app.py 的真实 CLI 启动。
数据和 Git 仓库全部由验证程序新建，不使用用户真实工程进行模拟审批。

| 请求条件 | 两个 API 的实际状态 |
|---|---|
| 本机 Host + 本机 Origin | 200 / 200 |
| 本机 Host + 无 Origin | 200 / 200；这是当前读取行为，不是登录证明 |
| 公网 Host + 公网 Origin | 403 / 403，FORBIDDEN_HOST |
| 本机 Host + 公网 Origin | 403 / 403，FORBIDDEN_ORIGIN |

调用一次 Python API，再调用一次模块 CLI，共 16 个诊断 GET，另有启动就绪轮询。
两次报告前后 A 记录、B documents、代码/架构 Git 未变化；真实 B 后端 available=true。
CLI 退出码为 2；服务在验证后停止。没有公网 DNS、TLS、登录或真实远程人审记录。
相关证据在 verification 下的 `deployment-2026-10-08-*` 文件。

## 5. 给 A 的明确接线清单

1. 选择包含最新 B/C/D/UI 的固定发布候选；补齐上游 Git 历史验证和当前审查残留。
2. 提供准确外部 HTTPS origin；定义受信代理、真实浏览器身份和工作区权限。
3. A 从可信服务器会话注入身份与请求元数据；不能使用客户端 JSON 中的 actor/forwarded 作为证明。
4. 同步更新公共 Host/Origin 校验、B 人审绑定、D 任务 Gateway；保留 CAS、CSRF、预览摘要和显式人工确认。
5. 服务器仓库登记取代公网用户任意提交本机路径；确认旧 D 数据位置与代码只读策略兼容。
6. 冻结契约后由各 owner 实现；再提供 HTTPS/登录/进程守护与备份恢复配置并实机验证。

没有服务器和域名也可以先完成以上应用准备与本地验证。
上线阶段再做域名解析、TLS、登录，以及不同网络第二设备的端到端验收。
本文件不给未完成适配的服务开放公网入口。
