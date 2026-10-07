# B 的 CONTRACT_V1 版本部分候选

状态：B 可运行工程合同；A_REVIEW_PENDING。新 task scope 优先于旧 MVP B parser 分工。
公共文档由 A 修改。命名/样例冲突交给 A 统一，不各自更改公共字段。

## 身份

| 字段 | 含义 |
|---|---|
| workspaceId | 本地工作区稳定 ID；planning 无 repo 也有此 ID |
| codeRepoId | 服务端登记的代码来源身份，不是目录名 |
| mapId | 跨版本、跨客户端的稳定图身份 |
| codeRevision | 完整小写 40/64 位代码 Git commit SHA，planning 为 null |
| draftRevision | 正整数 CAS，包含布局修改 |
| baseMapRevision / expectedMapRevision | 草稿/审核所依据的当前正式图摘要；首次为 null |
| mapRevision | sha256:64 位规范化语义身份，正式版本不可变 |
| mapSourceRevision | 实际架构 Git commit SHA，仅在 provenance envelope |
| verifiedCodeRevision | 明确人审核查覆盖的代码 SHA，未核查/纯规划为 null |

不同版本导出不能混用。C/D 消费 `{version, provenance}`；
当前查看代码在 graph_snapshot.workspace，正式版本的 codeRevision 和
verifiedCodeRevision 留在 versionEnvelope 中，三者分开显示。

## 最小图

`schemaVersion="architecture_graph_v1"`，nodes/edges/evidence/processes 均为数组。
完整可运行样例：smoke.py 的 graph()，真实输出：FUNCTION_SMOKE.json。

- node：id/title/responsibility/implementationStatus/interfaces/evidenceIds。
  implementationStatus 为 unknown/planned/implemented，规划不能 implemented。
- interface：id/name/kind/description/evidenceIds；kind=code_entry/team_contract。
- edge：id/from/to/type/label/evidenceIds；
  type=static_reference/functional_collaboration/expected_order。
- evidence：id/kind/reason。code 还含 path/codeRepoId/codeRevision、
  可选 lineStart/lineEnd/unknownReason。user_goal/user_constraint 含 content；
  unknown/observation 含 content 与 unknownReason。旧版本代码必须标未知原因。
- process：id/title/kind="expected"/steps/evidenceIds。
- step：id/nodeId/title/inputs/outputs/condition/branches/nextStepIds/
  allowedFailures/evidenceIds；branch=condition/nextStepId，步骤引用在本过程内。

同类对象 ID 唯一；接口、步骤 ID 在图内唯一。节点与证据使用独立命名空间。
新增对象缺 ID 时由操作服务分配；C 候选提供 ID 时校验并保留。
接口和证据引用必须存在；目录遍历、绝对路径、符号链接代码证据拒绝。
规范化 JSON 上限 2 MB、单批 128 操作、单文件证据核查上限 1 MB。
超限受控失败；A 的 HTTP body/context/token 上限另由其公共 transport 实施。

## Python 入口

| 函数 | 最小调用与输出 |
|---|---|
| open_workspace | mode/code_repo_id/code_revision；已有 workspace_id 可重开/显式推进代码 SHA → workspace |
| create_draft | workspace_id, graph 或 legacy 或 from_map_revision（三选一），base_map_revision, origin, proposal_id → unconfirmed draft |
| apply_draft_operations | draft_id, operations, expected_draft_revision, base_map_revision, proposal_id → 更新后的 draft |
| record_review | 仅 Gateway 确认后调用；draft_id、confirmation_token、preview_digest、decision、expected_draft_revision、expected_map_revision、proposal_id、code_repo_id、code_revision → reviewId/decision/publicationToken |
| publish_reviewed_graph | draft_id、publication_token、expected_map_revision → 不可变 version/provenance；失败不是正式版本 |
| get_version | workspace_id、map_revision → 原 version/provenance |
| export_version | 同 get_version → 同一版本包，不偷换 HEAD |

辅助：get_draft、graph_snapshot、associate_code、import_git_version；
最后一个在第二 clone 对实际架构 Git commit 读包并验证后持久导入新数据根。
architecture repo/source SHA 必须服务端配置/校验，不接受客户端任意路径。

