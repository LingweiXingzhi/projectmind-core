# 个人 API 与老师共享演示 · 2026-10-08

## Result

依据用户明确要求实现两种独立配置，沿用既有生成、纠正、解释与人工确认流程。
开发基线：PR75 远端 6fc10006a981cce68b7faa4abc6231e4bf721634，树 f65bb596543b43586b683e99d98b985e6acccea5。
本地为经校验的完整源树快照，尚不是完整上游 Git 历史 clone。

最新界面修正：弹窗名为“AI 服务”，平台 AI 仅查看状态/额度，所有共享网页 Key 输入已隐藏；个人 API 是可选入口。后文初次原生验证中的“共享网页保存”属于改用服务器托管之前的历史测试，不代表当前界面。

最新简化：平台模式删除绿色剩余 token 栏，不展示或承诺分配额度；后台预算仍保留。按钮改为“检查 API 是否可用”，每次点击先读最新配置，有配置时发一次真实的固定连接探测，明确显示本次成功或失败。打开弹窗本身不触发模型调用，未配置时不发送模型请求；连接探测会计入后台预算。

### 用户自带 API

1. 工作台“检查 AI 接入” → “使用自己的 API（可选）”。
2. 输入 API Base URL、真实 API Key、账户可用模型 ID → “保存并开始使用”。
3. 点击“测试已保存的连接”；成功后按原流程生成或纠正候选。测试本身调用模型并计入额度。

调用使用该用户的 Key，消耗该用户供应商账户的额度。个人配置及预算不替换共享配置。
公网绑定可信登录账号，重新登录可继续；本地绑定浏览器会话，服务重启或会话到期需重新填写。
本机操作者的姓名声明不会让人取得另一用户的 Key。
浏览器只记录非秘密的模式选择；个人会话失效后仍请求个人配置，提示重新输入，不自动消耗共享 Key。

### 老师无需自己的 API

1. 管理员按服务器私有共享 API 说明，在服务器环境变量或 Secrets 中自行填写 Key、服务地址、模型 ID，启用托管模式并重启后端。
2. 普通工作台选择“使用平台 AI”，检查配置状态和共享额度，再通过生成结果验证真实可用性。
3. 老师打开同一服务的 `/?demo=1#home`，按已有项目/新想法流程操作。

展示入口不显示配置表单，所有模型请求选择共享配置，即便普通工作台当前使用个人 API。
展示页不再提供共享 Key 输入入口；普通工作台的“管理员：服务器配置说明”仅解释部署方式，不读取或收集平台 Key。
旧链接 `/?configure-ai=shared#arch` 现在打开平台 AI 状态，不打开共享密钥表单。
公网老师仍需正常登录，共享编辑/测试只允许服务器登记的配置账号。
本地模式仅用于可信电脑上的演示；`?demo=1` 是展示模式，不是管理员权限隔离机制。
localhost 链接仅当前电脑能访问；没有真实公网服务器/域名时不能作为跨设备公网地址交付。

用户提供的截图显示千问平台按量付费 OpenAI 兼容地址：
`https://maas.qianwenapi.com/compatible-mode/v1`。页面提供此地址预设；模型 ID 与真实 Key 由用户填写。
截图中遮挡的 Key 没有被读取、还原或使用。Token Plan 与按量付费端点、凭据、可用模型不可仅据截图认定相同。
实际目标供应商联网/结构兼容/真实用量验证当前为 **NOT_RUN**。

### 密钥不经过聊天的服务器托管方式

按 [服务器私有共享 API](../deployment/PRIVATE_SHARED_API.md) 在你自己的云平台后台或私有 ai.env 中自行填 Key。
PROJECTMIND_AI_SHARED_FROM_ENV=1 让共享 API 只读取运行环境，关闭共享网页配置/探测，不把运行环境 Key 写进 SQLite。
老师仍无需 Key；个人 API 不受共享托管设置影响。不要将填好的配置文件或 Key 发给 Agent。
技术隔离依赖服务器不向 Agent 开放访问；同一台共享电脑上的私有文件/进程环境不能保证 Agent 绝对无法读取。

