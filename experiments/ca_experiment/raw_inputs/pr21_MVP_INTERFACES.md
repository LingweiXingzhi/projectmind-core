# 比赛版最小接口约定

> 状态：下文 **IMPLEMENTED** 的 MVP 入口与独立扩展入口已合入 `core/main`；合入不等于团队已批准这个 SHA 作为正式共同开发基线。**PROPOSED** 的业务能力仍待实现。接口不仅是函数名，还包括输入约束、来源版本、错误、调用顺序和结果性质。本文是模块数据 Contract；四人职责只以 [协作约定](COLLABORATION_CONTRACT.md) 为准，不定义长期 Project Model Schema。

## 共同词汇与不变量

- **功能节点**是地图中有意义的项目部分；`node.id` 用于引用同一张图里的节点。它不强制等于文件、目录、语言 package 或某个类。
- **代码版本**为 Git 的完整提交 SHA（当前代码接受 40–64 位小写十六进制）；`HEAD` 只可在服务端读取当前状态时解析。跨人交接和已保存输出一律放解析后的完整 SHA，不放易变的 `HEAD`。**地图版本**当前没有单独的提交 ID 或摘要：地图从现时本地文件读取。`Snapshot.revision` 仅证明代码证据的版本，不能证明地图职责或关系属于该提交；后续须补地图身份与核查状态。
- **证据路径**是仓库内相对路径，使用 `/`；相同名字的不同本地仓库不能仅靠目录名认作同一仓库。当前响应只有 `repository: repo.name`，尚无跨机器稳定仓库 ID；团队交接需另写仓库地址/来源，暂不把目录名当身份键。
- **性质**必须区分人工演示图 `curated_demo`、`ai_candidate`、`temporary_unconfirmed_draft` 与将来的人审正式图。Git 变化只能产生“待复核”，不能产生“架构已变化”的断言。
- 证据和比较使用完整代码提交；地图当前另有未固定的本地文件状态，交接时应明确写 `mapRevision: UNKNOWN`。若 `Comparison.targetRevision` 和 `Snapshot.revision` 不同，调用者先重新获取或明确提示代码版本不一致。

## IMPLEMENTED：当前已存在的读写入口

启动：Python 3.10+；`python app.py` 在本机 `127.0.0.1:8765` 提供界面；`python app.py --repo <本地 Git 仓库绝对路径> --map <人工整理的地图 JSON 绝对路径>` 可以指向另一个本地仓库。外部仓库必须同时给 `--map`，当前不会自动生成图。启动时解析仓库根目录并校验地图；无效输入使启动失败。以代码 `app.py` 的 `resolve_sources` / `load_map` 为准。

### 地图输入与快照

人工地图文件顶层：`note: string, nodes: Node[] (至少 1 个), edges: Edge[]`。每个 `Node` 必需 `id/title/summary/entryPoint: string`、`position: {x:number,y:number}` 非负且有限、`evidence: [{path:string,reason:string}]`；`id` 在图内唯一。`Edge` 必需 `from/to` 指向已知节点 `id`、`label:string`。当前校验不保证 `evidence.path` 真存在；快照会以 `existsAtCommit` 报告。这是**输入格式**，不是已批准的正式架构格式。

`GET /api/snapshot` → HTTP 200 JSON：

```json
{
  "repository": "仓库目录名",
  "revision": "完整 Git SHA",
  "parentRevision": "完整 Git SHA 或 null",
  "branch": "当前分支名或 detached HEAD",
  "mapOrigin": "curated_demo",
  "mapNote": "人工地图备注",
  "nodes": [{
    "id": "功能标识", "title": "功能名", "summary": "职责描述",
    "entryPoint": "人工记录的关键入口", "position": {"x": 20, "y": 54},
    "evidence": [{"path": "app.py", "reason": "为何相关", "existsAtCommit": true}]
  }],
  "edges": [{"from": "功能标识", "to": "另一功能标识", "label": "关系说明"}]
}
```

