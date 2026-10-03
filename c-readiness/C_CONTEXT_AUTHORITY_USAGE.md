# C_CONTEXT_AUTHORITY_USAGE — C 如何正确消费 Context Authority

## 总原则

CA 给 C 的是**可追溯的事实底座**,不是"可以全信的真相"。Poisoning 实验证明:相干伪造能穿过结构校验(5/10),PACK-ONLY 盲信率 2/5;而 pack+evidence 纠错率 4/4。所以 C 的姿态是:**底座用来定向,证据用来落锤。**

## 消费五步(实现为 C 内的一个函数,单点强制)

```python
def load_pack(path_or_dict, expected_revision: str) -> Pack:
    pack = validate_context_pack(pack, expected_revision=expected_revision)  # 失败 → raise,硬停止
    return pack
```

1. **PIN**:C 自己确定 expected_revision(=target_revision);不接受"pack 自报的 revision"作为匹配依据以外的东西。
2. **VALIDATE**:失败即硬停止(C 的响应返回 error,不降级)。
3. **SELECT**:
   - 只读 `current_state.current_by_scope`(FINDING-02:`current` 会静默丢 multi-scope key)。
   - key 出现在 `known_conflicts` → 该事实视作 HUMAN_REQUIRED,C 的输出必须落 unresolved,不得选边。
   - key 出现在 `verification_unavailable` → 视作 UNVERIFIED,不得作为 proposal 依据。
   - `known_stale_sources` / `historical_sources` / `proposals` / `research_notes` 里的 claim **永远不能**出现在 C 的 evidence。
4. **EVIDENCE**:进入 proposal.evidence 的每条 context_claim,必须已经核对:
   - `source.kind/ref/revision` 与 claim 值匹配(implementation.* 的 binding revision == project_revision,validator 已查,但 C 保留防御);
   - 若值含 status/pr/head 之外字段 → 查 `live_verification.verified_fields`(FINDING-03),查不到的字段标 UNVERIFIED。
5. **RECORD**:C 的每个响应带 `{schema_version, project_revision, registry_hash}`;proposal.evidence 里的 context_claim 条目含 `claim_id + pack_revision`,保证回放。

## C 应该用 CA 的哪些 key(现状清单,2026-10-03)

| key | 用途 | 注意 |
|---|---|---|
| implementation.main_head | 判断 target 是否基于最新 main | freshness=local_reference,合并前可 gh 复核 |
| implementation.pr_22_head / pr_21_head | 判断 B/V1 文档是否已合并 | OPEN≠MERGED≠TEAM_APPROVED;draft 字段 pack 没有(FINDING-07),需要时独立查 |
| implementation.code_facts | B 交付状态 + 附带评测摘要 | evaluated 字段不在 live 验证范围 |
| team.roles.v1 | 责任位口径 | HUMAN_DECISION;多 scope 时读 current_by_scope |
| contract.code_facts_shape / code_facts_input | C 调 B 的参数与解析约定 | 钉在 PR22 README;PR31 可能演进(见跨模块审计) |
| implementation.map_proposal_snapshot / handoff_snapshot | C/D 状态 | 范围仅三棵被观察树 |
| implementation.map_version / team_approval | 地图身份/团队批准状态 | 无 verifier,freshness=unverified |

## C 不该让 CA 做的事

- 不让 CA 替 C 判断"架构上该不该加这条 edge"——那是 INFERENCE,C 自己给理由,人裁决。
- 不用 CA 的 registry_problems 之外的信息推断 registry 健康;registry_problems 非空时照常消费但输出 limits 注明。
- 不缓存 pack 跨任务复用:每次 SuggestMapRequest 重新取/验证(便宜,且防 stale)。

## 降级路径

CA 不可用(扩展缺失/校验失败)时,C **可以继续运行**,但必须:(a) 输出 limits 注明 "context authority unavailable";(b) 不输出任何引用 context_claim 的 evidence;(c) 事实口径完全依赖 Git diff + code_facts + 当前地图(这本身就够 Stage 1–3 用)。CA 是增强,不是依赖锁死——这样 CA 的故障不会阻塞 C。
