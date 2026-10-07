# B 接入包：给 A / C / D 的可运行调用说明

状态：B 的工程候选，A_REVIEW_PENDING。依据 Issue #50 与 10 月 7 日任务书。
本包准备 B-N1 的接口交付和 B-N2 的调用样例；公共 CONTRACT_V1 由 A 登记。
当前未运行 A 的新工作台、实际 C 推理或实际 D Handoff，不声称三方联调已完成。

## 先运行实际样例

项目根目录，Python 3.10+、Git：

```sh
python -m extensions.architecture_workspace.smoke --test-fixture-only --output /absolute/new/fixture-directory
```

输出目录必须不存在，测试只创建独立 repo/data-root。

- `FUNCTION_SMOKE.json`：原有正常/规划版本、三种错误和第二 clone；保留原输出。
- `CONSUMER_CONTRACT.json`：17 次实际 B 调用的参数、响应、4 类错误，
  接受/修改/拒绝的候选夹具、C 快照、D 版本包及独立第二 clone 导入。
- 会话、CSRF、确认和发布令牌全部替换为 `<PRIVATE_RUNTIME_VALUE>`。
  JSON 供查看合同，不可直接重放；可执行 Python 示例在 consumer_contract.py，
  运行时使用真实新令牌，不能拿占位符调用服务。
- 测试包的 `C_TEST_DOUBLE`、`TEST_ONLY_SIMULATED_HUMAN`、`NOT_RUN`
  标志必须保留。候选是合成合同夹具，没有执行 C 推理或真实规则引擎。

`examples/consumer-contract-fixture.json` 为本次实际生成的包；与原 examples
交换例是不同 fixture 身份，不交叉配对。每次运行会产生新 ID/SHA。

## A：初始化和用户操作顺序

初始化使用服务端配置，不接受用户 JSON 任意指定磁盘路径：

```python
from extensions.architecture_workspace import WorkspaceService, HumanReviewGateway

service = WorkspaceService(
    configured_absolute_data_root,
    code_repositories=[configured_code_clone],
    architecture_repo=configured_architecture_clone,
    architecture_branch="architecture/candidates/your-approved-run",
)
gateway = HumanReviewGateway(service, configured_loopback_origin)
```

三个路径相互隔离；架构仓库已初始化、已有指定分支、提交身份已配置，工作树干净。
B 不 clone/fetch/push 或切换分支。架构 remote 与团队产品代码 remote 的处理由 A/负责人登记。

| 用户动作 | A 调用 B | 必须绑定 |
|---|---|---|
| 打开项目/规划 | service.open_workspace | mode、登记的仓库身份/代码 SHA；planning 为 null |
| 收到初图 | service.create_draft | workspaceId、graph、origin、baseMapRevision |
| 保存选择/编辑 | service.apply_draft_operations | draftId、expectedDraftRevision、baseMapRevision、proposalId |
| 刷新重开 | service.get_draft / graph_snapshot | 当前 workspace/draft 的稳定 ID |
| 请求审阅预览 | gateway.preview_review | 真实请求元数据/会话/CSRF，实际图和代码版本、coverage、理由 |
| 人明确确认/拒绝 | gateway.confirm_review | 同一 auth、confirmationToken、previewDigest 和上下文 |
| 发布 | service.publish_reviewed_graph | publicationToken、expectedMapRevision，HTTP 还须检查人审会话 |
| 打开历史/导出 | get_version / export_version | workspaceId、精确 mapRevision |

表里为工程概念名；Python kwargs 使用 B_CONTRACT_CANDIDATE_V1.md 与样例中的 snake_case。
本包不发明新 HTTP URL、公共 JSON casing 或状态映射；由 A 冻结后再对齐。