`entryPoint` 和职责目前来自**当前本地人工地图**，不能仅凭 `existsAtCommit` 断言入口确实存在、关系已被代码证明或地图已经核查适用到 `revision`。`parentRevision` 在初始提交可能为 `null`。

### Git 证据与版本比较

`GET /api/evidence?path=<已在地图中声明的路径>&revision=<完整SHA>` → `{path, revision, content, truncated}`。内容来自指定 Git 提交，不读取工作区未提交文本；当前最多显示 12,000 个字符。路径未在地图声明 → 400；在该提交中缺失 → 404。调用者先从快照选路径和 `revision`；不能把工作区内容与提交内容混写。

`GET /api/compare?base=<完整SHA>&target=<完整SHA>` → `{baseRevision,targetRevision,changes,reviewCandidates,note}`。`changes` 每项为 `{code,path,oldPath?}`，重命名包含原路径；`reviewCandidates` 每项为 `{nodeId,changedEvidencePaths}`。候选只表示地图声明的证据路径与 Git 变化路径匹配；没有匹配不证明节点未受影响。客户端需保证目标提交与正在看的快照一致，或提示用户刷新。当前比较不是缓存式重新分析，也没有量化省 Token。

`GET /api/export?revision=<完整SHA>&base=<完整SHA，可省略>` → 带提交信息的 Markdown 下载；若提供 base，附比较摘要。此出口是交接摘要，不是正式图入库。

### 可选 AI 与临时布局

`GET /api/ai-status` → `{configured:boolean, model:string|null, note:string}`。只有在服务端设置 `OPENAI_API_KEY` 和 `PROJECTMIND_AI_MODEL` 才可用。

`POST /api/explain`，`Content-Type: application/json`，JSON `{base:<完整SHA>, target:<完整SHA>, nodeId:<快照节点ID>}`，请求体当前不超过 2,048 字节。成功 → `{status:"ai_candidate",model,nodeId,baseRevision,targetRevision,changedEvidencePaths,diffTruncated,explanation,note}`；`explanation` 含 `summary:string, observations:string[], possibleEffects:string[], unknowns:string[], evidencePaths:string[]`。只对节点声明且本次变化的证据路径取差异，发往模型的差异最多 12,000 字符；`evidencePaths` 只能引用这些路径。未配置、模型不可用或返回不合约定时失败，不应显示为已确认结论。当前实现可自动化验证请求形状，尚未在本机真实调用外部模型。

同一能力在本地 Python 里可调用 `explain_change(repo, map_path, base_ref, target_ref, node_id) -> dict`，有界 Git 差异在函数内部构造。它**不是**可复用的通用 `build_change_context` 模块：其他功能若想复用差异范围，先按当前接口调用或提出小型提取 PR；公共接线责任以 [协作约定](COLLABORATION_CONTRACT.md) 为准，不能各自复制一套 Git 选择规则。

前端“保存临时布局”写当前浏览器的 `localStorage`；“导出图草稿 JSON”得到 `{status:"temporary_unconfirmed_draft",note,exportedAt,repository,revision,mapOrigin,nodes,edges,comparison?}`。`nodes` 的 `position` 是拖动后位置；它不改变职责、节点或关系，也不自动写入 model 仓库。`comparison` 为 JSON 对象或 `null`。**当前导出不含 AI 解释，也不含独立地图版本**；另一位协同者不能仅凭它复核完整 AI 结论。同名本地仓库当前可能共用布局键，因此多仓库并行使用时需复核导出内容；这是待修缺口，不应把该键当跨仓库身份。

临时图目前**没有应用内 AI 审查接口**。用户可以把导出的 JSON 交给 AI 或队友分析，但这不等于 ProjectMind 已自动比较方案、识别冲突或保存审查结果。