## Files Changed

- archloop/ai_settings.py：私有 SQLite、账户/会话个人配置、共享配置、持久化预算、域名准入。
- archloop/ai_transport.py、ai_worker.py：绑定配置、输出上限、工作进程 usage 与保守预留/结算。
- app.py、web_session.py、deployment/server.py：受保护设置/选择/测试接口、可信身份、私有目录和共享配置编辑者。
- web/user-guide.js/css、archworkbench.js：简洁表单、模式选择、Key 清空、独立额度与老师入口；复用原写会话。
- generate.py、correction.py：候选记录实际调用的模型，避免配置同时改变造成来源标错。
- tests/test_ai_settings_demo.py、check_ai_settings_ui.cjs、test_deployment_backup.py：权限、真实工作进程与合成供应商、DOM、冷恢复验证。

## 接口与数据边界

| 接口 | 行为 |
|---|---|
| GET /api/ai-settings?mode=personal 或 shared | 状态、预算；有配置权限时可读地址与是否已存 Key，永不回传 Key |
| POST /api/ai-settings/select | 保存当前使用的模式；请求体仅 mode |
| POST /api/ai-settings | 保存 baseUrl/apiKey/model/protocol/tokenLimit/outputLimit，可附 mode；立即生效 |
| POST /api/ai-settings/test | 用已保存配置进行实际结构化探测，可附 mode；不接受临时端点 |
| POST /api/ai-settings/check | 已认证使用者检查当前个人/平台 API；请求只允许 mode，用固定小探测验证，受 CSRF、输出上限与预算约束，不授予配置权限、不回传 Key |
| X-ProjectMind-AI-Mode: shared | 展示入口选择共享模型，不授予编辑或认证权限 |

本地写入必须有同源 Host/Origin 和已有写会话 CSRF；公网必须经现有认证/CSRF。
公开个人端点只接受服务器登记的 HTTPS 域名和默认 443 端口；保存时及调用前都检查。
撤销域名后保留可读旧地址以便纠正，但拒绝再发调用。
本地回环 HTTP 可用于本地模型；远程 HTTP、重定向、URL 凭据/查询/片段继续拒绝。
Key 留空仅可沿用同一地址的既有 Key；换地址必须输入新 Key。
Key 存 Git 外服务端 SQLite，POSIX 目录 0700、文件 0600，不在浏览器 storage、日志、响应或提交中。
本地默认路径由数据根派生于用户私有配置目录，可用 --ai-settings 指定 Git 外绝对路径；
公网存于 dataRoot/ai，冷备包含配置与预算，备份因此也含凭据。

## 额度与失败行为

默认总额 50000、单次输出上限 2048；总额 1000–1000000、输出 128–8192，输出不能超过总额。
个人和共享账本分开，生成/纠正/解释/连接测试均经同一传输层。
调用前 SQLite 事务原子预留输入字节、协议开销、输出与可能的兼容重试；不足时在启动工作进程之前拒绝。
供应商返回有效 usage 时结算；未知用量、失败/超时/中断保留预留，服务重启不会恢复已用额度。
因此失败可能消耗应用预算，且剩余额度非零仍可能不足以覆盖一次长输入；可缩短输入或由配置者增加额度。
保存配置不会清零预算，不能把额度改到已用/预留以下。供应商报告超过预留则如实记账，之后停止新请求。
额度不是供应商账单或任意网关都遵守的计费硬上限；真实账单和供应商侧限制仍以账户平台为准。

## Verification

