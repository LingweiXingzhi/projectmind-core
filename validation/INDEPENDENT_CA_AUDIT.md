# INDEPENDENT_CA_AUDIT — Context Authority / Draft PR #29 独立验收

- 审计人:全新的独立 Agent(不继承 Context Authority 作者的判断)
- 日期:2026-10-03
- 对象:PR #29 `feat/context-authority-mvp` @ `9ea23491d1849f21bad9f60c1c1ca8df55bb5936`(base main @ `7484d44`)
- 方法:只读 git/gh + 全量重跑测试 + 代码逐行审读 + 独立新增红队探针(不依赖作者报告的 PASS)
- 作者声明状态:C_CONSUMABLE_WITH_LIMITS → 本文独立复核该声明

---

## 0. 一句话结论

**PR #29 的实现质量经独立复核成立。** 172/172 测试独立重跑通过;live verifier 输出与 GitHub 真实状态一致;resolver 在全部 11 组新红队探针下无 SILENT WINNER / SILENT DATA LOSS / WRONG CURRENT / HIDDEN CONFLICT。发现 **5 个新 finding(均不阻塞 C,均有消费者侧缓解)**,其中 2 个建议 CA 后续小修。

---

## 1. 当前真实实现是什么(独立读码结论)

| 组件 | 文件 | 独立确认的行为 |
|---|---|---|
| Schema | `extensions/context_authority/schema.py` (155 行) | 6 种 claim type;**按 domain 定义权威类型集**(team→HUMAN_DECISION/CONTRACT;implementation→VERIFIED_FACT;contract→CONTRACT/HUMAN_DECISION;architecture→HUMAN_DECISION/CONTRACT/PROPOSAL;research→RESEARCH),**类型间无排序**;HISTORICAL 任意 domain 可载但永不进 current;research_artifact 来源不得为 CURRENT 类型背书;所有校验错误显式抛出,无静默默认值 |
| Registry | `registry.py` (88 行) | append-only claims.jsonl;重复 id 显式报错;行序无关(resolver 排序);server 自身从不写 |
| Resolver | `resolver.py` (253 行) | 确定性、fail-closed;**无时间戳优先、无类型多数决、无静默 fallback**;supersedes 图校验(BROKEN/SELF/CROSS_KEY/INVALID_AUTHORITY/CROSS_SCOPE/CYCLE 全部 → CONFLICT + HUMAN_REQUIRED);verifier 失败 → STALE+reason,**不伪造值**;live 值变化 → 生成派生 claim,保留原始 evidence |
| Verifiers | `verifiers.py` (112 行) | 只读(本地 git / gh api);PR verifier 区分 PR_OPEN/CLOSED/MERGED,拒收 open+merged 矛盾载荷;main_head 用 origin/main remote-tracking ref 并标 freshness=local_reference(诚实标注缓存可能) |
| Context Pack | `context_pack.py` (459 行) | schema_version="0.1";task 关键词→domain 过滤;**pack 级 validator**(459 行,结构性一致性:current 投影、counts、evidence 回链、do_not_assume、digest 重算);integrity 明确标注 guarantee=structural_consistency_only(不认证真伪) |
| Extension | `extension.py` (101 行) | 6 个 action;严格 key 校验;POST 输入 64KB 上限(app.py:439);响应无此限 |
| 消费者合同 | CONTEXT_AUTHORITY_FINAL_REPORT "C consumption gate" | validate_context_pack(expected_revision=...) 前置;选 key/scope;查冲突/stale/unavailable;保留 UNKNOWN/HUMAN_REQUIRED |

## 2. 什么已经测试(独立复现)

- **172/172 tests PASS**,7.8 秒,单进程(`python -m unittest discover -s tests`,2026-10-03 于 9ea2349)。构成:CA spec t1–t18、real drift fixtures f1–f5、resolver adversarial a1–a55、pack adversarial p1–p60、live boundary 4、metrics 9、core app/extensions 17。
- **Live pack 生成**(run_verifiers=True,真实 gh api + 本地 git):成功;`implementation.main_head`=7484d44(=真 origin/main)、`pr_21_head`=OPEN@ff22b76、`pr_22_head`=OPEN@0c467471(与 gh api 实查一致);`team_approval.team_approved=False` 与 `map_version.identity=none` 被诚实呈现(无 verifier 的 key 标 freshness=unverified,不冒充已验证)。
- **ExtensionHost 发现**:context_authority + project_summary 均 ready。
- **往返验证**:pack 生成后立即 validate_context_pack(expected_revision=同一 SHA)通过。
- **作者报告对照**:其"172/172 三进程 PASS"、"Open≠Merged"、"conflict→HUMAN_REQUIRED"、"proposal/research/history 不进 current"等关键声明均与我的独立复现一致。作者关于确定性已自带 caveat("does not promise identical live clocks"),与本文 F01 相符,无隐瞒。