HTTP 错误当前通常为 `{error:string}`；400 表示输入不合约定，404 表示缺失路径/页面，AI 服务错误为 502，部分 Git/文件错误为 500。调用者应根据 HTTP 状态处理，不依赖中文错误文案的字面内容；实现各路线的精确处理以 `app.py` 的 `make_handler` 为准。

### 独立扩展入口

`core/main` 已实现 `extensions/<功能名>/extension.py` 的自动发现、独立 HTTP 数据入口和可选独立页面。新增一个扩展只需修改自己的目录及测试；服务重启后主页侧栏自动出现入口。详情、错误行为和样例见 [独立扩展接口](EXTENSION_INTERFACE.md)。这是功能接入方式，CodeFacts、MapProposal、Handoff 的业务能力仍须分别实现和验收；它不会自动修改人工功能图。

## PROPOSED：下一轮新增能力的最小交换约定

以下字段只为当前并行开发提供数据交换边界，不是 Master Spec 的四层模型或永久 Schema。实现者需要在首个 PR 固定样例和错误行为。各扩展在自身目录实现功能、页面与 HTTP 数据入口；输出嵌入现有主图的职责见 [协作约定](COLLABORATION_CONTRACT.md)。

**接入状态：通用扩展路由与页面入口已经实现，下文 CodeFacts、MapProposal、Handoff 的业务函数仍是提案。** 已实现的 `Snapshot` 和 `Comparison` 是可读取的 JSON 交换面。可用 [同一份合成合约样例](MVP_CONTRACT_EXAMPLE.json) 独立开发和验证；该文件只用于测试交换形状，不代表仓库里真实存在 `src/entry.py`。各功能自己实现 `handle` 并调用自己的业务函数；现有路由的响应字段须保留，或明确提供兼容过渡。

### 地图来源补丁与跨请求一致性

在 `Snapshot`、`Comparison` 和两种导出中增加同含义的地图身份，例如 `mapSource: {kind:"local_curated_file", digest:"sha256:<64位摘要>", confirmedForRevision:null}`。`digest` 必须对本次实际读取的地图字节计算；`confirmedForRevision:null` 表示团队尚未核查适用版本，**即使地图文件恰好处在代码仓库中也不能自动改成提交 SHA**。比较基于另一份地图内容时，不可继续显示为同一次快照的“待复核节点”：实现可让服务端返回不匹配错误，或让界面强制刷新并提示，具体在 PR 固定。`Snapshot.revision` 仍只表示代码提交。此补丁的首个验收是“同一代码 SHA、改地图内容 → digest 改变且用户看到地图状态”。这比提前设计正式 model 仓库格式小得多。

### `collect_code_facts(repo, revision, paths=None) -> CodeFacts`

输入：已解析的本地 Git 仓库根目录、完整提交 SHA、可选的仓库相对路径列表。输出最少为：

```json
{
  "revision": "完整 Git SHA",
  "files": [{"path": "app.py", "language": "python", "entries": [
    {"name": "build_snapshot", "kind": "function", "line": 106}
  ]}],
  "skipped": [{"path": "unknown.bin", "reason": "未支持或不可读取"}]
}
```

`entries` 是在该提交中能核查的代码事实，允许为空；`line` 是该版本的 1 起始行号。首版可只支持一门在演示仓库实际使用的语言，其他文件进入 `skipped`；不能为满足图而猜造函数。输入路径不存在、提交无效时给明确错误，不在后台偷偷读取当前工作区。此输出不负责判断“功能模块”或建立全量调用图。用一个临时 Git 仓库的已知文本作独立验收。

### `suggest_map(snapshot, code_facts) -> MapProposal`

输入：同一提交的 `Snapshot` 和 `CodeFacts`；若 SHA 不一致，拒绝生成。输出最少为：

```json
{
  "status": "ai_candidate",
  "revision": "完整 Git SHA",
  "candidates": [{"title": "候选功能", "summary": "简述", "evidencePaths": ["app.py"], "unknowns": []}],
  "note": "待人复核，不覆盖人工地图"
}
```

