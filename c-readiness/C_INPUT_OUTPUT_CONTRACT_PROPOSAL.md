# C_INPUT_OUTPUT_CONTRACT_PROPOSAL — SuggestMapRequest / MapProposal 字段提案

> 状态:PROPOSAL(供团队评审;未冻结)。字段命名延续 ProjectMind 既有风格(Snapshot/CodeFacts/MapProposal,MVP_INTERFACES 已有 suggest_map(snapshot, code_facts) -> MapProposal)。

## 请求:SuggestMapRequest

```jsonc
{
  "base_revision":    "<40/64-hex 完整 SHA>",        // 比较基准(常=地图最后一次人工确认对应的 commit)
  "target_revision":  "<40/64-hex 完整 SHA>",        // 被评估的当前 commit(= Snapshot.revision)
  "changed_paths": [                                 // 来自 Git diff(与 A 的 /api/compare 同源)
    {"path": "app.py", "status": "modified"}         // added | modified | removed | renamed(+old_path)
  ],
  "code_facts": {                                    // B 的原始输出,revision 必须等于 target_revision
    "revision": "…", "files": […], "skipped": […]
  },
  "current_map": {                                   // 人工地图原文(nodes/edges 原样)
    "nodes": […], "edges": […]
  },
  "context_pack_id": {                               // 可选但强烈建议(CA 底座标识,非 CA 的 pack 引用)
    "schema_version": "0.1",
    "project_revision": "…",                        // 必须 == target_revision 或显式说明差异
    "registry_hash": "sha256:…"
  },
  "context_pack": { … }                              // 可选:直接内嵌 pack;C 只在 validate 通过后使用
}
```

约束:
- `base_revision`/`target_revision` 拒绝 HEAD/短 SHA(与 B 输入约定一致)。
- `code_facts.revision != target_revision` → 整个请求拒绝(suggest_map 既有约束)。
- `context_pack.project_revision != target_revision` → 拒绝或显式降级为"不使用 pack"(输出注明)。
- `changed_paths` 只接受与 Git diff 一致的内容;C 不自行跑 diff 以避免口径分叉(Stage 1 接收 diff 是 A 或调用方给的)。

## 响应:SuggestMapResponse

```jsonc
{
  "request": { "base_revision": "…", "target_revision": "…" },
  "proposals": [ MapProposal, … ],
  "unresolved":   [ {"subject": "…", "reason": "NEEDS_HUMAN_REVIEW", "evidence": […]} ],  // 有信号无定论
  "no_proposal":  [ {"paths": […], "reason": "comments_or_formatting_only"} ],            // 显式空结论(可审计)
  "limits": [ "code_facts skipped N files", "context_pack conflicts N (excluded)", … ]
}
```

## MapProposal

```jsonc
{
  "proposal_id":       "mp-<target_revision前8>-<序号|短hash>",   // 稳定可引用
  "subject":           "app.py",                                  // path 或 node id
  "kind":              "NODE_ADD",                                // 见下表
  "proposed_change": {                                            // kind 对应的载荷(全部是"建议值")
    "node_id":   "map-proposal",                                  // 新节点建议 id(新增时)
    "title":     "地图建议生成",
    "summary":   "…职责候选描述…",                                 // INFERENCE
    "entryPoint": "extensions/map_proposal/extension.py · handle()",
    "edge_from": "repository-snapshot", "edge_label": "消费版本"    // RELATION_ADD 时
  },
  "rationale":  "新增文件 + B facts 显示 3 个 class + 被 app.py import;地图无对应 node",
  "evidence": [                                                   // ≥1 条;可追溯链
    {"kind": "git_diff",   "revision": "…", "detail": "extensions/map_proposal/ added"},
    {"kind": "code_fact",  "revision": "…", "detail": "class MapProposalExtension @ line 12", "claim_id": null},
    {"kind": "map_node",   "detail": "nodes[] 无 entryPoint 含 map_proposal"},
    {"kind": "context_claim", "claim_id": "claim-…", "key": "…", "pack_revision": "…"}  // 用了 CA 才有
  ],
  "confidence":    "low|medium|high",
  "uncertainty":   ["responsibility inferred from filenames — human must confirm"],
  "status":        "PROPOSED",
  "human_required": true
}
```

## kind 枚举(按真实地图结构裁剪,共 7 种)

| kind | 载荷 | 触发信号(典型) |
|---|---|---|
| NODE_ADD | node 草案 | 新文件 + 声明事实,地图无对应 node |
| NODE_REMOVE_CANDIDATE | node_id | node 的全部 evidence path 在 target 中已删除 |
| RESPONSIBILITY_CHANGE | node_id + summary/entryPoint 候选 | entryPoint 函数消失/改名、文件职责大改 |
| RELATION_ADD | edge 草案(from,to,label) | 新增跨模块 import 连接两个已有 node 的 evidence 域 |
| RELATION_REMOVE_CANDIDATE | edge | 两侧文件间 import 全部消失 |
| IMPLEMENTATION_LINK_CHANGE | node_id + evidence[] 候选 | node.evidence[].path 改名/移动 |
| UNKNOWN | 自由描述 | 信号矛盾/证据不足 → 一律落 unresolved,不编 proposal |

注意:地图 node 还有 `position` 与 note —— **任何 kind 的 proposed_change 都不含 position**;`note` 字段仅当人工维护时使用。

## 状态机(proposal 侧)

PROPOSED → (human) ACCEPTED | REJECTED | DEFERRED。C 只产出 PROPOSED;ACCEPTED 后的地图写入是 A/人的流程,不属于 C。

## 不变式(实现必须保证)

1. 每个 proposal:evidence 非空,且至少一条 evidence 能定位到 (revision, path)。
2. `status` 恒为 PROPOSED;`human_required` 恒为 true。
3. 无 `changed_paths` 与 map/code_facts 交叉信号时返回空 proposals + 空 no_proposal 解释,不报错。
4. 输出字节级可复现:同输入 → 同输出(不嵌时间戳;生成时间由调用方记录)。