## 3. 什么只是文档声称(未独立复现/超出本次范围)

- 作者引用的历史实验数字(Raw 60/60 vs CA 60/60、poisoning 10 CORRECTED 等)的**原始 run 数据**存在(experiments/ca_experiment/ 下 jsonl 齐全),本次以第 9/10 节的独立重判与新 holdout 代替信任。
- benchmark 侧报告(B_PR22_HOLDOUT 等)只能读快照,benchmark 目录无 git 历史,无法溯源其产生过程。

## 4. 独立新增红队探针(172 测试之外)

脚本:`../evidence/redteam/redteam_resolver.py`(随本 package 提交)。结果:

| 探针 | 场景 | 结果 |
|---|---|---|
| RT-A | 同 key 两个 scope 均 ACTIVE 且值不同 | **FINDING-02**(见 §5) |
| RT-B/B2/B3 | do_not_assume 计数 vs domain 过滤后 sections | **FINDING-04** |
| RT-C | 真实 default verifier 路径 + code_facts 值携带额外字段 | **FINDING-03** |
| RT-D | 5000 节点 supersedes 环 | OK:0.07s,CYCLIC_SUPERSEDES→HUMAN_REQUIRED,无递归爆栈 |
| RT-E | 5000 claims + 1 冲突 | OK:0.08s,counts 正确,双方 claim 均保留,HUMAN_REQUIRED |
| RT-F | 空 registry 端到端 pack 构建+验证 | OK:digest 稳定,4 条基础 do_not_assume |
| RT-G | verifier 抛 SystemExit | **FINDING-05**(泄漏,非阻塞) |
| RT-H | verifier 全员不可用 + 3 个注册值 | OK:3 个全部 withheld 进 stale(reason 明确),0 进 current,**无静默选边** |
| RT-J | supersedes 重复列同一目标 | OK:去重处理一次,无异常 |
| RT-K | CONTRACT vs HUMAN_DECISION 同 key 同 scope 不同值 | OK:CONFLICT+HUMAN_REQUIRED,无类型多数决 |
| (既有 p01–p60) | 伪包/重签/来源伪造/投影破坏等 60 例 | 全部拒绝(独立重跑) |

**四类禁止行为逐项核验:SILENT WINNER 无、SILENT DATA LOSS 无(所有丢弃均有 stale/conflict/unavailable 记录+原因)、WRONG CURRENT 无(live 值必须匹配 verifier 才进 current,且标 derived evidence)、HIDDEN CONFLICT 无(validator 强制 conflict 保留且 HUMAN_REQUIRED)。**

## 5. Findings(全部不阻塞 C)

### FINDING-01(LOW)|pack digest 在 verify=true 时不可字节级复现
- 复现:同一 task/registry 连续两次 `build_context_pack(run_verifiers=True)`,digest 不同;3 轮共 45 处差异,44 处为 `verified_at` 时间戳,第 45 处为 digest 本身;`run_verifiers=False` 时两次字节全等。
- 影响:C 无法"重新生成同一 pack 来核对 digest",只能结构校验或固定 verify=false。
- 作者状态:报告中已声明该限制("Captured timestamps/network results are held fixed; this does not promise identical live clocks")。**非隐瞒,记录为已知限制。**
- 建议:后续 CA 版本把 `verified_at` 排除出 digest 输入,或 digest 只覆盖语义投影;C 侧短期对策见 C_CONSUMABLE_INTERFACE.md。

### FINDING-02(MEDIUM)|多 scope 同 key 的 ACTIVE 行从 `current` 便捷投影中静默消失
- 复现:`team.roles.v1` 在 scope=team 值 X、scope=legacy-doc 值 Y,均 HUMAN_DECISION → 两者都保留在 `current_by_scope`,但 `current` 字典无此 key;conflicts=0(不同 scope 不算冲突);**do_not_assume 无任何提示**。
- 影响:只读 `current` 的消费者会以为没有角色映射 → 事实缺口(非错误事实,是缺失事实)。数据本身无损。
- 建议(CA 小修):build_do_not_assume 增加"存在 N 个 multi-scope key,只出现在 current_by_scope"规则;C 侧短期对策:**只把 `current` 当索引,一律读 `current_by_scope`**。

