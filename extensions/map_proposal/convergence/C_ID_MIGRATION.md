# C Convergence — Proposal / Node ID Migration Note (W5, R06/F10/D impact)

## 旧 ID 方案（被替换）

| 来源 | 旧方案 | 缺陷 |
|---|---|---|
| TEAM @3bd980de | `mp-<target8>-<顺序号>`；node id = 路径压缩（`a/b.py`→`a-b-py`） | 顺序号依赖遍历顺序；压缩路径可碰撞（X09 两个 service.py 同 id） |
| LOCAL @5058c54 | proposal 顺序编号；node id = basename 派生 | 同上；且引用不可回放 |

## 新 ID 方案（本分支）

- **proposal_id** = `mp-<target_revision 前 8 位>-<sha256([target, kind, subject, proposed_change 规范化 JSON]) 前 12 位>`。
  - 同一固定输入永远得到同一 ID（S26）；payload 变化 → 新 ID（旧候选不被自动覆盖）。
  - 顺序号不再出现在 ID 中；候选排序变化不影响 ID。
- **node_id（候选建议新增的节点）** = `mapnode-<sha256(完整 repo-relative path)>`，宽度从 10 位起，与现存 map 节点 id 冲突时确定性加宽（12/16/32/64/加盐）。
  - 冲突检查以请求传入的 current_map 现存 id 集为准。

## D / 调用方消费影响（不在 C 的 PR 内改动）

1. 旧 `mp-<seq>` / 路径压缩 id 引用不会自动映射到新 id；历史候选需要按 `(target_revision, kind, subject)` 三元组重新定位。
2. 旧 `candidates` 字段仍是兼容投影（K03），只包含已准入 canonical NODE_ADD；其内容不再独立生成，不能再用它旁路 canonical 审查。
3. prior_decisions（F20）按 `(subject, kind)` 匹配，与旧方案一致；subject 语义未变。
4. `proposed_change` 永不含 `position`（构造期强制）；`entryPoint` 仅在可辩护时给出（唯一顶层 class），否则缺省并由 uncertainty 说明。
