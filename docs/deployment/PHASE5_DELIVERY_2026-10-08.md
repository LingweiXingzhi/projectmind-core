# 第五阶段交付：C 与模型协议接续

## Result

对照最新未合并整合 #60 固定 ad119865a82f2faad0ebc8bdd47475e43c93a6e8，接回 C 的真实登记、同仓库同版本追踪对照和两种服务端模型协议。
补齐传输边界/私有诊断值保护；保留部署账户、D 私有任务、共享记录、三步人工复核与源上下文秘密过滤。
只局部复用经核验文件，未完整复制 #60/#63，未引用其历史截图/验收作为本轮证据。

## Files Changed

archloop/backend_c.py、service.py、deployment/server.py：四类 C 调用经真实登记 dispatcher，投影代码身份并保留拒绝/覆盖理由。
extensions/map_proposal/candidates.py：有身份与完整覆盖才在声明观察范围内给出一致/偏差；格式/数量有边界。
archloop/ai_transport.py、generate.py：Responses/Chat服务端配置、schema、HTTPS/本机HTTP、禁止重定向、大小/JSON/诊断边界。
三套新增验证与复用 C 测试；生成测试适配到真实部署账号，协议见 PROVIDER_AND_C.md。

## Verification

固定运行本地 9c2b3840b0ef039b686c043bb6e83b37736865c9，对应远端
6a62766e97c0a972f01c4249a108a708803617a3，同树 4dbdc00ea7146270527d305ec1b414aead0dda3d。
最终后续交付提交只加入本文件与本轮摘要。

- 完整回归 1008 项 / 261.003 秒：985 通过、23 既有条件跳过，退出 0。
- 全量包含本机 Responses/Chat 协议夹具、真实部署登录后的生成接口、schema/JSON拒绝、重定向不联系目标、大小/端点/密钥诊断边界，以及真实 C HTTP 身份/覆盖与规划 UNKNOWN。
- Waitress CLI+Caddy真实本地TLS 40 请求；证书/域名、任务/记录、人审/跨会话拒绝继续通过；A/B/D/工作记录/历史及架构Git停机冷恢复一致。
- 整页 11 真实脚本 / 117 生产HTTP请求 / 0脚本错误，记录与任务行为继续通过。源代码Git未被夹具写入改动。
- 证据在 verification/phase5/。本机协议服务使用合成密钥与预写 JSON，不是实际模型生成或目标厂商联通证明。

首次上游生成测试缺少其本地 session helper，改为本部署真实账户 HTTP；首次传输边界检测发现非有限值嵌在 JSON 字符串中绕过前置检查，已加严格输入序列化后重验。
自检另外控制深层坏 JSON、关闭 HTTPError 响应、避免公开完整端点路径/未知响应字段名。固定提交全量包含这些修复。
原生浏览器/布局、公网/第二设备、真实模型/任务验证器仍未验证。

## Project Model Impact

UPDATE 候选。依据固定来源差异、用户整项目授权与实际测试。
观察是参与者声明对照，模型输出是候选，不赋予运行验证/认知批准权。正式 Model 未修改，权威综述仍缺。

## Risks / Follow-up

模型 HTTP timeout 仍是 I/O 超时，整体墙钟截止与完整停止/重试治理需继续完善。
后续对照中文 UI #63，核对与当前部署交互的兼容性；最新整合本地控制器的其他差异仍单独接续。
当前云资源/真实模型配置/原生浏览器等条件不齐，不把本地通过表述为已部署公网。
依赖 PR #65 的独立 Draft PR，不合并 main 或正式 Model。
