# NEXT TEAM DIVISION

依据修复后架构与原始角色映射（A = Core / Integration / Product Experience；B = Code Facts；C = Map Proposal；D = Continuity / Handoff / Worklog）。NOW 项只含剩余合并/就绪缺陷与人类决定；NEXT FEATURE CYCLE 只含有真实工作支撑的接缝；LATER 待产品需求出现再做。

## A — Core / Integration / UI

Own:
- ExtensionHost 与共享运行时
- Core compare/map 接口
- 集成 BCD 运行时（含 A30）
- 统一 UI shell（三区导航）
- 跨扩展故障隔离
- 公共 API 组合

NOW:
- 审阅/合并 readiness：A30 修复分支、BCD audit-fixes 分支、UI 修复分支的 PR（全部未合并 main）
- HOST-01（LOW，deferred）：加载期 GeneratorExit/KeyboardInterrupt 隔离语义设计（不得盲目捕获 BaseException，保留操作员中断）

NEXT FEATURE CYCLE:
- UI 证据源语义扩展（新提案/证据类型的专用渲染）
- 扩展生命周期可观测性
- 新扩展免路由硬编码（既有 GOOD SEAM 维持）

不接管 B/C/D 领域逻辑。

## B — Code Facts

Own:
- 客观代码事实、parsers/collectors
- revision 绑定事实
- skipped/资源预算语义

NOW:
- 无阻塞项（B 分支未改动，维持 PASS_WITH_LIMITS）

NEXT FEATURE CYCLE:
- 语言 dispatcher seam（首个真实需求：TypeScript collector）
- B 页面 schema 校验开放（当前封闭 python + 五种 kind）
- per-file Git 子进程缓存（仅当规模需求出现）

不实现 Map Proposal 逻辑。

## C — Map Proposal

Own:
- 架构推断、证据域推理
- 提案 kinds、关系分析器
- CA 消费策略、人工审查边界

NOW:
- 终审后按 verdict 处理任何新 finding
- C→D 结构化提案引用契约（C_D_REFERENCE_CONTRACT_PROPOSAL.md 起草，标注 PROPOSED / HUMAN REVIEW REQUIRED——不阻塞其他修复）

NEXT FEATURE CYCLE:
- 语言分析器 seam（随 B 的 TypeScript collector）
- 新提案 kind（如 API_CONTRACT_CHANGE）——既有 GOOD SEAM
- 完整 T2 真实消费链（当前证据不足，需 CA 侧 live verifier 支持）
- src-layout 正式解析器（C-06 目前是可见 UNKNOWN 降级，不是解析实现）

不做 B parser、不当正式地图写入者。

## D — Continuity / Handoff / Worklog

Own:
- continuity / handoff / worklog / 历史 / 协作状态
- 提案引用（未来）

NOW:
- 无阻塞项（D-01/02/03 已修）

NEXT FEATURE CYCLE:
- 干净存储抽象收尾（repository_storage_folder 已是无副作用 context；后续评估是否提取共享 module）
- C proposal-reference 消费（等 C 契约草案）
- schema 版本演进与迁移

不把 C 提案当架构真相。

## LATER（明确推迟）

- parser 缓存、通用存储适配、导出格式扩展
- 性能与全树扫描优化（B 全树扫描为已记录限制）
- 域建模 glossary（CONTEXT.md）——待产品概念收敛后由 grill/domain-modeling 流程引入
