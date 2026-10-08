# #70 全项目复审修复交付（2026-10-08）

## Result

来源固定为 PR70 `f3698745f9d96851cf52c3e410b6600caf5d53a6`。从完整来源树建立独立修复分支；没有覆盖原 PR70、PR71 或 main。源码快照与来源树完全一致，但本地并非正常认证克隆的完整上游历史。上传以真实来源提交作为父提交。

已复现并修复：

- 安装器在 umask 077 下留下 root 所有的 0700/0600 发布文件，服务组无法读取。发布树按目录/可执行文件 0750、普通文件 0640 配置；凭据与状态仍按自己的私有规则处理。先检查符号链接、特殊文件和硬链接，避免修改外部对象。
- 模型套接字超时不能限制慢速响应、队列和 HTTP400 重试的总时间。调用采用一个总预算、最多 4 个临时工作者、受信任的服务端取消 Event，超时/取消终止实际网络进程并回收。请求大小在启动前验证，协议/schema/store=false 等约定保留。没有增加浏览器取消按钮。
- 编码的历史版本修订 URL 无法读取详情。只解码版本标识段，保留后续验证。
- 深层或非有限 JSON 可绕过输入规则；本地和公开入口均在业务写入前拒绝，包含指数溢出产生的无穷数。
- 验收程序缺少 HTTPS 登录、服务器仓库别名、真实治理任务流程，使用计数相等代替独立 HEAD 检查等。加入证书/主机名验证、真实会话/CSRF、明确的可写夹具同意、独立 Git HEAD 比对和真实 handoff 校验；真实 AI/人审/任务核验仍诚实记录 NOT_RUN，不自动关闭任务。
- 测试默认依赖队友 Windows 路径和假定 HEAD~5。使用当前仓库的真实组件、可用首父历史及保留外部路径覆盖；Linux 维护测试在 macOS 明确跳过，不伪装 systemd 验收。

## Files Changed

关键文件：`deployment/host.py`、安装脚本、`app.py`、`deployment/wsgi.py`、`archloop/ai_transport.py`、新内部 `ai_worker.py`、`archloop/acceptance.py`、`acceptance_http.py` 及相关测试。未改正式 Project Model。

## Verification

最终完整回归：1057 项，1048 通过 / 9 跳过，0 failure / 0 error（319.301 秒）。

最终固定源码、测试数量、实际执行耗时和日志摘要见同目录 `verification/review70-20261008.json`。基线 1037 项，6 failure、3 error、23 skip；该机器上的安装路径别名和 Linux 命令条件分别记录，不能当成功能通过。

真实运行包括：Waitress CLI + Caddy 私有 CA 证书/主机名验证、40 次 HTTPS 请求、会话/CSRF/跨浏览器确认及发布隔离、CAS、治理任务与共享记录、停机后冷恢复。完整 DOM 运行 11 个源脚本、119 次真实 HTTP 请求、零脚本错误；DOM 的对话框等有 polyfill，不是浏览器验收。本分支未运行原生浏览器；PR71 的浏览器结果不归到本分支。

生产验收夹具 31 PASS / 5 NOT_RUN；实际任务实施回挂停在 verification_pending，没有虚构任务已核验。原生 handoff 的本地完整性通过，不代表第二副本的 Git 导入通过。

复现：

```sh
python3 -m pip install -r deployment/requirements.txt
# 将已核验的 node 与 caddy 可执行文件加入 PATH。
python3 -m unittest discover -s tests -v
python3 verification/rehearse_public_https.py --caddy "$CADDY" --output "$NEW_PRIVATE_OUTPUT"
python3 verification/rehearse_public_dom.py --node "$NODE" --jsdom "$JSDOM_MODULE" --output "$OTHER_NEW_PRIVATE_OUTPUT"
```

运行输出目录必须是 Git 树外的新私有目录。未将密码、Cookie、私有状态、账户文件或本机绝对路径上传；原始日志留在本地，仓库仅保存脱敏摘要和校验值。最终提交只附加交付文档和摘要，功能源码与实际验证来源一致（详见摘要中的关联）。

## Project Model Impact

MINOR。

依据：`AGENTS.md` 的“Code provides implementation facts / AI proposes / Humans confirm”，`docs/standards/AGENT_STANDARD.md` 的内部实现变化分类，以及既有部署/传输/人审职责。内部工作者、权限与验收接线没有改变模块责任；不更新正式 Model。Model 仓库 main 只有起始 README，候选综述不能当作获批准的正式模型。

## Risks / Follow-up

公网主机、域名、DNS、公开 CA、真实不同设备、真实模型、队友人审、真实项目验证器、Linux systemd 与不同服务 UID 的实际启动仍 NOT_RUN。本地发布组权限检查不等于已在 Linux 主机成功启动。上游完整历史没有通过 Git CLI 验证。

PR71 未包含 PR70 的安装准备模块；两份后续修复保持独立。团队整合时需选择共同模型/输入修复，避免重复覆盖，另外接入安装权限和验收改动。保持 Draft，须人工审阅与明确合并指令，不自动 merge。
