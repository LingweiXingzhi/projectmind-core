# 下一阶段：任务协作与界面接续

状态：已审视并形成实施计划，尚未把新 D/UI 接入运行入口。
当前已上传候选：Draft PR #61，基线整合 803c6736d1ab01bee004a77c2d2b3b140b28cb12。
仍按整项目开发，不恢复旧 ABCD 写入范围限制。

## 已确认的差距

1. **版本不相同**：A 的 _legacy_fix_task_delegation 发送 draft.graph.mapRevision（maprev-*）。
   D 的 create_archloop_backend 要求服务端登记的 versionHandoff 中 B 的 sha256:* mapRevision。
   单独复制 D 文件不会接通；不能把草稿 hash 改名当已发布版本。
2. **工作区身份不相同**：A 工作区与 B workspace/map 绑定须逐字段查清。
   D 严格核对请求 workspaceId 与 versionHandoff.workspaceId，禁止猜测或客户端覆盖。
3. **来源包不相同**：旧 architecture_handover_v1 与新 architecture_handoff_v1 是不同格式。
   新 D 包须由真实 B 已确认版本包和固定来源构建，不给旧包换 schemaVersion 冒充。
4. **会话未接上**：D FixTaskGateway 目前只接受 http 本机来源，并使用本机声明 actor。
   公网入口已获得真实登录 actor/浏览器绑定；须用 Python 可信请求元数据接续，
   精确 HTTPS 来源与实际 loopback peer 保持，JSON/代理头不能提供身份或批准。
5. **状态目录未接上**：D Continuity Store 可以接受独立 SQLite 路径，默认旧扩展位于代码 .git。
   公网运行应明确使用已有私有 dataRoot 下的 D 子目录，纳入单实例锁及停机备份。
6. **界面需适配**：UI PR #56（2ef017917feb0308f2c477610630ab72d6b7a3e3）
   新增布局/画布/搜索，但仍有 actor 声明对话框、证据读取的本机绝对路径输入、
   固定 Local 在线标识、依赖旧扩展的 worklog/decisions 聚合。
   公网页面应使用登录账户、已登记仓库和真实能力状态；不得盲目覆盖本轮修复。

D 对照源码：PR #54，固定 c8b942a8d724b1bd0509f61b2db6ec642a117181；
读取了 architecture.py、archloop_backend.py、fix_tasks.py、fix_gateway.py、store.py。
UI 对照读取了完整变更文件清单及上述实际 patch；其历史浏览器报告不作为当前候选的证据。

## 执行顺序与验收

### 1. 服务端版本绑定与任务创建

- 先核对最新 GitHub refs/PR 与本地工作区，不覆盖任何更新或未提交工作。
- 在独立候选中接回新 D 的固定源码，复用 B 的正式版本 export 与 D 的包构建/校验函数。
- 在 A 服务增加明确的受保护接续路径：只取当前工作区实际已发布版本，核对 draft 与 lastPublish
  的对应关系、代码来源/代码 SHA、独立架构 Git mapSourceRevision 及 A↔B 绑定。
- 未发布、草稿偏离、跨仓库、跨工作区或版本不一致均返回机器可读错误；规划模式不伪造代码事实。
- D 私有状态由服务器配置；操作者/偏差身份来自真实会话与服务端持久记录。
- 测试真实公开路由创建任务、错误版本/伪造 actor 拒绝、服务重启后任务读取、代码 Git 未改。

### 2. 任务状态、回挂与验证

- 接续 queued→received→in_progress→submitted→verification_pending→verified；严格沿用 D 的 CAS。
- 提交校验独立实现分支、固定 SHA、允许改动范围及中间提交，不能信任客户端“测试通过”。
- 验证 provider 只允许服务器配置；无 provider 保持 NOT_RUN。
- 验证预览与人工确认绑定相同真实浏览器、任务及版本；不允许 JSON human_confirmed/command。
- 先完成配置内的可复现夹具闭环，明确其不构成真实项目验收。

### 3. UI 接续

- 对 UI #56 与当前 HTML/JS 做逐项合并，保留真实账号、CSRF、登记仓库与当前错误语义。
- 优先接画布/详情、已发布版本和新任务状态；旧 worklog/decisions 依赖不可用时明确显示能力状态。
- 布局偏好可以留浏览器，批准身份与真实服务器路径不能依赖 localStorage。
- 脚本语法、页面所需 DOM 与 HTTP 能力先验；可运行浏览器环境恢复后再验实际点击、拖拽与移动布局。
  当前浏览器 NOT_RUN 状态保持，不能用源码检查代替浏览器通过。

### 4. 阶段交付

- 按实际改动运行 D 接续、入口边界与 A/B/C 回归；共享路由/持久化改动完成后再完整回归。
- 新增 D 状态后重复完整停机备份/恢复，核对所有数据根和版本来源。
- 上传独立候选并核对远端树、Draft 与 main；更新 Result/Files Changed/Verification/Model Impact/Risks。
- 云服务器/域名、真实 AI、正式 Model 文本缺口继续保留，不能提前写成完成。

## 本次补充验证

新增 GEN-01 整包回归：合成 clientAPIKey/HTTPAccessToken 内容不进入固定提交上下文包；
普通 clientAPIEndpoint/monkey 等代码保留；工作树修改不能改变所读固定提交。
公网入口专项现为 16 项，2.927 秒全部通过。本次只增测试与计划，运行源码未改；
此前完整 936 项结果仍对应原 c949 实现，不把新增项冒充完整重跑结果。

Project Model Impact：本文件只记录实现缺口与接续计划，沿用 UPDATE_CANDIDATE，不修改正式 model。
