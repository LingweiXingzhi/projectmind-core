# #71 整合版本独立复审与修复（2026-10-08）

## Result

固定来源：PR71 `2689f5c19cd7bf2265d4bb3c02c85070d08abcf4`，完整源树 465 个 blob 全部核对。当前原 PR71 是 Draft/open；PR 描述的作者验收不作为本轮验证证据。本轮在新的独立修复分支开发，保留作者的合并历史、双 D adapter、接口和本地入口写会话。未覆盖原 PR71、未合 main、未发布正式 Project Model。

复现与修复：

| 问题 | 修复与实际检查 |
| --- | --- |
| 公网账户登录/CSRF 通过后，仍被本地演示会话拒绝，工作区创建返回 FORBIDDEN_SESSION | 仅 public 模式使用 WSGI 注入的真实会话；本地仍要求自己的 Cookie/令牌。真实 Waitress 登录、写入、人审、C/D 与记录测试通过；伪造身份、缺 CSRF、跨会话确认/发布仍拒绝。 |
| 合并丢失设计复核选择；代码静态证据复核自动覆盖期望过程 | 恢复“核查代码证据/确认设计与期望过程”选择；公开静态证据的默认覆盖不推导过程行为。设计确认可显式覆盖过程，才能创建对应治理任务。保留本地 D 的既有行为。 |
| sha256: 修订的编码详情链接返回 404 | 仅解码版本标识，真实发布后检查编码/原始路由及另一浏览器读同版。 |
| 公共深 JSON 500、本地 NaN/深层额外字段被接受并写入 | 业务前拒绝非有限数及超过 64 层嵌套，包括 1e9999；原始 HTTP 回归确认 400 且没有工作区修改。 |
| 模型慢响应、排队和重试可超过整体预算 | 一次总预算、最多四个临时工作者、受信任服务端取消、终止与回收；真实本地慢响应/重试/并发测试，保留大小、schema、协议和隐私边界。 |
| 治理任务表单标签挤在一起，小屏搜索与账户操作挤压 | 保留字段/按钮/枚举，仅恢复表单布局、可读标签及窄屏头部。原生 Chromium 实际填写、下载、两个浏览器上下文与 430px 截图验证。 |
| 测试依赖固定 Windows 路径或不存在的父提交 | 默认使用当前仓库的真实 B/CA 模块，可显式指定外部实现；仅在有首父历史时做版本比较，不虚构上游历史。修正 /tmp 路径别名期望。 |

## Files Changed

`app.py`、`deployment/wsgi.py`、`archloop/backend_b.py`、共享模型传输和内部工作者、架构/任务页面、样式及相关测试/验证脚本。PR71 的 `archloop/acceptance.py` 原作者实现未替换。PR70 的主机安装模块不在 PR71 来源中，安装修复另行交付。

## Verification

最终完整回归：1061 项，1059 通过 / 2 跳过，0 failure / 0 error（309.335 秒）。

基线：1051 项，18 failure、1 error、24 skip。17 项 failure 来自 public 会话接线；其余是临时路径别名和单提交快照的父提交假定。最终固定提交、完整回归数量/耗时、跳过理由与日志 SHA256 见 `verification/review71-20261008.json`。

- 真正 Waitress CLI + Caddy、本地 CA/主机名验证，40 个 HTTPS 请求；错误 CSRF/Origin、跨浏览器确认/发布均 403，CAS 冲突 409。既有/规划两个工作区发布，不为规划伪造代码 SHA。
- 服务停止后冷恢复：A 工作区、B 文档、D 任务、工作记录/历史、架构 Git HEAD 一致；SQLite integrity=ok；会话不恢复。
- 11 个原始脚本在完整 DOM 中运行，124 次真实 HTTP 请求，零脚本错误；工作记录 CAS 冲突保留输入，AI 决策维持候选。
- 原生 Chromium，102 次请求，零 pageerror；实际 HTML dialog、真实登录 Cookie、两浏览器绑定、治理任务接手/实施中、原生文件下载与服务端 JSON 全等、编码版本路由。430px 窄屏无横向溢出，表单字段及账户操作可完整显示。
- 浏览器仅对隔离 .invalid 私有 CA 夹具使用证书例外；独立 Python 客户端真实验证 CA/主机名。没有安装系统信任根或修改系统代理。两个上下文不等于真实第二物理设备。

复现：

```sh
python3 -m pip install -r deployment/requirements.txt
# 将已核验的 node/caddy 加入 PATH；dev harness 使用显式 jsdom/Playwright 模块。
python3 -m unittest discover -s tests -v
python3 verification/rehearse_public_https.py --caddy "$CADDY" --output "$NEW_PRIVATE_OUTPUT"
python3 verification/rehearse_public_dom.py --node "$NODE" --jsdom "$JSDOM_MODULE" --output "$OTHER_NEW_PRIVATE_OUTPUT"
python3 verification/rehearse_public_browser.py --node "$NODE" --playwright "$PLAYWRIGHT_MODULE" --caddy "$CADDY" --browser-cache "$BROWSER_CACHE" --output "$BROWSER_PRIVATE_OUTPUT"
```

验证输出必须在 Git 外的新私有目录。真实模型密钥未使用，测试只有合成提供商/临时仓库/夹具人审。原始日志和截图在本地，上传的是脱敏摘要。最后的文档提交不修改功能代码；TLS/浏览器来源与全量来源的差异仅测试文件，摘要逐项记录。

## Project Model Impact

MINOR。

依据：`AGENTS.md`、`docs/standards/AGENT_STANDARD.md`、既有 public 真实身份/CSRF、人审覆盖与 B/C/D 边界，以及当前源码。修复整合接线、内部传输和展示，不把静态证据或 AI 候选升级为确认认知，不修改正式 Model。Model 仓库 main 仅起始 README，候选综述不能作为正式批准来源。

## Risks / Follow-up

本地是精确完整源树与自己的修复历史，没有经正常认证 Git CLI 克隆完整上游历史；GitHub 上传以原 PR71 的真实提交作父提交，保留其原始 ancestry。历史 smoke 只证明当前可用的比较，不证明完整上游历史。

真实公网/域名/DNS/公开证书、第二实体设备、真实模型语义、实际队友人审与真实项目任务验证器仍 NOT_RUN。服务器取消只是内部能力，没有浏览器取消操作。独立人审/正式 Model 发布需团队确认。本分支保持 Draft；main 与原 PR71 不变，不能把测试通过或 MERGEABLE 当作合并授权。
