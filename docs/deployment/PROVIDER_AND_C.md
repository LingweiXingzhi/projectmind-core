# 真实 C 登记与模型端点配置

## Result / 来源

从最新未合并整合 #60 固定 ad119865a82f2faad0ebc8bdd47475e43c93a6e8 复用 C dispatcher / 过程追踪身份校验、模型协议适配与相关测试。
源码先按 Git blob SHA 校验；部署接续和传输边界在此候选另行修改并重验。
本轮没有直接复制全部 #60，也没有用其本地声明会话替换公网账户。D 权威存储、共享记录、登录、人审三步和秘密上下文过滤继续保留。

## C 调用与证据

部署服务显式登记 correction=extension:map_proposal，规则候选/纠正/增量/偏差都通过同一个可调用 dispatcher。
过程追踪投影包含真实工作区 codeRepoId/codeRevision。不同仓库/版本、缺少身份、格式无效或没有覆盖步骤的轨迹不能报告 ALIGNED。
拒绝原因、覆盖节点与不完整证据保留在响应；最多 200 条轨迹、每条最多 200 步。
匹配身份的输入仍是参与者提供的观察声明；规则对照的 ALIGNED 仅在覆盖范围内成立，不等于服务器真实运行验证或正式认知批准。
规划图没有代码身份，追踪结论保持 UNKNOWN。

## 模型配置（服务端）

2026-10-08 最新接续：标准本地/公网启动已支持页面保存个人 API 或运行者共享 API。
私有配置覆盖对应初始环境配置，个人配置永不继承共享 Key；每次模型请求绑定同一配置与独立额度。
公网个人端点须为登记的 HTTPS 域名，共享设置仅指定账号能编辑。
详见 [AI 接入交付](../user-flow/AI_ACCESS_DELIVERY_2026-10-08.md)。下面的环境变量仍是共享配置的初始来源。

| 环境变量 | 内容 |
|---|---|
| PROJECTMIND_AI_API_KEY 或 OPENAI_API_KEY | 服务端密钥，不写进 Git、请求 JSON 或浏览器 |
| PROJECTMIND_AI_MODEL | 该端点提供的模型标识 |
| PROJECTMIND_AI_BASE_URL | API 基地址，默认 https://api.openai.com/v1 |
| PROJECTMIND_AI_PROTOCOL | auto / responses / chat_completions |

auto 对 api.openai.com 选择 responses，其他主机选择 chat_completions；也可明确指定协议。
请求形状以 [OpenAI API reference](https://developers.openai.com/api/reference/resources/chat) 的 Chat Completions 为兼容依据；Responses 使用 [text.format JSON schema 接口](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)。
协议兼容不证明任意厂商/模型都支持所有字段，必须以目标端点实际验证为准。
模型内容经过项目 schema 与后续图/操作校验，候选需人工应用、复核和发布。

远程端点只接受 HTTPS；HTTP 仅允许 localhost/回环 IP 的明确本机服务。
端点不接受 URL 内凭据、查询/片段、无效端口。普通生成请求不能携带临时模型/端点，必须先经受保护配置入口保存；服务器拒绝重定向以免传递密钥/源上下文。
请求至多 1 MiB，响应至多 2 MiB；非有限 JSON 值、格式错误、schema 不符和传输异常控制失败。
公开状态只显示模型、提供方主机和协议；完整端点路径与响应中的未知字段名不回显。
Chat 端点明确返回 HTTP 400 时允许一次去掉 response_format 的兼容重试，输出仍执行本地 schema 检查。
当前接续已通过独立网络工作进程施加整体墙钟截止，取消/超时会终止并回收工作进程；两次兼容尝试共用同一截止。
默认共享总额度 50000、单次输出 2048；调用前保守预留，可信 usage 结算，未知/失败保留预留。
这是应用侧预算，不是供应商货币账单或所有网关都遵守的绝对计费上限。

## Verification / Files Changed

archloop/backend_c.py、service.py、deployment/server.py：真实登记、投影身份、拒绝原因。
extensions/map_proposal/candidates.py：同版过程证据与输入边界。
archloop/ai_transport.py、generate.py：服务端协议配置、schema 和传输边界。
复用的真实生成测试适配到部署账号 HTTP，没有引入 #60 的本地声明 session helper。
实际固定提交的回归/TLS/DOM结果另见阶段交付记录；本机协议夹具不代表真实模型调用成功。

## Project Model Impact

UPDATE 候选：真实引擎登记与模型传输能力接续。依据固定源差异、用户整项目授权和实际验证；正式 Model 未修改/批准。

## Risks / Follow-up

未配置真实模型账号，真实 AI 仍 NOT_RUN；D 真实验证器也未配置。
新整合的本地控制器与中文 UI 仍需兼容核对；不宣称当前部署树等于完整 #60/#63。
云资源、原生浏览器、第二设备与权威项目综述仍有外部条件缺口。
