# C_START_HERE — Map Proposal(C)开工入口

> 写给下一位 C Agent。生成于 2026-10-03 独立验收;基准:VALIDATION_BASELINE.json。

## 第一屏:你要知道的六件事

1. **你是谁**:C = Map Proposal。你观察"代码变了什么"与"地图说了什么"的差异,产出带证据的 MapProposal,供人工复核。
2. **你不负责什么**:你**不直接修改正式 Project Map**(也不动 node position、不改其他模块代码)。你只产出 PROPOSED;接受与否由人决定。conflict 一律 HUMAN_REQUIRED,**你不得自己裁决**。
3. **你依赖什么**:
   - Context Authority:**PR #29 @ validated SHA `9ea23491d1849f21bad9f60c1c1ca8df55bb5936`**(状态见下)
   - B / Code Facts(声明级事实;PR31 正在演进它,运行时以实际扩展为准)
   - Git diff(changed_paths,与 A 的 /api/compare 同口径)
   - Current Project Map(人工维护,无版本身份)
4. **Context Authority 当前状态**:`C_CONSUMABLE_WITH_LIMITS`(8 个已知 finding,0 个阻塞 C;清单见 `../validation/findings/CONTEXT_AUTHORITY_KNOWN_LIMITATIONS_FOR_C.md`)。
5. **关键安全规则**:Context Pack 是 **authoritative starting point,不是不可质疑神谕**。结构校验 ≠ 真伪(相干伪造能通过校验)。对关键事实——**revision、PR status、contract shape、implementation state**——必须保留 evidence fallback(git/gh 只读核验)。行为规则见 `C_CONTEXT_SAFETY_RULES.md`(10 条,必读)。
6. **conflict = HUMAN_REQUIRED**:出现在 `known_conflicts` 的 key 不得进入你的任何 proposal 依据,相关差异落 unresolved。

## 五份必读(按序)

1. 本文
2. `C_CONTEXT_SAFETY_RULES.md` — 10 条可执行安全规则(最高优先级)
3. `C_CONSUMABLE_INTERFACE.md` — FROZEN / PROVISIONAL / DO_NOT_DEPEND_ON 三级接口冻结
4. `C_PRODUCT_BOUNDARY.md` — 能做什么 / 禁止做什么
5. `C_INPUT_OUTPUT_CONTRACT_PROPOSAL.md` + `C_ACCEPTANCE_PLAN.md` — 数据契约与 F1–F20 验收

辅助:`C_CONTEXT_AUTHORITY_USAGE.md`(五步消费协议)、`C_B_CODEFACTS_USAGE.md`(B 输出细节)、`C_DO_NOT_ASSUME.md`(20 条禁假设)、`C_IMPLEMENTATION_SEQUENCE.md`(Stage 0–6)。

## 一页纸现状(2026-10-03 实测)

| 事实 | 值 | 来源 |
|---|---|---|
| main | 7484d44(PR #20 merge) | gh api |
| PR #21 | OPEN 非 draft,V1 角色文档(docs/v1-source-of-truth-cleanup@ff22b76) | gh api |
| PR #22 | OPEN **draft**,B 首版原型(collaboration/b/…),686 单元 0 失败 | gh api |
| PR #31 | OPEN **draft**,B 真实 Core 接入(extensions/code_facts/ 正式目录+30 测试) | gh api |
| PR #27 | OPEN draft,D handoff-continuity | gh api |
| PR #29 | OPEN draft,Context Authority MVP(本验收对象) | gh api |
| C | 未实现(全分支无 extensions/map_proposal) | 全分支树检索 |
| Project Map | data/project-map.json:{note, nodes[6], edges[8]};node={id,title,summary,entryPoint,position,evidence[{path,reason}]};edge={from,to,label} | 读文件 |
| 地图版本身份 | 无(none)——mapSource 提案未实现 | pack claim-map-version |
| 团队批准 | main_baseline=candidate,team_approved=false | pack claim-team-approval |

## 实现顺序

见 `C_IMPLEMENTATION_SEQUENCE.md`(Stage 0–6)。第一个可交付里程碑:**Stage 0+1+4 的最小闭环**——给定 pinned revision 的 diff 与当前地图,对"新增文件"产出一条 NODE_ADD 候选(带 evidence,不依赖 B),fixtures F1/F6/F7/F8/F18 先绿。

## 三条铁律(来自验收实验)

1. **pack 必须 validate 后才能用,校验失败=停止**(poisoning:检测到失败仍继续消费是真实风险)。
2. **evidence fallback 是强制的**:每个 proposal 的 rationale 必须能追到 Git revision/changed file/code fact/map node;追不到就输出 UNKNOWN/NEEDS_HUMAN_REVIEW。
3. **C 的每个输出都标 FACT / INFERENCE / PROPOSAL / UNKNOWN** 四类之一,最终接受权在人。
