# B 双面接口实现与接入说明

日期：2026-10-07；状态：B_IMPLEMENTATION_CANDIDATE / A_REVIEW_PENDING。
公共合同仍未冻结。本实现为可选的 Python 包装，不注册公共 HTTP，保留 V1。
现有 TWO_SURFACE_INTERFACE_V2_DESIGN.md 是设计阶段历史；以本文件区分已实现能力和待协调项。

## 已实现的两面

`UserWorkspaceAPI` 由 A 的可信服务端建立，绑定一个实际 workspace/map。
所有调用（包括读取）要求 Gateway 的真实 peer/Host/Origin、本机会话、CSRF。
`CollaborationAPI` 由服务端绑定工作区、C/D 角色和明确允许的正式版本集合。
传入另一个 workspace/map/revision 不扩大范围。
这些对象限定可调用能力，不隔离同一 OS 账户下的任意代码执行，不是多用户 RBAC。

| 面 | action | 行为 |
|---|---|---|
| A 操作面 | openWorkspace / readView | 打开已绑定工作区、显式推进固定代码 SHA；分别返回当前代码与正式认知 |
| A 操作面 | prepareDraft | 手动初图或明确选择的 C bootstrap；始终创建未确认草稿 |
| A 操作面 | saveDraft | 手动编辑或候选选择；CAS、操作、候选固定和选择审计原子保存 |
| A 操作面 | restoreAsDraft / associateCode | 恢复历史为新草稿；规划显式关联代码进入 mixed |
| A 操作面 | previewReview / confirmReview | 实际 before/after、覆盖与拒绝理由；绑定会话和预览 |
| A 操作面 | publishVersion / publicationStatus | 同会话使用服务端原授权发布/重试；最小状态投影 |
| A 操作面 | importExactVersion | 仅登记来源、完整固定版本引用；读取真实 Git 包核对后 CAS 导入 |
| C 协作面 | readContext / validateProposal | 只读上下文、候选结构与 basis 校验；不写草稿、不确认 |
| C/D 协作面 | readExactVersion | 只读服务端授权的精确正式版本，完整包不改写 |
| D 协作面 | exportExactVersion | 导出允许的原包；不拥有导入、编辑或人审入口 |

## 服务端建立对象

先通过 WorkspaceService 打开 planning 或登记的固定代码仓库工作区。
然后受信服务端创建 `UserWorkspaceAPI(service, gateway, workspaceId)`。
需要接收 D 导入申请时，额外配置 `source_registration_id`；它只对应该 service 的
已配置独立架构 Git 仓库，JSON 不能指定磁盘路径或任意 URL。

C/D 使用 `CollaborationAPI(service, workspaceId, role="C"|"D",
allowed_map_revisions=(...实际允许的 mapRevision...))`。
正式版本发布后，由服务端重新签发允许该版本的对象；请求不能自行扩大版本列表。
C 的 readContext 在当前正式包未获允许时拒绝，不能用“当前”绕过授权。
角色与范围来自服务端构造参数，不来自 worker 的 JSON 自报。

A 调用：`api.call(action, request, auth=trusted_metadata)`。
C/D 调用：`api.call(action, request)`。
每个 request 含 `apiVersion="b-surfaces-v2-candidate"`、稳定 `requestId`。
成功返回 apiVersion/requestId/status/context/data；失败返回机器错误与可安全返回的 currentContext。
`requestId` 是关联标识，不让重复编辑自动幂等；超时先读实际 revision/operationId。
新 facade 不接受 A 草案的 actor-only publish，也不自报 CONTRACT_V1 已接通。

## 请求字段

所有写 context 都是实际八字段：workspaceId/mapId/mode/codeRepoId/codeRevision/
baseMapRevision/draftId/draftRevision。planning 无代码；existing_project/mixed 必须完整 SHA。
没有草稿时 draftId/draftRevision 都为 null。

| action | apiVersion/requestId 之外的字段 |
|---|---|
| readView | 可选 draftId |
| openWorkspace | context（无草稿），可选 targetCodeRevision |
| prepareDraft | context（无草稿）、graph、origin；候选路径还需 proposal/selectedCandidateId |
| saveDraft | context、operations；候选路径还需完整 proposal/selection |
| restoreAsDraft | context（无草稿）、mapRevision |
| associateCode | context（无草稿）、codeRepoId、codeRevision |
| previewReview | context、reason、coverage、limits、verifyCode |
| confirmReview | context、previewId、previewDigest、decision=accept/reject |
| publishVersion | context、reviewId |
| publicationStatus | draftId |
| importExactVersion | context（无草稿）、sourceRegistrationId、完整 versionRef |
| C readContext | 可选 draftId |
| C validateProposal | context、proposal |
| C/D readExactVersion；D exportExactVersion | 完整 versionRef |