会话入口使用本机同源 POST，Cookie 的 HttpOnly/SameSite 等设置由 A 负责。
peer/Host/Origin 从真实 request 获取，session/CSRF 从服务端会话与请求头/Cookie 获取，
不能相信 JSON、候选包里同名字段。后台候选通道不持有 Gateway 或审核/发布令牌。
A 不能把 service.record_review 或 _preview 直接映射到普通扩展 POST。
发布 HTTP 必须有会话防伪检查，不能只凭前端隐藏按钮。

展示 preview 的 beforeGraph/afterGraph/appliedOperations/rejectedCandidates、coverage、
verifyCode 和 limits。返回成功前不要显示“版本已发布”；publishing 表示等待恢复。
失败后保留原授权及日志，不能为恢复而 reset/clean、清库或替换审核决定。

## C：候选与选择结果

C 提供候选，A 处理用户选择，B 校验和保存。新候选结构在公共合同冻结前保持工程候选状态。

本例三个候选：

1. 接受 `candidate-add-helper`：应用 node.add + edge.add。
2. 修改 `candidate-step-title`：保留步骤 ID，用人工纠正后的 step.update，source=human。
3. 拒绝 `candidate-unproven-title`：不应用原 operation；将 candidateId/proposalId/理由记录到审阅。

候选 ID 和操作 ID 是不同概念；一个候选可以对应多条操作。
source=human/rule_based/ai_generated 表示编辑来源，不能代替人审授权。
新对象 ID 在 add.value 内；step 操作带 processId；不适用字段受控拒绝。

已有完整图用 create_draft；已有草稿的局部变化用 apply_draft_operations。
使用 B 返回的 proposalId，若由 C 提供该 ID，应在 create_draft 明确提供并全程保持。
codeRepoId/codeRevision、baseMapRevision 和 expectedDraftRevision 不可从目录名或 HEAD 标签猜测。
graph_snapshot 返回的版本包只读；C 不能将新 HEAD 直接写为 verifiedCodeRevision。

### 四种实测失败

| 错误 | CONSUMER_CONTRACT 的实际触发 | 下一步 |
|---|---|---|
| REVISION_CONFLICT | 草稿已从 1 改为 2，旧客户端仍提交 1 | 重读草稿，保留用户输入，重新预览选择 |
| STALE_CONTEXT | 同一 draft 提交另一 proposalId | 重取对应候选/工作区；不能静默改 ID |
| EVIDENCE_MISMATCH | code 证据 path=../private | 修正候选证据，不读取仓库外内容 |
| HUMAN_REVIEW_REQUIRED | 未经审阅申请发布 | 走实际预览和明确确认；不伪造 actor |

## D：版本包与第二客户端

用 export_version 获取 `{version, provenance}`，读取指定 mapSourceRevision 的实际 Git 对象。
确认仓库来源、完整代码 SHA 和 mapId 后，在独立数据根打开工作区并 import_git_version。
同版比较使用完整 version；provenance 的读取说明可能不同，实际 source SHA 必须核对。

本例第二客户端有两份真正独立 clone。代码 origin 明确设置为同一测试来源 URL，
代码身份一致不是由同名目录推断。它证明 B 的 Git 导入路径，不证明 D 的实际交接产品或跨设备部署。

规划包有 confirmed_design 和 null 代码字段，不能填服务程序的 SHA；
关联代码须调用 associate_code 并保留设计历史。FixTask、回挂、关闭偏差和 T01–T28 工具由 D/C/A 对接。

## 接入验收与当前边界

- B 专项、CLI 及实际参数/响应已验证；旧只读扩展继续阻止 POST。
- A 用新受保护 HTTP/UI 跑保存、刷新、人审、发布与历史，才可标公共接入通过。
- C 提供实际 bootstrap/incremental 候选并走 A→B，才可标实际候选联调通过。
- D 使用实际交接模块读取精确包、跑新主线后，才可标 D_VERIFIED。
- 公共合同差异见 CONTRACT_GAPS_FOR_A.md；本轮证据和限制见 CONSUMER_STAGE_DELIVERY.md。
