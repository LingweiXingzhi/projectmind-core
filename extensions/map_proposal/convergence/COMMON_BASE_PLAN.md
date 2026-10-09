# C Convergence — Common Base Plan & Dependency Registration (W0)

## 1. Common Base

获批 common base 尚未由 A/Core owner 正式确认。本分支的处理（对齐 C_CONVERGENCE_PLAN §11）:

- 实现起点 = TEAM C frozen HEAD `3bd980de`（治理 baseline，非 LOCAL HEAD）。
- C-only 设计、oracle、port manifest 已固定，不依赖获批基座即可推进。
- 共同 Core 基座（extension_host / compare seam）按本仓库冻结 base `7484d44ddeac3c054ca3ba68f92293d965bb615c` 的接口编程；获批后如有 rebase 导致 SHA 变化，SOURCES_MANIFEST.md 继续记录 TEAM source SHA 与 C-only diff 来源。

## 2. 外部依赖登记（立即登记，阻塞整体 gate）

| 依赖 | Oracle | Owner | 状态 | 对 C 的影响 |
|---|---|---|---|---|
| **D1 (A30/F12): 共享 Host runtime SystemExit 隔离** | S30: 七扩展集成，故障扩展普通 Exception 与 runtime SystemExit 分别注入，其余 route 仍可调用；不能只测 load 或 C 内部 catch | A/Core owner（修复 extension_host.py 或提供满足 oracle 的隔离执行机制） | **BLOCKER — 未完成时整体不能报 30/30 PASS** | C 不修改 extension_host.py；C 只交付自身 B/CA 依赖边界的隔离测试。S30 标记 EXTERNAL_BLOCKED 直至独立交付落地。 |
| D2: B Code Facts 接口（PR #31 @ `80e091ac`） | S13–S15 的真实 collector 行为 | B owner | 冻结接口作为对照边界；集成时重新独立核验 | R02 按其 revision/files/skipped 契约编程 |
| D3: CA Context Pack validator/resolver（PR #29 @ `9ea23491`） | S19–S25 的真实 validator 行为 | CA owner | 冻结接口作为对照边界；集成时重新独立核验 | P01/R04 调真实 validate_context_pack |
| D4: Core compare → C route 端到端 | S29 + 七扩展 smoke | A/Core owner + TEAM C owner | 待 W6 | pinned 请求 + 兼容投影 + 正式地图 hash 不变 |

## 3. 提交序列（对齐 C_CONVERGENCE_PLAN §11.4）

convergence: establish W0 contract oracle → complete W1 input and evidence gates → implement W2 diff-map reasoning → implement W3 relation analysis → implement W4 CA trust → implement W5 compatibility and identity → W6 integration suite。

每阶段独立 commit，便于 owner 审查与回退。normal push only，不 force push。

## 4. Gate 提醒（C_CONVERGENCE_PLAN §10 摘要）

- 30/30 PASS 才能申请 READY 评审；S30 未满足时整体 gate 阻塞，不能由 C 内部 catch 替代。
- 所有 kind 满足 evidence、PROPOSED、human_required、无 position、无地图写入。
- poison/conflict/stale/unavailable/未支持外部事实不进 proposal 强证据。
- C 的实施 diff 不复制/改写 B、CA registry、D、Core Host。
