# CONTEXT_AUTHORITY_SCHEMA — 数据模型与解析规则 v0.1

> 状态：Context Authority MVP 的实现契约（`extensions/context_authority/`）。deterministic resolver；无 LLM 参与；无时间戳优先级；无静默回退。

## 1. Claim（claims.jsonl，追加式注册表）

```json
{
  "id": "claim-v1-role-map",              // ^claim-[a-z0-9][a-z0-9._-]{0,79}$，全局唯一
  "key": "team.roles.v1",                 // 点分小写；首段=域
  "value": { ... },                       // 任意 JSON 标量/对象
  "type": "HUMAN_DECISION",               // 见下
  "scope": "team",                        // 生效范围（路径/分支/提交/团队）
  "source": {"kind": "human|repo|gh_api|doc|report|research_artifact",
             "ref": "...", "revision": "可选：完整 SHA 或日期"},
  "supersedes": ["claim-old-role-map"],   // 可选：显式取代
  "created_at": "...", "verified_at": "...", "notes": "..."
}
```

### type（六种，固定枚举）
`VERIFIED_FACT`（可验证的仓库/Git/PR 状态）· `HUMAN_DECISION`（人已裁决）·
`CONTRACT`（现行接口/交付契约）· `PROPOSAL`（提案）· `RESEARCH`（研究结论）·
`HISTORICAL`（历史材料，仅溯源）

### state（四态，**由 resolver 派生，不存储**）
`ACTIVE` · `STALE` · `SUPERSEDED` · `CONFLICTED`
—— RESEARCH/STALE 是两个正交维度：type 说"这是什么性质"，state 说"它现在还算数吗"。

## 2. 域 → 权威类型（无全局排序）

| 域 | 可成为 CURRENT 的 type |
|---|---|
| `team.*` | HUMAN_DECISION, CONTRACT |
| `implementation.*` | VERIFIED_FACT |
| `contract.*` | CONTRACT, HUMAN_DECISION |
| `architecture.*` | HUMAN_DECISION, CONTRACT, PROPOSAL* |
| `research.*` | RESEARCH |
| 任意域 | HISTORICAL 永可注册，**永不进 current** |

\* PROPOSAL 只进 proposals 段，绝不成为"已确认架构"。类型不在域授权内的注册直接报错（不静默改类型）。

## 3. resolver 规则（确定性）

1. **supersedes**：被引用 claim → `SUPERSEDED`（保留可查，不进 current）；断链引用 → `registry_problems.BROKEN_SUPERSEDES`。
2. **同 (key, scope) 组**内存活且 current-eligible 的 claim：
   - value 全等 → 折叠为一条 ACTIVE（claim_ids 并列，按 id 排序）；
   - value 不等 → 全体 `CONFLICTED`，输出 `{status: CONFLICT, resolution: HUMAN_REQUIRED}`，**绝不自动选赢家**；
   - 时间戳不参与任何比较（T8）。
3. **stale 检测**（仅 VERIFIED_FACT 且 key 注册了 live verifier）：存储 value ≠ live value → 旧 claim `STALE`（附 live_value），并派生确定性 auto-claim 为 ACTIVE；verifier 不可用 → 旧值退出 current，保留 STALE provenance，记入 `verification_unavailable`。
4. **current 白名单**：只有 VERIFIED_FACT / HUMAN_DECISION / CONTRACT 可进 current；PROPOSAL→proposals、RESEARCH→research、HISTORICAL→historical。
5. **确定性**：所有输出排序；registry 行序不影响结果（T13/T14）；`registry_hash = sha256(按 id 排序的规范 JSON)`。

## 4. CURRENT_STATE.json

```json
{"generated_at_note": "derived view - regenerate rather than hand-edit",
 "current": {key: {value, type, claim_ids, source, scope, ...}},
 "conflicts": [{key, scope, status: "CONFLICT", claims, resolution: "HUMAN_REQUIRED"}],
 "stale": [...], "proposals": [...], "research": [...], "historical": [...],
 "verification_unavailable": [...], "registry_problems": [...],
 "registry_hash": "sha256:...", "counts": {...}}
```

## 5. Context Pack

`build_context_pack(task, repo_root, registry_path, revision=None, run_verifiers=True)`
→ `{schema_version:"0.1", task, task_domains, project_revision, current_state, relevant_contracts,
human_decisions, verified_facts, known_conflicts, known_stale_sources,
proposals, research_notes, historical_sources, do_not_assume, verification_unavailable,
registry_problems, evidence[], integrity}`。project_revision 从 Git 解析，显式输入要求完整小写 40/64 字符 commit SHA。evidence 区分 claim_revision/source_revision，保留每条 claim 的独立来源。

## 6. API（遵循 EXTENSION_INTERFACE）

- `GET /api/extensions/context_authority?action=state|claims|conflicts`
- `POST /api/extensions/context_authority` ≤65536B：
  `{"action":"resolve_state"}`、`{"action":"context","task":"...","revision"?:"...","verify"?:"bool"}` 或 `{"action":"validate_context","pack":{...},"expected_revision"?:"..."}`
- 严格键校验；未知字段/未知 action → 400；注册表数据错误 → 400（显式失败，不吞）。

## 7. Live verifiers

`implementation.main_head`（本地 git origin/main）、`implementation.pr_21_head`、
`implementation.pr_22_head`、`implementation.code_facts`（gh api）。区分 PR_OPEN / CLOSED / MERGED。main 仅核查缓存 origin/main，freshness=local_reference，不声称网络实时。verifier 不可用时退出 current。

## 8. 验证后冻结的消费边界

current_by_scope 保留每个 (key,scope)。兼容 current 仅包含无 scope 歧义的 key；counts.current 计 scoped rows。非法 supersedes（环/自引用/断链/跨 key/不合法权威）进入 HUMAN_REQUIRED 和 registry_problems，不静默丢失。直接 resolve 调用也执行 schema/重复 ID 验证；research_artifact 来源不能支撑 current-eligible 类型。

validate_context_pack(pack, expected_revision) 校验所有投影、类型、状态、证据、revision、counts、warnings 和 checksum，失败显式 ValueError。checksum 无签名，只证明内部一致；一致伪造的人类决定或遗漏 claim 必须沿独立证据核查。扩大的 pack 可能超过 host POST 65,536B，应调用 Python validator；不修改共享 host 上限。C 的稳定/临时/禁用字段详见根目录 C_CONSUMABLE_INTERFACE.md 与 AGENT_BOOTSTRAP.md。
