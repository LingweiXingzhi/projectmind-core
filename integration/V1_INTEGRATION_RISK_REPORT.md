# V1_INTEGRATION_RISK_REPORT — B / D / CA(以及 A)跨模块只读审计

- 审计人:独立验证 Agent,2026-10-03;只读,不修改任何分支
- 对象:PR #22/#31(B)、PR #26/#27(D)、PR #29(CA)、main(A);扩展名、文件所有权、schema 术语、revision 语义、概念重复、共享核假设

## 总评

**没有发现会阻止各自合并的硬冲突**(扩展目录名全部唯一、SHA 语义一致、POST 限额一致)。风险集中在三类:**概念重复(三套"建议/候选"机制)、契约证据漂移(B 的 PR31)、PR 覆盖盲区(CA registry 只登记 21/22)**。

## 逐项结论

| 维度 | 结论 | 详情 |
|---|---|---|
| endpoint collision | **无** | 各扩展走 `/api/extensions/<name>`,name 唯一:project_summary / context_authority / code_facts(PR31) / continuity+handoff+worklog(PR27);未来 map_proposal 亦唯一 |
| file ownership collision | **无直接冲突;1 处包含关系** | PR27 分支包含 PR26 的 worklog 全部 5 文件(分支继承,#27 self-declared "继承 Handoff 731135b 与 Worklog 9b3d333")。**合并顺序约束:#27 应在 #26 之后(或替代 #26)合并**,否则 worklog 出现两套历史;PR #24(#23-handoff-draft)是 #27 的祖先,同理 |
| extension naming | **一致** | 全部符合 host ID_PATTERN(小写字母开头 ≤40);无同名 |
| schema naming drift | **低风险,两处约定不一** | CA 用 `schema_version:"0.1"`;D 用 `FORMAT:"projectmind-continuity-v1"`;B 无显式 schema 版本(README 承载)。建议 V1 统一为 `schema_version` 字段+语义化版本;另外 "draft" 一词三义(D 的 checkpoint 状态 draft / GitHub PR draft / CA 无此概念),C 文档已要求消歧 |
| revision semantics | **一致(强项)** | 40/64-hex 完整 SHA 正则在 A(app.py)、B(facts.py SHA_PATTERN)、D(handoff.py SHA)、CA(context_pack.py REVISION_PATTERN)四处**逐字相同**;都拒绝 HEAD/短 SHA;B 与 D 都遵守"不自动 fetch 对象" |
| duplicate concepts | **最重要风险** | 三套"建议/候选"机制并存:①A `/api/compare` 产出 `reviewCandidates[{nodeId,changedEvidencePaths}]`(地图证据路径命中变化的待复核标记);②D 把 reviewCandidates 原样装进交接包;③C 即将产出 MapProposal。三者是同族概念(候选→人工裁决)但数据结构/生命周期/存储位置都不同。**建议:C 的 proposal 模型向后兼容 reviewCandidates(或明确映射),否则统一 UI 时会出现三个"待办"入口** |
| status terminology | **中等风险** | PR 状态:PR_OPEN/CLOSED/MERGED(CA)+ GitHub draft(FINDING-07,CA 不读);claim 状态:ACTIVE/STALE/SUPERSEDED/CONFLICTED(CA 派生);D checkpoint:draft/ready/receiving/active/blocked/completed(中文标签)。没有冲突但聚合展示时需要一张统一状态映射表(见 UI IA 文档) |
| UI fragmentation | **高(已立项审计)** | main 有 6 个扩展页 + 主图;PR 合并后约 8 个扩展页,各自独立 index.html,无统一导航/状态语言 → 见 UNIFIED_UI_INFORMATION_ARCHITECTURE.md |
| shared-core assumptions | **一致** | 都依赖 ExtensionContext(repo/map_path/snapshot()/compare())与 EXTENSION_INTERFACE(64KB POST、400/500 错误语义);D 的 MAX_PACKAGE=12MB 是本地文件存储,不与 POST 限额冲突;无人写共享文件(app.py/web 零改动)✓ |
| PR 覆盖盲区 | **中等** | CA registry 只登记 pr_21/pr_22 head;PR24/26/27/29/31 无 claim。**具体影响:B 的 PR31 正在改变 code_facts 行为(--no-lazy-fetch、partial-clone 显式报错、移入正式目录、新增 SHA-256 仓库测试),而 CA 的 contract.code_facts_shape 证据仍钉 PR22 README@0c46747**。若 PR31 先于 PR29 合并,B 契约 claim 的 evidence 立即过期——需要 registry 追加 supersedes claim(设计上支持,尚无人做) |

## 建议动作(按优先级)

1. **合并顺序记入 PR 描述**:#26 →(或 ←)#27;#24 与 #27 二选一或明确 #27 包含 #24。
2. **PR29 合并前/后立即追加 B 契约的 PR31 跟进 claim**(append-only + supersedes,CA 已支持,无需改代码)。
3. **CA verifier 加 draft 字段**(FINDING-07,schema 0.2 事项)。
4. **统一"候选"概念模型**:C 的 MapProposal 设计时把 reviewCandidates 作为输入/映射目标(本报告 + C_INPUT_OUTPUT_CONTRACT_PROPOSAL 已预留)。
5. UI 聚合前先做状态术语映射表(见 UNIFIED_UI_INFORMATION_ARCHITECTURE.md §3)。
