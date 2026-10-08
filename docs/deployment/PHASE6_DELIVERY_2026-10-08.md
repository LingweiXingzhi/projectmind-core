# 第六阶段交付：中文界面与交接包显示

## Result

核验中文 UI #63 的基线/head 26 个 blob，并将13文件显示变化接入已验证部署树。
保留账户/仓库选择、人工三步复核、治理任务和共享记录；枚举显示中文，机器值/未知标识/源码/导出保持原文。
发现原生 D handoff 的图身份位于 versionEnvelope，修复旧显示读取造成的 undefined 文件名/说明，导出 JSON 不改写。

## Files Changed

web/ 与四个扩展 HTML；governed-tasks.js 显示中文状态并保留原始状态属性；verification 演练增加实际交接包捕获。
基于 PR #66；未合并 #63/main，没复制旧截图或历史报告。
10处三方冲突逐项读取：保留当前账户/真实任务/复核控制和 HTTPS 网络状态，接回相应中文标题/状态；没有引入上游本地声明任务控制器。

## Verification

固定 local edd555c26a224e2e07f245b3246d9ab68a1b1068 = remote
7728eb98a19b645e7be99c4b23e8d77584444352，同树 a8f17fbae0eba736d4b3c32cbe86ecac6981508a。

- 12 JS语法通过；6 HTML控制标识/值/路由属性保持一致，仅两页增加既有标签辅助脚本。
- 真实部署相关30项 / 11.776秒全部通过；任务控件DOM4项通过。
- 整页11真实脚本 / 119生产HTTP请求 / 0脚本错误，中文/未知标识、任务/记录/复核继续通过。
- Blob下载捕获的原生 handoff 与服务器另次读取逐字段一致，文件名/显示不含 undefined，机器状态仍为 confirmed_cognition。
- 首次新增断言误将已有项目版本当作 planning 的 confirmed_design，核对公共契约后修正夹具断言并重跑；没有改服务器状态迁就测试。
- 去掉源候选额外空行并执行 diff检查。源码Git未被演练写入改动。

本阶段仅界面/演练变动，没有重跑全量或TLS；前阶段1008项和TLS40仅为基线。
jsdom包含对话框/滚动/Blob URL与下载捕获替身；原生浏览器视觉、真实下载与小屏布局仍NOT_RUN。
证据见 verification/phase6/，复现命令沿用 verification/rehearse_public_dom.py。

## Project Model Impact

NONE：显示与既有原生包读取适配，不变更责任、协议、存储或批准判断。正式 Model未改。

## Risks / Follow-up

最新整合 #60 的其他本地控制器差异、模型整体墙钟截止/停止重试仍需继续接续。
公网资源、原生浏览器、真实模型/任务验证器与权威综述仍缺；不将本地/DOM成功当作真实公网完成。
本候选为独立Draft，不合 main。
