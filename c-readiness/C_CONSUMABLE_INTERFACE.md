# C_CONSUMABLE_INTERFACE — C 可以安全依赖 Context Authority 的哪些内容

- 审计人:独立验证 Agent,2026-10-03
- 依据:INDEPENDENT_CA_AUDIT.md(F01–F08)、CONTEXT_POISONING_STUDY.md、HIDDEN_HOLDOUT_AND_SUFFICIENCY_REPORT.md、schema.py/context_pack.py/extension.py 逐行读码
- 对象:Context Authority @ PR29 head `9ea23491d1849f21bad9f60c1c1ca8df55bb5936`,schema_version **0.1**

## 前置判定

**CONTEXT AUTHORITY STATUS: C_CONSUMABLE_WITH_LIMITS**(理由与证据见 ../validation/OVERNIGHT_CONTEXT_AUTHORITY_VERDICT.md)。
C 可以开工,但必须按本文件的消费规则来;F02/F03 两条 limit 直接影响 C 的实现方式。

---

## 1. FROZEN_FOR_C_V0_1(C v0.1 可以硬依赖)

以下内容有 schema 强校验 + 172 测试 + 独立红队覆盖,改动会破坏 validator/测试,可信度最高:

| 接口 | 冻结内容 | 依据 |
|---|---|---|
| Pack 顶层字段集 | `{schema_version, task, task_domains, project_revision, current_state, human_decisions, verified_facts, relevant_contracts, proposals, research_notes, historical_sources, known_conflicts, known_stale_sources, do_not_assume, verification_unavailable, registry_problems, evidence, integrity}` — validator 要求**字段集精确相等** | context_pack.py `_validate_context_pack`(字段集 require) |
| schema_version | 字符串 `"0.1"`;validator 拒绝其他值 | 同上 |
| project_revision | 完整 40/64 位小写 hex;`validate_context_pack(pack, expected_revision=…)` 消费者侧钉定 | REVISION_PATTERN + p23 |
| current_state 结构 | `{current, current_by_scope, counts, registry_hash}`;`current` = 单 scope 键投影;`current_by_scope` = 全量行 | p32/p43/p44 |
| 行级不变量 | `PROPOSAL/RESEARCH/HISTORICAL` 永不进入 current;t3/t4/t5/a14/a15/p28/p30;CONFLICT 行必带 `resolution: HUMAN_REQUIRED`;SUPERSEDED 行必带 `superseded_by` 且与 supersedes 边闭合 | validator 多条 + 独立红队 RT-K/RT-H |
| evidence 回链 | 每条 current/section 行的 claim_id 必须在 evidence 有完整条目 `{claim_id,key,scope,type,value,source,revision,claim_revision,source_revision}`;来源 kind 枚举 6 种;research_artifact 不得为 current 类型背书 | p24/p25/p57/p58 |
| integrity | `{"algorithm":"sha256","digest","guarantee":"structural_consistency_only"}`;digest 为**未密钥**结构一致性校验,**不认证真伪** | validator 重算;poisoning 实证 |
| Claim 类型/域 | 6 类型;DOMAIN_AUTHORITY 集合(无排序);同 key+scope 值冲突 → CONFLICT/HUMAN_REQUIRED | schema.py + RT-K |
| API 动作 | GET `state/claims/conflicts`;POST `resolve_state/context/validate_context`;严格 key 校验 | extension.py + t 系测试 |
| resolver 确定性 | 同一 registry 输入(无 verifier)→ 字节级一致;有 verifier 时语义级一致(见 PROVISIONAL #1) | t13/t14 + FINDING-01 |

## 2. PROVISIONAL(可用,但 C 必须防御其变化)

1. **`verified_at` / `live_verification.verified_at` 时间戳**:每包不同(digest 因此不可字节复现,FINDING-01)。C 不得把"重新生成 pack 对 digest"当作验证手段;验证=调 `validate_context_pack`。
2. **`current` 便捷投影会静默丢 multi-scope 键**(FINDING-02):C **一律读 `current_by_scope`**,把 `current` 当索引。CA 后续可能给 `current` 加多 scope 支持或加告警,C 不应感知。
3. **`freshness` 取值集合**:`verified / local_reference / unverified / mixed`。行级 freshness=verified 时,值内**仍可能含未被 live 验证的字段**(FINDING-03)——C 对 `implementation.*` 值中 status/pr/head 之外的字段必须回 `evidence[].live_verification.verified_fields` 查字段级范围,查不到就当 UNVERIFIED。
4. **`do_not_assume` 计数文本**(FINDING-04):数字可能指全 registry 而非本包 sections;C 只可依赖固定后缀语义("OPEN does not mean merged"、PROPOSAL/RESEARCH/HISTORICAL/stale/conflict 各类禁令),不得解析数字。
5. **verifier 覆盖的 key 集合**:当前只有 `implementation.main_head / pr_21_head / pr_22_head / code_facts` 四个。新 key(如 pr_27_head)随时可能加入;C 不应假设"pack 里没有的 PR 就不存在"(holdout h11-h13/h21 实证)。
6. **PR verifier 返回值字段**:`{status: PR_OPEN|CLOSED|MERGED, pr, head}`;`draft` 等新字段可能追加(FINDING-07)。C 解析时对新字段向后兼容。
7. **`registry_hash`**:对 registry 内容敏感,registry 合法追加即变化;C 可用它判断"两个 pack 是否出自同一 registry 状态",不可用作长期标识。
8. **section 行的 `state` 字段**:current 行恒 ACTIVE;非 current 行的 state 枚举可能扩展。

## 3. DO_NOT_DEPEND_ON(C v0.1 禁止依赖)

1. **registry 文件本体与位置**(`extensions/context_authority/data/claims.jsonl`):append-only、内容随时合法追加;C 只消费派生 pack,不直读 registry。
2. **evidence 之外的任何 claim 字段**(notes/created_at 等可能重排);C 只用 evidence 契约字段。
3. **HTTP 传输层**:POST 64KB 上限、响应编码等属 core 传输细节;C v0.1 用 Python API(`build_context_pack`/`validate_context_pack`)或本地文件交付 pack。
4. **extension UI / inspector 页面**:演示性质,无兼容承诺。
5. **`task` → domain 关键词映射**(TASK_KEYWORDS):启发式且可能调整;C 固定用自己的 task 字符串并实测其 `task_domains` 覆盖所需域(map 触发全域)。
6. **counts 的具体数值**;只可依赖 counts 与 sections 的一致性(validator 保证)。
7. **`generated_at_note` 等 meta 字段的存在与措辞**。

## 4. C 消费协议(五步,MANDATORY)

```
1. PIN     : C 侧确定自己的 expected_revision(完整 SHA)
2. VALIDATE: validate_context_pack(pack, expected_revision=pin) —— 失败=硬停止,不得降级消费
3. SELECT  : 只从 current_by_scope 选 (key,scope);known_conflicts/verification_unavailable 命中的 key 一律
             转 HUMAN_REQUIRED / UNKNOWN,不得取值
4. EVIDENCE: 对将写入 proposal 依据的每条 claim,打开 evidence 条目核对
             source.kind/ref/revision 与(implementation.*)live_verification.verified_fields
5. RECORD  : C 的输出必须带 pack 的 schema_version + project_revision + registry_hash,
             使 proposal 可回溯到具体事实底座
```

## 5. 已知 limit 对 C 的一行总结

- F01:C 验证 pack 用 validator,不用 digest 复现。
- F02:C 读 current_by_scope,不读 current。
- F03:C 对 implementation.* 值的非核心字段查 verified_fields,否则 UNVERIFIED。
- F04:C 不解析 do_not_assume 数字,只用固定禁令。
- F05:不影响 C(第三方 verifier 才相关;CA 修复建议见 VERDICT)。
- F07:C 把 PR_OPEN 当"可能还是 Draft",合并/接手判断必须独立查 draft 字段。
- F08:source.ref 的章节级定位可能有误,C 对 doc 类 source 做文件级核验即可。