最终 Python 门禁：176 项，168 通过、8 跳过（Linux 维护专用，本次为 macOS）；49.089 秒。
命令：`PYTHONPATH=tests python -B -m unittest tests.test_ai_settings_demo tests.test_archloop_ai_providers tests.test_ai_lifecycle tests.test_ai_transport_boundaries tests.test_archloop_a_service tests.test_archloop_a_backend_b tests.test_archloop_a_http tests.test_archloop_d_adapter tests.test_archloop_d_fix_tasks tests.test_archloop_c_candidates tests.test_archloop_b_review_sessions tests.test_public_deployment tests.test_deployment_maintenance tests.test_workbench_import_ux tests.test_workbench_handover_download tests.test_deployment_backup -v`。
初次组合命令缺少备份测试历史使用的 PYTHONPATH=tests，模块导入失败；按现有测试路径约定重跑上述完整命令，最终无失败。
用户新增密钥隐私要求后的托管模式补测：设置/HTTP 模块 24 项全部通过（包含上述门禁已有的 22 项和新增 2 项），11.241 秒。systemd 实机运行与真实服务器配置未执行。
托管改动后的公开部署、既有模型协议与冷备复测：35 项全部通过，10.257 秒。
两份 DOM 检查：`NODE_PATH=<jsdom所在node_modules> node tests/check_ai_settings_ui.cjs` 与 `tests/check_workbench_flow_ui.cjs` 均通过；JS 语法和 diff 空白检查通过。

执行记录以本次实际最终门禁为准，见 PR 描述。新增设置测试覆盖配置立即生效、私有权限、Key 不回显、账号隔离、共享配置编辑权限、CSRF、域名撤销、无个人会话拒绝、存储故障不回退、并发预算、未知用量/重启、输出上限及无个人 Key 的老师真实工作进程调用。
冷备检查包含 AI 配置/预算恢复和 0600 权限。DOM 检查包含自动协议、地址预设、保存/测试、密钥清空、未保存输入保留、展示强制共享；既有操作流程 DOM 检查继续运行。
原生内置浏览器实际完成个人配置保存/测试、共享独立配置保存/测试、老师无 API 输入→保存想法→模型候选预览→共享额度结算。全部模型调用使用明确标识的本地合成供应商，不是千问真实生成。
初次原生生成发现测试夹具错误返回连接探测对象；结构校验如实拒绝，修正夹具后重试出现候选，未自动采用/发布。
交付预览已切换新的空白配置，停止合成供应商，保留测试证据；用户需自行输入真实 Key 和模型 ID。
补充原生复测：老师页配置入口可直接进入普通工作台的共享配置表单，API Key 输入为空，保存按钮可见。
上述配置表单复测属历史。最新 UI 按用户服务器托管要求改为共享状态页；平台模式不出现 Key 字段/保存按钮，个人模式仍可填写和保存。两份 DOM 回归与 JS 语法检查通过；原生界面结果与截图以本次 PR75 补充记录为准。
最新原生复测：实际刷新当前 AI 弹窗，标题为“AI 服务”，平台模式显示真实未配置状态、50000 共享额度、无 Key 表单和保存按钮；管理员配置说明折叠，个人 API 为可选入口。页面 error 日志为空，截图保留于本地测试证据目录。未读取用户密钥，未调用真实供应商。
以上绿色额度显示已按用户最新要求删除。连接检查新的真实 HTTP/认证用例及页面“成功/失败/无自动调用”回归以本次补充验收为准。
本次连接检查门禁：设置、公开部署、工作进程生命周期与输入边界合计 56 项全部通过（21.588 秒），两份 DOM 回归和 JS 语法检查通过。原生当前预览中绿色 token 栏已消失，按钮名为“检查 API 是否可用”；点击后仍如实显示未配置，未触发真实模型调用，页面 error 日志为空。

## Project Model Impact

**UPDATE（候选）**。增加 AI 私有配置、身份/共享配置编辑者授权与持久化预算责任，接口和代码映射需要正式 Model 后续记录。
依据为用户对两种 API 使用方式的明确指示、当前差异及本次实测；候选已列入 docs/deployment/MODEL_IMPACT_CANDIDATE.md。
权威项目综述仍未补齐；本次不修改/批准正式 Model，不把合成输出当作确认认知。

## Risks / Follow-up

真实千问调用、真实账单、云部署及不同网络的第二设备未验证；仍为 NOT_RUN。
本地个人会话到期后的旧配置文件仍留在私有目录，不会自动删除密钥。
公网服务当前是单进程团队部署，老师账号共享团队工作区权限，不是多租户隔离。
本轮仅更新 PR75 独立分支，保留 Draft，不合并 main；后续由队友审查。
