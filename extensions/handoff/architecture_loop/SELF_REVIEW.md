# D 成果复审 · 2026-10-07

这是同一开发者的代码复审，不是独立审计。复审起点为 GitHub PR #54 的 dc17d64a2a0757643a09f3896fe64aa722ad6bae；本机与远端一致、工作区干净。原两份 evidence manifest 共 33 个文件 SHA256 核对一致。旧 main、旧 integration 未变。

## 已复现并修复的 D 问题

| ID | 严重性 | 修复前实际结果 | 修复与回归 |
| --- | --- | --- | --- |
| D-R01 | HIGH | 请求 workspace-unrelated，provider 返回 workspace-fixture，接入器仍返回另一工作区的任务 | 请求 workspaceId 必须等于版本交接上下文的 workspaceId；否则 STALE_CONTEXT，任务不新增。 |
| D-R02 | HIGH | 独立分支先增加范围外 unapproved.py，后续删除并修 flow.py；最终 diff 仅 flow.py，旧检查接受并进入待验证 | 除最终差异外，检查基线之后交付历史每个提交（含 merge 各父比较）的路径；范围外变动即 SCOPE_MISMATCH，保持 in_progress，submittedRevision 为空。 |

两问题均使用真实临时 Git/SQLite 复现，修复前/后见 evidence/self-review/before-fix.json 和 after-fix.json。新增两项有效回归；D 分支全量 636 项 OK（14 skipped），对应原始日志 full-regression.log。D 专项 32 OK；与固定 A/B/C 共存 D 专项 32 OK。真实 D HTTP fixture 正常接手/修正/回挂/测试人确认继续通过，产品报告仍 INCOMPLETE，退出 2。实际 C 组件修正链继续通过，其原 4 项问题仍复现；不是正式项目人审或主页面集成。

## 对先前进度表述的修正

- 同版交接与规划包：有实际 B 导出、固定 Git blob、第二 clone 验证，是组件完成，不是用户已在主页面使用。
- 实施任务：状态、存储、固定版本和回挂已有实现与真实夹具证据；此前范围/工作区约束仍有上述两处遗漏，现已修复。不得以既有 30 个测试通过宣称边界完整。
- 日志整合：实现的是原日志固定版本只读引用与原接续任务关联，没有新增主页面日志选择/完整用户交互。
- B/C 对接：实际组件调用成立；C 当前图形状需要显式投影，实际 C 输出仍被 B canonical validator 拒绝。不能说共同契约或公共主线已接通。
- T01–T28 工具目前是结果/组件证据收集器。它实际执行 D 夹具，并对公共实例读取 /api/archloop 与 /api/ai-status；没有逐项执行全部 28 条产品故事，也没有可使完整产品自动 PASS 的路径。BLOCKED/NOT_RUN 是未执行结果，不是测试覆盖。A 公开 HTTP probe 和 C probe 分别提供具体额外检查，仍不能替代 UI 全主线。
- 826 项 OK（14 skipped）来自固定组合的全仓回归，其中多数为已有功能，不是 826 个新产品场景。原始结果有效，不能据此声称任务书最终完成条件满足。
- 缺真实浏览器截图/录屏、真实 AI、物理跨设备与独立审计。地图 UNKNOWN/AI 候选/日志未核实状态均未提升；仍未达到“主线关键项全部通过”。

## 当前结论

D 核心组件已实现并有实际验证，接入和验收交付仍属于候选。两处 D 缺陷已修复，不把全部剩余工作归因于 A/B/C：D 仍需在契约/公共后端就绪后补成逐项可执行主线验收、浏览器证据和新集成 SHA 复验。A/C 已报问题按 owner 处理，不能由 D 越界修改。

最新修复属于 MINOR（D 职责内校验，职责边界未变）；本轮原 UPDATE 模型候选继续等待人工确认。最终独立审计 AUDIT_PENDING。
