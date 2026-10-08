# 第三阶段：部署中的共享工作记录

## Result / 工作计划

当前整合项目的工作日志、决策视图仍依赖 legacy map 与代码 .git 内的本机存储。
本候选依赖部署 PR #61 和治理/UI PR #62，在独立工作树里复用已有 worklog Store 的文本与历史能力，
接入真实 A 工作区、登录身份和外部私有数据库，使 Overview / Worklog / Decisions 可以共享记录。
验收：真实 HTTP 身份、工作区/版本绑定、CAS 冲突、原始历史、规划空代码 SHA、持久化/恢复、页面操作和全量回归。

## Files Changed / 公共接口

archloop/work_records.py 实现受保护工作区记录服务；service/app/server 接续。
已有 Store.save 增加仅由服务器调用传入的可选 server_fields，旧扩展 JSON 路由不接收它；旧本地行为保留。
web/work-records.js 提供查看、分类、保存、编辑、历史和 JSON 下载；view.js 的首页聚合改用真实共享记录。

| 路径 | 方法 | 内容 |
|---|---|---|
| /api/archloop/records | GET | 团队实例聚合记录，前 200 条，包含 total/truncated |
| /api/archloop/workspaces/{id}/records | GET | 该工作区记录，前 200 条 |
| 同上 | POST | 文本记录保存；新建/编辑均校验 expectedMapRevision / expectedDraftRevision |
| .../records/{recordId}/history | GET | 原始历史，最新 100 版，含 total/truncated |
| .../records/export | GET | 当前工作区当前记录 JSON，最多 2 MiB；全部历史用私有数据库冷备 |

保存字段：category（daily/decision/goal/issue）、date（YYYY-MM-DD）、title（≤200字符）、body（≤15000字符）、origin（human/ai）。
编辑同时提供 id、expectedVersion，布尔值不充当整数 CAS。actor/author 不赋予身份；实际作者只取真实登录上下文。
页面冲突后保留输入；重新载入最新记录前需保存自己的文本。后台工作区切换不丢弃未保存表单。
固定旧图/草稿的记录请求不会被自动绑定到新版本。

## 身份、认知与存储

这是同一团队实例，全体登记账号可读写团队工作区，尚无细粒度角色权限。
每版记录包括 workspaceId、binding（代码/图/草稿/阶段身份）、authorIdentity 和 createdBy；编辑不会丢失原始版本。
human → participant_claim / contributor_record，ai → ai_candidate。decision 分类不产生正式认知、人审批准或真实运行事实。
规划工作区允许代码 SHA 为 null；样例阶段标为 sample，不冒充发布版本。
数据在 dataRoot/work-records/records.sqlite3，目录 0700、数据库 0600；一起停机冷备并校验 entries 与 history。
每实例最多 1000 条记录、5000 个历史版本；容量已满在写入前拒绝，不擅自删除数据。

## Verification / Risks / Follow-up

本轮精确固定提交的实际验证结果在第三阶段交付记录中列明，不沿用上一阶段的次数当作本轮验证。
首次 HTTP 运行暴露通用认证入口注入 actor 与严格字段白名单不匹配；保留服务器身份注入并接纳/忽略该字段后重验。
文件原件导入/旧记录迁移尚未接通，界面明确告知；没有在公网打开 Word 转换器或假造 legacy map。
原生浏览器、真实公网/第二设备、真实模型/验证器和权威项目综述仍待完成。

## Project Model Impact

UPDATE 候选：部署实例使用真实工作区身份保存共享参与者记录，分类本身没有模型批准权。
依据用户整项目推进授权、已有工作记录模块、实际代码与验证。正式 Model 未修改、未批准。
