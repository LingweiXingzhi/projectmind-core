# 第二阶段交付：任务治理与工作台

## Result

已完成真实部署服务→A 工作区→不可变 B 图版本→D 持久化任务的接续，以及 UI #56 的三方集成。
任务支持创建、接手、实施、回挂、受控验证预览/确认和下载。未配置真实验证器时保持待验证。
本地生产 HTTP、Caddy TLS 和冷恢复已通过；尚未上线公网。

依赖第一阶段 PR #61。固定运行源码：本地 453553face25ae045c80e941e33e68bcff875ca2，
对应远端 951b59c5d67dfcacc0211eb2568325d7e9a2756e，完整树均为
89c2194215e3ec8c67c5fb8e4c920df238d19995。GitHub 常规连接上传了校验过的对象；本机 Git CLI 未认证，不能表述为完整上游历史 clone。
最终交付的后续提交仅加入本文件和本轮验证摘要，不改变运行源码。

## Files Changed

- archloop/backend_d.py、service.py、app.py、deployment/server.py：真实版本/来源绑定与公开任务路由。
- extensions/continuity/fix_gateway.py、fix_tasks.py：HTTPS 账户/浏览器绑定、容量/到期/并发保护、导入身份来源。
- web/ 与相关扩展 HTML：固定 UI 候选接续、真实账户/仓库控件、三步复核、治理任务面板。
- archloop/context_pack.py：字段名或值中包含 TODO/xxx 不再绕过凭据检测。
- tests/ 与 verification/：边界、真实 HTTP、DOM、TLS 与恢复；详见 PHASE2_PROTOCOL.md。

## Verification

固定运行树上实际执行：

| 验证 | 结果 |
|---|---|
| `python -m unittest discover -s tests -v` | 979 项 / 253.844 秒，956 通过、23 既有条件跳过，退出 0 |
| 11 个工作台/认证 JS `node --check` | 通过 |
| `node verification/test_governed_tasks_dom.cjs <jsdom>` | 4 项控件检查通过，fetch/对话框替身 |
| `python verification/rehearse_public_dom.py --node <node> --jsdom <jsdom> --output <新私有目录>` | 10 个真实脚本、49 个生产 HTTP 请求，脚本错误 0 |
| `python verification/rehearse_public_https.py --caddy <已校验Caddy> --output <新私有目录>` | Waitress CLI + Caddy 2.11.7；30 请求，证书链/域名真实验证 |
| 停机冷备恢复 | A 两工作区、B documents、架构 Git HEAD、D 一任务一致；SQLite integrity_check=ok；浏览器/D 会话均未恢复 |

HTTP/DOM/TLS 使用隔离的合成 Git 项目、测试账号和模拟人工决定。断言代码 Git 未变化。
另有测试专用真实 subprocess 验证器演练，标明 fixtureOnly，不等于配置了真实团队项目验证器。
初次整页演练发现新任务脚本 404，补上静态路由后重跑通过；预先的夹具端点/范围问题也已修正，未把失败运行列为成功。
机密与完整原始日志保留在私有外部目录；可审查摘要在 verification/phase2/。

DOM 使用 jsdom 30.1.2 与 Node 24.19.0，真实 fetch 到生产服务；HTTP 段只模拟代理 Host/Origin。
真实 TLS 由独立 Caddy 演练覆盖。原生 Chromium 被 macOS MachPort 限制，浏览器/布局验收仍为 NOT_RUN。

## Project Model Impact

UPDATE。依据：固定 D/UI 来源、用户整项目部署准备授权、实际代码差异与以上证据。
建议记录共享任务治理、私有存储和浏览器身份边界；不是批准具体项目认知。
正式 Model 未修改；权威项目综述仍未在 model 仓库找到。

## Risks / Follow-up

- 无云服务器/域名，真实公网、第二设备、Linux systemd/证书续期尚未运行。
- 未配置真实模型/任务验证器；相关能力清楚显示未完成。
- 原生浏览器验收未完成。旧工作日志/决策扩展仍依赖旧地图，下一阶段按真实工作区迁移。
- 全部成果作为独立 Draft PR；main、第一阶段/原 B 分支、正式 Model 均不由本轮合并。
