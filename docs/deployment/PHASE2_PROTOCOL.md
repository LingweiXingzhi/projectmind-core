# 第二阶段：共享工作台与治理任务

## Result / 依据

本候选依赖第一阶段 Draft PR #61 的账号、来源校验、B 版本与私有存储。
采用 D #54 固定提交 c8b942a8d724b1bd0509f61b2db6ec642a117181 的 23 个已核验文件作为组件起点。
页面采用 UI #56 固定 2ef017917feb0308f2c477610630ab72d6b7a3e3，真实共同基线为
b75ad820e0d31e3dadf842b414f6950b5aa46102。运行文件三方接续；未复制旧截图或历史测试为本轮证据。
治理入口、身份适配、边界修复和页面任务面板为本轮实现；不是声称上游 PR 已获合并批准。

## 工作过程

1. 登记真实代码仓库，创建 existing_project 工作区；无代码 planning 可以发布设计，不能创建代码修复任务。
2. 使用明确标注的规则候选或已配置的 AI。应用草稿并保存期望过程。
3. 选择复核范围：代码静态事实不会自动覆盖期望过程；设计与期望过程不表示程序已经按此执行。
4. 复核预览、同一浏览器人工确认、发布不可变架构 Git 版本。草稿改变后必须重新复核发布。
5. 任务提示只列已纳入人工复核覆盖范围的过程/步骤。填写实际观察声明、允许改动路径和验收要求。
6. 接手→实施→回挂真实独立分支提交。服务器检查 SHA、代码来源、范围和提交历史，进入待验证。
7. 请求配置的服务器验证器产生预览，再由同一登录浏览器核查确认。默认未配置真实验证器，明确拒绝此步骤；不能用客户端命令或 human_confirmed 字段关闭偏差。

## 公共接口

路径均以 `/api/archloop/workspaces/{workspaceId}` 为前缀，受第一阶段会话/CSRF 保护。

| 路径 | 方法 | 行为 |
|---|---|---|
| /fix-task-hints | GET | 固定版本身份、可用过程、创建/验证能力 |
| /fix-tasks | POST | expectedMapRevision、expectedDraftRevision、expectedProcessRef、deviation、scope、evidence、acceptance |
| /fix-tasks | GET | 本工作区任务；不返回内部 versionHandoff 或服务器源路径 |
| /fix-tasks/{id}/markdown | GET | 任务说明下载 |
| /fix-tasks/{id}/governance | POST | transition、submit、verification_preview、confirm_verification |
| /handover | GET | 原生 architecture_handoff_v1；必须具有可传递的 Git origin |

除预览外的治理写入带 expectedRevision 和 expectedMapRevision；冲突拒绝，不覆盖别人进展。
actor 字段不授予身份，实际 actor 来自服务器登录。公网内部 D 会话与验证令牌绑定该浏览器，重启/到期不恢复授权。
验证预览/确认数量有上限；容量不足在运行验证器前拒绝。验证令牌只在浏览器内存短期保留。

## 数据与来源

- A 工作区 ID 与 B 内部工作区 ID 可以不同，使用已保存的真实绑定，不假设字符串相等。
- handoff 保持不可变 B version envelope，并标明当前 A workspaceId。代码仓库 ID/SHA、图版本必须一致。
- D 数据在 dataRoot/d/continuity.sqlite3，目录 0700、数据库 0600。停机后与 A/B 和架构 Git 一起冷备。
- 原始创建者是 authenticated_account。导入任务原始作者标为 imported_participant_claim，接收者单列 receivedBy/receivedByIdentity，不改写声明为可信身份。
- 本机 source locator 仅在服务器内部使用；无可传递 origin 的导出返回能力不可用，不泄露绝对路径。
- 模型上下文秘密检测按字段和值独立判断；字段名或真实值里包含 TODO/xxx 不能绕过检测。

## Verification / Risks / Follow-up

精确已提交版本的完整测试、真实本地 Caddy TLS、D 冷恢复和整页 DOM/真实 HTTP 证据在第二阶段交付记录中报告。
夹具观察/确认仅验证机制；不是本团队正式认知批准，也不证明真实目标项目行为。
jsdom 使用对话框/滚动等替身，不能证明原生浏览器布局与交互。云部署、第二设备、真实模型/验证器、原生浏览器和完整上游 Git 历史仍待完成。
工作记录/决策旧扩展在无旧地图的公网入口仍不可用；须继续按真实工作区和私有存储迁移。

## Project Model Impact

UPDATE：新增部署服务到真实任务治理与工作台的接续，证据为上述固定来源和本候选代码差异。
只提交模型变更建议；权威项目综述缺失，正式 Model 未修改、未批准。
