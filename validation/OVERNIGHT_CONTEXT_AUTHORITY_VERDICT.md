# OVERNIGHT_CONTEXT_AUTHORITY_VERDICT

> 2026-10-03 过夜独立验收 · 全新独立 Agent · 不继承 Context Authority 作者判断
> 本文件为已发布的 validation package 副本;原始工作目录 `G:\jiagou\projectmind-overnight-2026-10-03\`,可复现证据见 `../evidence/`

---

## 第一屏

**CONTEXT AUTHORITY STATUS: `C_CONSUMABLE_WITH_LIMITS`**
**C_CAN_START: `YES_WITH_LIMITS`**
**PR29_HEAD: `9ea23491d1849f21bad9f60c1c1ca8df55bb5936`**(feat/context-authority-mvp → main,OPEN draft,base 7484d44)
**PRODUCT BUGS FOUND: 8(全部记录在案;0 个阻塞 C)**
**FIXES MADE: 无(未改任何产品代码——按"只修阻塞 C 的 bug"原则,8 条均不构成;修复建议已写入下文)**
**REMAINING LIMITS: 6 条消费级限制 + 2 条建议 CA 小修(见下)**

---

## 1. 判定依据(独立复现,非采信作者报告)

### 重跑与验收(全部独立完成)

| 项 | 结果 |
|---|---|
| 172/172 测试重跑(9ea2349) | PASS,7.8s |
| live pack 生成 +往返 validate + live verifier 对 GitHub 实况 | 全部一致(PR21/22 OPEN、main 7484d44、team_approved=false 诚实呈现) |
| ExtensionHost 发现 | context_authority + project_summary ready |
| 独立红队 11 组新探针(172 测试之外) | 无 SILENT WINNER / SILENT DATA LOSS / WRONG CURRENT / HIDDEN CONFLICT |
| 作者冻结实验抽查(B1/A1 原始 jsonl vs GT) | 相符,其 metrics 声明可信 |
| 独立 Hidden Holdout(24 全新问题,GT 先冻结) | **CONTEXT 条件 3 agents:24/24 全对、0 分歧;RAW 条件:71/72、2 处 agent 间分歧(1 处真错误)** |
| 独立 Poisoning Study(P01–P10 相干伪造 + 13 fresh agents) | 结构校验拦 5/10(粗心伪造);**相干伪造 PACK-ONLY 盲信 2/5;pack+evidence 纠错 4/4** |
| Sufficiency(三条件) | pack-only 6/24 充分、5/24 部分、13/24 无信息但 **0 幻觉**;pack+evidence 24/24 |

### C_CONSUMABLE 11 条最低要求逐条

| # | 要求 | 判定 |
|---|---|---|
| 1 | 无严重 silent resolver bug | ✓(红队 11 探针 + 既有 115 adversarial) |
| 2 | conflict → HUMAN_REQUIRED | ✓(RT-K/RT-E/RT-H + validator 强制) |
| 3 | proposal/research/stale/history 不污染 current | ✓(t3-t5/a14/a15/p28/p30) |
| 4 | OPEN ≠ MERGED | ✓(a45/a46,p29;verifier 拒收 open+merged 载荷) |
| 5 | MERGED ≠ TEAM_APPROVED | ✓(team_approval 独立 key,merge 不升级) |
| 6 | pack deterministic | **语义层 ✓;字节层仅 verify=false 成立**(F01:时间戳入 digest) |
| 7 | evidence/revision 可追溯 | ✓(validator 全链回查;holdout 中 evidence 链两次把 agent 引到跨仓库证据) |
| 8 | hidden holdout accuracy 不下降 | ✓(24/24 ≥ RAW,且反超 h14/h16) |
| 9 | factual disagreement 降低有充分证据 | ✓(0 vs 2 分歧;poisoning 纠错 4/4;协议遵从率 100%) |
| 10 | poisoning 无严重系统性风险 | ✓(附条件:相干伪造可穿校验,**消费协议必须把 evidence fallback 设为强制**——已写入 C 接口) |
| 11 | C-facing schema 明确 | ✓(schema_version 0.1 + 精确字段集校验 + 消费 gate 文档) |

## 2. PRODUCT BUGS FOUND(F01–F08,详见 INDEPENDENT_CA_AUDIT.md)

| ID | 严重度 | 一句话 | 对 C |
|---|---|---|---|
| F01 | LOW | verify=true 时 digest 不可字节复现(verified_at 入 digest) | 用 validator,不用 digest 复现 |
| F02 | MEDIUM | multi-scope key 从 `current` 投影静默消失,无告警 | 只读 current_by_scope |
| F03 | MEDIUM | 部分 live 验证的字段级范围行级不可见;未验证字段随值透传且行级 freshness=verified | 查 evidence.verified_fields |
| F04 | MED-LOW | do_not_assume 计数文本=全 registry 计数,sections 是过滤后;validator 不查数字 | 不解析数字 |
| F05 | LOW | verifier 抛 SystemExit 可穿透 resolve 与 host.run(仅 catch Exception) | 不影响 C;建议修复 |
| F06 | LOW | pack 的 project_revision 在包内零佐证(孤立 SHA) | C 必须 PIN 自己的 revision |
| F07 | MEDIUM | PR verifier 不读 draft 字段——PR22 实为 Draft,pack 只显示 PR_OPEN | 合并判断独立查 draft |
| F08 | LOW | claim-team-approval 的 source.ref 章节定位失准(§开场状态不存在) | doc 类 source 做文件级核验 |

## 3. FIXES MADE

**无产品代码修改。** 理由:§29 约定只修"真实 blocker / semantic bug";F01–F08 均有消费者侧安全用法,不阻塞 C。实验/报告产物已整理为本 review package(见仓库根 README);两个 worktree 保持 clean(见 §5 安全检查)。

**建议 CA 后续小修(不紧急,可与 schema 0.2 一并)**:
1. F02:build_do_not_assume 增加"存在 multi-scope key"规则(一行)。
2. F03:current 行加 `verified_fields` 或 freshness=partial(小改,注意兼容)。
3. F04:计数规则改为按过滤后 sections 生成;validator 强制数字一致。
4. F05:host.run 与 _verify 改 catch (Exception, SystemExit)。
5. F07:PR verifier 返回值加 `draft: bool`(pr_22_head 立即受益)。

## 4. REMAINING LIMITS(C 消费必须遵守)

1. 校验=结构一致性,**不是真伪**(poisoning:相干伪造 5/10 穿过);evidence fallback 强制。
2. 读 `current_by_scope`,不信 `current` 投影完整性。
3. `freshness=verified` ≠ 全字段已验证;非核心字段查 verified_fields。
4. do_not_assume 数字不可信,固定禁令可信。
5. registry 只覆盖登记过的 PR(21/22);PR24/26/27/29/31 无 claim;**PR31 正在演进 B 接口而 CA 契约仍钉 PR22 README**(合并后需追加 supersedes claim)。
6. pack-only 覆盖 6/24(SUFFICIENT)+5/24(PARTIAL)——单独用 pack 不够,CA 是增强不是唯一事实源。

## 5. 最终安全检查

```
MAIN MODIFIED: NO          (main = 7484d44,两 worktree clean)
MAIN PUSHED: NO
MAIN MERGED: NO
FORCE PUSH: NO
PR #22 MODIFIED: NO        (B 分支未动;PR22/27/29 仅只读 gh 查询)
PR #27 MODIFIED: NO
OTHER TEAM BRANCH MODIFIED: NO
C IMPLEMENTED: NO          (只产出设计/验收/开工包文档)
DISCLOSURE: 本轮执行过一次 git fetch origin(只读更新本地 remote-tracking refs,不改任何分支/远程)
实验产物位置: 本仓库 review 分支(validation/ c-readiness/ integration/ benchmark/ evidence/);原始工作目录 projectmind-overnight-2026-10-03/ 保留在盘上
```

## 6. STOP POINT 确认

按 §34:CA 独立验收 ✓ + C readiness package ✓ + B/D/CA integration risk ✓ + benchmark publication readiness ✓ → **到此停止**。不 merge main、不开始 C 编码、不做统一 UI、不建 benchmark 远程 repo。等待用户下一条指令。
