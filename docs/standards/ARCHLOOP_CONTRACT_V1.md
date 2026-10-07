# CONTRACT_V1 — 架构认知闭环共享契约（A 起草）

版本：CONTRACT_V1_DRAFT（冻结于开发分支提交 36dbc14 之后的固定 SHA；本文件为 B/C/D 对齐用草案）
起草：A 执行器（ZCode, RUN_ID ZCODE-ARCH-20261007-130829-60B）
依据：`ProjectMind_架构认知闭环_ABCD完整任务书_2026-10-07.md` 共同产品与数据约束 §8/§9。

## 1. 版本身份（六字段分离，全部强制出现在交换面）

| 字段 | 含义 | planning 模式 |
|---|---|---|
| workspaceId | 工作区稳定 ID（`ws_<ts>_<hex6>`） | 必填 |
| codeRepoId | 稳定仓库身份（`repo-<sha256[:16]>`，由 root+remote 哈希；不用目录名） | 必须 null |
| mapId | 图身份（已有项目默认 `map-<codeRepoId后缀>`） | 可 null |
| codeRevision | 代码完整 Git SHA（40–64 hex） | 必须 null |
| mapRevision | 规范化语义图内容的不可变哈希（`maprev-<sha256[:40]>`；布局不计入） | 可产生 |
| mapSourceRevision | 架构仓库保存图的 Git 完整 SHA；未入库 null | null |
| verifiedCodeRevision | 确已人审核查的代码 SHA；局部批准不得宣称全仓 verified | null |
| draftRevision | 草稿 CAS 修订（mapRevision+随机后缀，每次写更新） | — |

设计确认（confirmed_design）≠ 已实现（implemented）≠ 代码核查（verified）。

## 2. 图 schema（最小集）

节点：`id`（稳定，重命名不换身份）、`title`、`summary`（职责）、`status ∈ {candidate, confirmed_design, implemented}`、`provenance ∈ {code_fact, ai_candidate, human_input, rule_based}`、`entryPoints[]`、`interfaces[]`、`evidence[]{path, reason, kind ∈ {code_fact, requirement, unknown}}`、`process[]{stepId, title, detail, inputs[], outputs[], branches[], next[]}`。
关系：`from/to`（节点 ID）、`type ∈ {static_reference, functional_collaboration, expected_sequence}`、`label`。
过程是"期望执行过程"，不是从代码推断的运行轨迹；stepId 稳定，重排不丢身份。

## 3. 操作（operations）——直接编辑、纠正预览、C 提案共用

`add_node{node}` / `update_node{nodeId, fields ⊆ {title,summary,status,entryPoints,interfaces,evidence}}` / `remove_node{nodeId, force?}`（有引用时需先展示影响）/ `add_edge{edge}` / `update_edge{match{from,to,type}, fields}` / `remove_edge{match}` / `update_process{nodeId, process}`。
apply 时以 `expectedDraftRevision` CAS；不一致返回 `REVISION_CONFLICT`（HTTP 409）。

## 4. 错误字典（machine code，中文文案仅展示用）

BAD_REQUEST / VALIDATION_FAILED(400) · NOT_FOUND(404) · STALE_CONTEXT / REVISION_CONFLICT / EVIDENCE_MISMATCH(409) · BACKEND_UNAVAILABLE(503) · DEV_SAMPLE_DISABLED(403) · AI_NOT_CONFIGURED / NOT_RUN_AWAITING_CONFIGURATION(503) · AI_GENERATION_FAILED(502) · FORBIDDEN_ORIGIN(403)。

## 5. HTTP 面（A 拥有；loopback Host + 同源 Origin 校验；写操作全部 JSON POST）

| 路由 | 方法 | 语义 |
|---|---|---|
| /api/archloop | GET | 服务与 adapter 状态 |
| /api/archloop/sample-graph | GET | 标注的演示样例图 |
| /api/archloop/workspaces | GET/POST | 列表 / 创建 |
| /api/archloop/workspaces/{id} | GET | 打开（含身份+草稿） |
| .../generate | POST | 生成候选（production→AI；dev_sample→须带 sampleGraph） |
| .../apply-candidate | POST | 用户确认后候选→草稿 |
| .../apply-ops | POST | CAS 草稿操作 |
| .../correction-preview | POST | 自然语言纠正预览（origin 标注） |
| .../diff | GET | 基准候选→当前草稿差异 |
| .../impact?nodeId= | GET | 删除影响 |
| .../review | POST | 人审决定（expectedMapRevision+actor+reason） |
| .../recheck | GET | 代码变化复核（staleNodes） |
| .../fix-task | POST | 修正实现任务（D seam） |

## 6. 对 B 的接线请求（persistence capability）

需要：open_workspace / create_draft / apply_draft_operations / record_review / publish_reviewed_graph / get_version / export_version。
当前 A 端行为：真实来源（非 dev_sample）草稿提交 review 时，先记录决定（delivery=recorded_locally_pending_b_backend），再抛 BACKEND_UNAVAILABLE；dev_sample 来源直接 DEV_SAMPLE_DISABLED(403)，任何模拟人审不得产生版本。
B 交付时提供固定 HEAD + 本契约第 1/2/3/4 节字段映射差异（如函数名不同请给映射表），A 以 adapter `register("persistence", backend)` 接入，不改前端。

## 7. 对 C 的接线请求（correction capability）

需要：correction_preview(baseMapRevision, graph, instruction, selectedNodeIds) → {operations[], diff, note, origin:"c_backend"}；增量提案接 B 版本图。当前 dev_sample 预览为本地确定性规则（明确标注"演示纠正预览 · 非真实 AI 输出"）。C 交付后 adapter 切换，前端零改动。
真实 AI transport：`archloop.ai_transport.call_model(instructions, payload, schema_name, schema)`（从 app.py explain 提取，语义保持）；未配置时返回 NOT_RUN_AWAITING_CONFIGURATION，不伪造候选。

## 8. 对 D 的接线请求（handoff capability）

需要：create_fix_task(workspaceId, deviation, expectedProcessRef, evidence, acceptance) → FixTask（结构化、带 mapRevision 与验收）；同版交接包接 B 版本身份。当前 fix-task 在 dev_sample 模式返回标注样例任务。D 的 T01–T28 验收工具就绪后 A 提供一条命令运行入口。

## 9. 安全与诚实边界（不变量）

- 生产路径后端缺失 → BACKEND_UNAVAILABLE；样例只在显式 dev_sample 模式且全程带 `origin: "dev_sample"` / "演示数据" 标注；模拟人审永远不能产生版本。
- 真实外发 AI 只用已配置服务端 transport；密钥不出服务端、不入日志。
- 新写端点全部 loopback/Origin 校验；确认操作绑定 expectedMapRevision。
- 布局位置不入 mapRevision；拖动不产生新图版本。
- AI 未配置时如实返回 NOT_RUN_AWAITING_CONFIGURATION；规则候选标 rule_based，不冒充 ai_generated。