### FINDING-03(MEDIUM)|部分 live 验证的字段级范围在行级不可见,未验证字段随值透传
- 复现:registry 中 `implementation.code_facts` 值为 {status, pr, head, fabricated_field, unit_count},走真实 `build_default_verifiers` 路径:PR head 匹配 → fabricated_field/unit_count 原样进入 current value,行级 `freshness=verified`;字段级范围只存在于 `evidence[].live_verification.verified_fields=["status","pr","head"]`。
- 影响:这是 poisoning study 最相关的面:**恶意/出错的 registry 作者可以让任意字段搭 freshness=verified 的便车**。行级没有"部分验证"标记。
- 缓解:append-only registry + 人工 owner 使恶意注入概率低;evidence 链使字段范围可查。
- 建议(CA 小修):行级增加 `verified_fields` 或把 freshness 改为 partial;C 侧对策:对 implementation.* 值中 status/pr/head 之外的字段,必须回 evidence 查 verified_fields 或视为 UNVERIFIED。

### FINDING-04(MEDIUM-LOW)|do_not_assume 计数文本用全 registry 计数,sections 是 domain 过滤后的,且 validator 不校验数字
- 复现 A(合法 pack 自相矛盾):task="team roles only",registry 含 1 条 implementation stale(resolve 级 verifier 不可用)→ pack `known_stale_sources`=0、`verification_unavailable`=0,但 do_not_assume 写 "1 stale/superseded claims exist"。
- 复现 B(伪包):把两条计数规则数字改成 99 并重算 digest → `validate_context_pack` 接受(suffix 匹配忽略了数字)。
- 影响:消费者看到计数警告却找不到对应条目;伪包可用夸大计数制造恐慌/掩盖。数字本身不可信,固定后缀部分可信。
- 建议:计数规则改为按过滤后 sections 生成;validator 强制数字一致。

### FINDING-05(LOW)|verifier 抛 SystemExit/BaseException 可穿透 resolve 与 extension runtime
- 复现:`_verify` 只 catch `Exception`;SystemExit 直接穿出 `resolve()`;`ExtensionHost.run` 同样只 catch Exception(load 路径已修 SystemExit,run 路径没有)。
- 影响:内置 verifier 不会触发;若未来允许第三方注册 verifier(C 生态可能),单个坏 verifier 可打死整个服务线程。
- 建议:run 路径 catch (Exception, SystemExit);_verify 同理。非阻塞。

## 6. Authority Rules Audit 专项结论

- **不存在全局 HUMAN > CONTRACT > FACT 简单 precedence**。`DOMAIN_AUTHORITY` 按 domain 列权威类型集合,集合内无序;同 key/scope 两条不同类型合法 claim 值不同 → CONFLICT/HUMAN_REQUIRED(RT-K 实证);值相同 → 合并保留全部 evidence(t/a19 实证)。
- Git SHA/PR 状态 → VERIFIED_FACT(verifier live 校验,Open/Closed/Merged 三态区分,p29 实证 MERGED≠TEAM_APPROVED:`implementation.team_approval` 是独立 key,merge 不会升级它)。
- team role → HUMAN_DECISION/CONTRACT;research finding → RESEARCH(进 research_notes,永不进 current,t4/a54/p15/p57 实证);proposal → PROPOSAL(t3/a15/p28 实证)。
- 无 supersedes 的两条 ACTIVE 冲突 → 永远 HUMAN_REQUIRED,无任何自动选边路径(代码逐行确认 + RT-K/RT-E/RT-H 实证)。

## 7. 结论

- 作者的 C_CONSUMABLE_WITH_LIMITS 自评**成立**,本文把 limits 具体化为 F01–F05。
- C_CONSUMABLE 11 条最低要求逐条核对:1 无严重 silent resolver bug ✓;2 conflict→HUMAN_REQUIRED ✓;3 proposal/research/stale/history 不污染 current ✓;4 OPEN≠MERGED ✓;5 MERGED≠TEAM_APPROVED ✓;6 pack deterministic —— **语义层 ✓ / 字节层仅 verify=false 时成立(F01)**;7 evidence/revision 可追溯 ✓;8/9 hidden holdout 与 disagreement 改善 → 本文第 10 节独立实验;10 poisoning study → 本文第 8 节;11 C-facing schema 明确 ✓(schema_version=0.1 + validator + 消费 gate 文档)。
- 最终状态判定见 OVERNIGHT_CONTEXT_AUTHORITY_VERDICT.md。