操作：node/edge/evidence/process/step 的 .add/.update/.remove，
step.reorder（processId/value=完整 step ID 顺序），layout.set。
更新指定 id 与 changes；id 不能改变。add.value 可以缺 id。
operationId 可省略由服务分配，source=human/ai_generated/rule_based；
缺省 source=human 只记录编辑来源，绝不构成批准。
批次原子校验；坏引用时全部回滚，无隐藏级联。

## A 人审调用顺序

1. 服务端按固定配置创建 service/Gateway，并隔离 worker 权限。
2. 从真实 peer/Host/Origin 创建本机会话；操作者为声明身份。
3. preview_review：auth(session_id/csrf_token/peer/host/origin) +
   reason、expected_draft_revision、expected_map_revision、proposal_id、
   code_repo_id/code_revision、coverage、limits、verify_code、rejected_candidates。
   coverage={scope:all|partial,nodes,edges,processes,evidence}，对象 ID 明列。
   rejected_candidates 每项 proposalId/candidateId/reason；仅记录未应用候选，
   不得把“拒绝”显示成已从图移除。手动修正见实际 appliedOperations。
4. 展示返回 beforeGraph/afterGraph/appliedOperations/rejectedCandidates、
   previewDigest 和 coverage。令牌默认 300 秒，最多 600 秒。
5. 人显式确认：Gateway.confirm_review(auth, 上述固定身份、
   confirmation_token/preview_digest/decision=accept|reject)；
   accept 产生独立 publicationToken，reject 不产生发布权限。
6. 用该令牌调用 publish_reviewed_graph；A 的发布 HTTP 同样必须会话防伪。
   后台候选路由不取得 Gateway/令牌，不能自行批准、发布。

相同确认重试返回原响应；同令牌换决定为 REVIEW_REPLAY。草稿、图、代码、
会话或实际预览改变则拒绝。发布进行中冻结草稿/版本推进，可在新进程用原
发布授权恢复；不向客户端暴露底层 intent/permit/journal 内容。

## C / D

C 只读 graph_snapshot 和 CA/代码事实；保持 codeRepoId/完整 SHA 一致。
新候选操作带 B proposalId 和 baseMapRevision/expectedDraftRevision，
不能覆盖人审正式版本。AI 初图的生成 provenance 由 C 提供并负责真实性，
测试替身明确标 fixture，不声称真实 API 已调用。

D export_version 取得三种版本身份、confirmation/coverage/limits；
在第二架构 clone 固定 source commit 读取/校验，然后 import_git_version。
Git 字节校验不认证审核人，不自动核查新代码。FixTask / 实施提交回挂、
主线 T01–T28 和 D 验收工具仍由 D 实现。

## 错误字典与正常/冲突样例

WorkspaceError.as_dict() → `{error:{code,message}}`。完整列表见 errors.py。
稳定常用映射建议：INVALID_INPUT 400；NOT_FOUND 404；
REVISION_CONFLICT/STALE_CONTEXT/EVIDENCE_MISMATCH/REFERENCE_CONFLICT 409；
HUMAN_REVIEW_REQUIRED/REVIEW_EXPIRED/REVIEW_REPLAY/REQUEST_FORBIDDEN 403；
PUBLICATION_FAILED/STORAGE_FAILED 503。A 冻结 HTTP 合同后由其实现状态映射。

smoke.py 实际产生正常包以及三种错误，均可重现：

| 机器码 | 实际触发 |
|---|---|
| REVISION_CONFLICT | 已保存 revision=2，另一客户端仍提交 expectedDraftRevision=1 |
| STALE_CONTEXT | 用同一预览令牌提交另一 codeRepoId |
| EVIDENCE_MISMATCH | code 证据引用 ../private |

不要依赖中文 message 分支。旧扩展 POST 的实际响应是 403
`{error:"PUBLIC_ADAPTER_REQUIRED"}`，不会运行写事务；该兼容边界不冒充
新的公共 workspace HTTP 合同。