初版可给一个稳定的“根据当前人工节点和代码事实补充候选说明”的例子，不要求自动构造整仓架构；若调用 LLM，仍需显式配置、限制输入、保留未知项。`evidencePaths` 必须从输入真实路径中选；若没有足够依据，返回空 `candidates` 与原因。先用本文固定样例独立测试，真实 CodeFacts 输出可用后再联调。候选不得写回 `data/project-map.json` 或正式 model 仓库。

`status:"ai_candidate"` 只用于确实经过模型生成的结果。首日可用可控模型响应验证接口；无可用模型时返回明确的未配置状态，不用规则结果冒充 AI。以后若增加纯规则候选，另标生成方式。

### `build_handoff(snapshot, source_locator, comparison=None, ai_candidates=None) -> Handoff`

输入：当前 `Snapshot`、明确提供的仓库来源 `source_locator={kind:"git_remote"|"local_path",value:<非空字符串>}`、可选 `Comparison`，以及可选的 `/api/explain` 原样成功结果列表；比较目标若不是快照 SHA，拒绝或显式返回不匹配。当前 `Snapshot.repository` 只有目录名，不能用它推算可在另一台机器打开的地址。本机路径交给别的电脑时可能不可用，接收者须按 `kind` 判断。最少输出形状：

```json
{
  "status": "handoff_draft",
  "repository": "仓库目录名",
  "sourceLocator": {"kind": "git_remote", "value": "调用者提供的仓库 URL"},
  "codeRevision": "完整 Git SHA",
  "mapRevision": "UNKNOWN",
  "mapOrigin": "curated_demo",
  "nodes": [{"id": "功能标识", "title": "功能名", "evidencePaths": ["app.py"]}],
  "changes": [{"code": "M", "path": "app.py"}],
  "reviewCandidates": [{"nodeId": "功能标识", "changedEvidencePaths": ["app.py"]}],
  "aiCandidates": [],
  "unknowns": ["地图尚未标记核查适用版本"],
  "nextCheck": "按代码提交和证据路径复核"
}
```

没有比较时 `changes`、`reviewCandidates` 为空列表；传入 AI 解释时 `aiCandidates` 中保留原 `status:"ai_candidate"`、来源路径和 `explanation.unknowns`，不能凭空生成。地图身份补丁完成后，`mapRevision` 应升级为实际 `mapSource`，但未确认适用的状态仍保留。不得加入没有来源的“正式架构已确认”字样。用非作者在新会话读包后回答“代码证据对应哪个提交、地图版本是否已核查、哪个节点待复核”作为验收；扩展页面可提供独立下载，主图导出按钮的共享改动按 [协作约定](COLLABORATION_CONTRACT.md) 处理。

### 后续提案：`review_draft(draft, reference_snapshot) -> DraftReviewCandidate`

仅在团队决定把“导出后交 AI 分析”接入应用内时实施。输入为导出的 `temporary_unconfirmed_draft` 和供对照的当前快照；先检查仓库来源、代码提交与地图状态是否可比。输出仍是 `ai_candidate`，最少列出**可从两份图直接观察的节点/关系差异**、可能后果、证据节点 ID 和不能判断之处；对不一致版本先返回“不可比较”，不能把临时拖动位置当架构依赖改变。它不写正式图。当前没有这个函数、HTTP 路由或任务责任人；不能把此提案当作首日隐藏任务。

## 改动与验收

每个新增模块的 PR 附上固定输入、实际输出、错误样例、只针对公共接口的必要测试和接入方式。字段含义或版本约束改变时先按 [协作约定](COLLABORATION_CONTRACT.md#5-接口变更办法)通知使用者；扩展路由按已实现的约定自动接入，各业务接口通过验收后才更新本文件的 `IMPLEMENTED` 状态。当前已实现出口不会因为本提案而自动改变。
