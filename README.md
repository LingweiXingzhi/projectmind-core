# ProjectMind Context Authority Independent Validation Package

> **本 README 是 validation package 的入口,不是产品 README。** 本分支(`review/context-authority-validation-2026-10-03`)只承载独立验收 / C readiness / 集成研究文档,不承载 Context Authority 产品代码修改。产品 README 与产品代码见 `main` / `feat/context-authority-mvp`。

## RESULT

**CONTEXT AUTHORITY: `C_CONSUMABLE_WITH_LIMITS`** · **C CAN START: `YES_WITH_LIMITS`**

8 个已知 finding,**0 个阻塞 C**;均有明确 consumer-side boundary。

## VALIDATED PR / SHA

**Draft PR #29**(`feat/context-authority-mvp`)@ **`9ea23491d1849f21bad9f60c1c1ca8df55bb5936`**
(base main `7484d44`;验收日期 2026-10-03;172/172 测试 + 独立红队 + hidden holdout + poisoning study)

## C CAN START?

**YES_WITH_LIMITS。** 入口:[c-readiness/C_START_HERE.md](c-readiness/C_START_HERE.md)(第一屏六件事)。C 必须实现 [c-readiness/C_CONTEXT_SAFETY_RULES.md](c-readiness/C_CONTEXT_SAFETY_RULES.md) 的 10 条安全规则。

## MOST IMPORTANT LIMITATION

**Context Pack 结构校验 ≠ 真伪**:相干伪造能通过 validator 并自带正确 digest(poisoning 实证 5/10 穿过,PACK-ONLY 消费者盲信 2/5)。因此 **evidence fallback 对高影响事实(revision / PR status / contract shape / implementation state)是强制的**;conflict 一律 HUMAN_REQUIRED,C 不得自行裁决。

## WHERE C SHOULD START

1. [c-readiness/C_START_HERE.md](c-readiness/C_START_HERE.md) → 2. [C_CONTEXT_SAFETY_RULES.md](c-readiness/C_CONTEXT_SAFETY_RULES.md) → 3. [C_CONSUMABLE_INTERFACE.md](c-readiness/C_CONSUMABLE_INTERFACE.md) → 4. [C_IMPLEMENTATION_SEQUENCE.md](c-readiness/C_IMPLEMENTATION_SEQUENCE.md)(Stage 0 起步,第一个里程碑 = Stage 0+1+4 最小闭环)

## 文档地图

| 目录 | 内容 | 读者 |
|---|---|---|
| [validation/](validation/) | 裁决(OVERNIGHT_CONTEXT_AUTHORITY_VERDICT)、独立审计(INDEPENDENT_CA_AUDIT)、投毒研究(CONTEXT_POISONING_STUDY)、holdout+充分性(HIDDEN_HOLDOUT_AND_SUFFICIENCY_REPORT)、[findings/](validation/findings/)(已知问题与 C workaround) | Reviewer / 全员 |
| [c-readiness/](c-readiness/) | C 开工包 10 份(入口/安全规则/接口冻结/边界/契约/验收/用法/禁假设/施工顺序) | **C 必须阅读** |
| [integration/](integration/) | B/D/CA 跨模块风险、统一 UI 信息架构 | Reviewer / A integration |
| [benchmark/](benchmark/) | benchmark 发布就绪(仍待用户选 remote) | Reviewer |
| [evidence/](evidence/) | 冻结 GT、问题清单、毒包清单与构造脚本、红队探针与结果 | 复现者 |
| [VALIDATION_BASELINE.json](VALIDATION_BASELINE.json) | 验收身份:SHA/状态/数字/报告索引 | 机器可读 |

**本 package 不是**:PR #29 的 merge 授权、C 实现的开始、benchmark 上传授权。决策清单见 VALIDATION_BASELINE.json `human_decisions_still_required`。