versionRef 六字段：codeRepoId/mapId/codeRevision/mapRevision/mapSourceRevision/verifiedCodeRevision。
其中 verifiedCodeRevision 是期望比对值，实际字段来自读取的不可变 Git 包。
发布后原 draft 的 baseMapRevision 保留旧基线，新正式引用单独返回。
旧草稿与新代码不同则标 contextCurrent=false/canEditThisDraft=false，不偷偷改旧证据。

## 候选选择与原子审计

候选正文含 apiVersion/proposalId/kind/basis/generation/candidates/unknowns/proposalDigest。
generation 使用 source=rule_based|ai_generated、runId、fixtureOnly。
bootstrap 候选含 graph 且 basis 无草稿；patch 候选含有稳定 operationId 的 operations。
摘要对去掉 proposalDigest 的规范正文计算，仅校验内容一致性，不认证作者。

每个 patch 候选必须决定一次，接受/修改要覆盖整组操作；拒绝项必须有理由且没有实际操作。
接受保留原全文/来源。修改保留 operationId/op/目标 id/processId，source=human；
新增对象仍保留 value.id。改变操作种类或目标需要拒绝原项，另行保存人工新操作。
组内相对顺序保持；组间依赖顺序由实际操作列表明确给出。
实际操作集合必须恰好等于已选集合。额外人工编辑走独立 saveDraft。

新的 service.create_candidate_draft / apply_candidate_selection 在同一 SQLite 事务内
固定原候选、写草稿和审计记录；图/引用/真实证据失败整批回滚，不留下半份候选记录。
同 workspace 内同 proposalId 原文不可替换。
C patch 的 proposalId 标识该次候选，draft.proposalId 保留 V1 草稿来源身份，二者可不同。
新的选择摘要保存在草稿；拒绝记录从存储读出加入真实审核，不接受浏览器自报拒绝清单。
全拒绝也保存选择审计、增加一次 draftRevision、使旧审核失效，图内容保持。
每草稿累计拒绝项上限 128，与原审阅入口一致；超限在写入前原子拒绝，保留此前审计。

旧不可变 version 包与 semantic hash 字段不变。V2 原候选/选择摘要未加入 D 的正式包，
完整离线候选前后追溯协议仍需 A/C/D 冻结；D 原包已有 appliedOperations/rejectedCandidates。

## 审阅与恢复

浏览器只拿 previewId/reviewId；facade 的引用到授权绑定保留可信服务端内存。
底层 V1 私有 SQLite intent 为内部幂等重试保存原授权响应；数据库权限为 0600。
这些值不进入浏览器操作响应、版本包或公开运行证据；不声称本机数据库没有令牌。
这些引用必须配合原有效会话，不能转交给同名 actor 的另一会话或 C/D。
编辑会使旧预览失效；publishing 冻结原决定/草稿并只继续原事务。
原有效会话可明确重试，Git commit 中断仍使用 V1 恢复机制。
过期预览和授权缓存会清理，每个 surface 有 128 项上限。

服务重启/会话失效后内存授权消失，publicationStatus 返回 awaiting_trusted_recovery。
不从数据库授权记录、actor、reviewId 或原日志恢复发布权；保留现场。
跨会话明确恢复的权限和存储方案待 A 确认，未实现 resume/reset/重新批准冻结事务。
本轮不把“恢复可见”说成“重启后可自动发布”。

## 当前公共接入差异

见 AC_ALIGNMENT_2026-10-07.md。A/C 的新分支已经存在，其合同是 DRAFT。
图结构、代码/图身份、草稿修订、人审授权及 C dispatch 尚有不同。
本轮可在 B 自身真实 Git、真实 SQLite 和测试 HTTP 适配器运行；
A 共享工作台、真实 C 推理、D 产品交接与新的全链路验收仍需三方接线。
测试人审只批准合成 fixture，不替真实负责人批准 ProjectMind Model。

Project Model Impact：MINOR（B 职责内包装/原子候选审计，既有责任边界不变）。
正式 Model 未修改；初交付 UPDATE 建议仍待人工批准。

## 可复现的独立演示

```sh
python -m extensions.architecture_workspace.surface_smoke --test-fixture-only --output /absolute/new/surface-fixture
python -m unittest tests.test_archloop_b_surface_http -v
```

第一条生成 SURFACE_SMOKE.json：21 次实际新 facade 调用、17 个断言、同版双 clone、
planning→设计批准→关联代码→mixed 新草稿。它会创建全新的合成仓库，不能用于真实项目批准。
未标测试、目录已存在、相对输出或仓库内输出都拒绝，不覆盖已有工作。

fixture_http.py 只在专用 example.invalid 合成代码仓库和测试架构分支建立临时
127.0.0.1 随机端口，测试真实 socket、Cookie/Header、同源和防伪检查；不注册 Core 或提供 UI。
它固定 TEST_ONLY_SIMULATED_HUMAN，不把 body actor 当用户身份。
会话端点需要返回浏览器使用的 CSRF 值；运行证据不保存会话/防伪/原授权令牌。
这证明 B 测试适配器可用，不能等同 A 的实际公共工作台接通。
