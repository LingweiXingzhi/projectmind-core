# C_PRODUCT_BOUNDARY — Map Proposal 的产品边界

## C 是什么

一个**建议生成器**:观察"代码变了什么"与"地图说了什么"的差异,产出结构化的 Map Proposal,供人工复核后更新正式 Project Map。它是 A(Core/Integration)与 B(Code Facts)之上的第三层,消费两者的产物,不反向修改它们。

## C 做什么

1. 读取 pinned revision 的 Git diff(哪些文件增删改/改名)。
2. 读取 B 的 Code Facts(声明级:path/name/kind/line/skipped)。
3. 读取当前 Project Map(nodes/edges)与 Context Pack 的 current/contracts/proposals。
4. 产出 proposals[]:node/relation 草案,每条带 evidence 链与 confidence/uncertainty。
5. 对证据不足的差异输出 UNKNOWN / NEEDS_HUMAN_REVIEW 条目(而不是沉默或猜测)。

## C 不做什么(硬边界)

| 禁止 | 理由 |
|---|---|
| 写/改 Project Map 任何文件(node 增删、edge 改、position 动) | 地图是人工维护的正式资产;README 明确布局仅是查看位置;map 无版本身份,自动写会破坏可追溯性 |
| 修改 app.py / extension_host.py / web/ / 其他扩展 | A 的领地;C 以独立扩展 `extensions/map_proposal/` 存在,遵循 EXTENSION_INTERFACE(handle + 可选页面) |
| 把 proposal 直接标为 ACCEPTED/MERGED | proposal 生命周期只到 PROPOSED/REJECTED/ACCEPTED(by human);C 不自行翻转状态 |
| 依赖图/调用图/架构判断当事实输出 | B 明确不提供 dependency graph;C 对"职责/关系"的判断永远是 INFERENCE |
| 用 RESEARCH/PROPOSAL/HISTORICAL/Stale 资料当现行事实 | pack 的 do_not_assume;poisoning 实证这类污染最危险 |
| 在无 evidence 时生成强结论 | §21 防幻觉约束;无证据 → UNKNOWN |
| 实现 mapSource/版本身份写回 | 那是 map_source_patch 提案的领地(PROP OSED,未接受);C 只读地图,不认证地图 |
| 输出人名/人员任命类推断 | A/B/C/D 是责任位不是人员 |

## 与 V1 其他角色的接口边界

- **A**:C 以 `extensions/map_proposal/extension.py` 接入 ExtensionHost(A 不需要改 core);建议输出走 C 自己的页面/API + 可选导出 JSON;A 未来可以把 proposal 列表渲染进主图待复核区(由 A 决定)。
- **B**:C 调用 code facts 扩展的公开函数/HTTP 接口,读 revision/files/skipped;**C 不复刻 B 的解析逻辑,不绕过 skipped 语义**;`CodeFacts.revision == Snapshot.revision` 必须核对。
- **D**:C 的 proposal 导出格式应可被交接包引用(proposal_id 稳定、可引用),但不依赖 D 的实现。
- **CA**:按 C_CONTEXT_AUTHORITY_USAGE.md 消费;CA 不为 C 的推断背书。

## 成功的最低定义(V0.1)

对一个 pinned revision 的真实 diff,C 能:(a) 对"新增文件/新增跨模块 import"给出 ≥1 条证据完整的 proposal;(b) 对"仅注释/格式/内部重构"输出 NO_PROPOSAL 而不是编造;(c) 对证据不足的信号输出 NEEDS_HUMAN_REVIEW;(d) 全程零写入正式地图。
