# D：同版交接与实施修正闭环

任务 Issue #52；固定起点 `c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db`。
本目录是 D 的接入说明与证据。正式模型内容仍由人确认；不修改旧图、日志实现、公共 UI 或旧集成分支。

## 实际能力

- `architecture.build_version_handoff` 消费 B 的 `{version, provenance}`，分开代码身份/代码 SHA/图身份/图语义版本/图来源 Git SHA/核查适用 SHA。
- `inspect_version_handoff` 在登记的两份 clone 读取固定 Git blob。缺提交、同名异仓、来源不同、脏工作区、摘要或内容被改都受控拒绝。不 fetch、不 checkout、不写正式图。
- 规划包保留 null 代码字段与 confirmed_design；确认设计不表示实现完成。
- `capture_worklog_refs` 只读原 Worklog 的固定历史版本，保留正文、保存时代码 SHA、作者声明与未核实状态；不改原日志，不带附件字节。
- `FixTaskService` 复用原 Continuity SQLite 连接，只增两张任务/历史表；不另建共享工作数据库。可关联原接续记录 ID 与固定日志版本。
- 任务包含偏差、已确认的期望过程/步骤、观察证据、允许改动路径、验收与未知。
- queued → received → in_progress → submitted → verification_pending。真实提交需要仓库身份正确、继承代码基线、在独立分支、变化非空且不越界。
- verified 需要本次可信验证凭据、对应 C 复核引用、明确人确认。AI 声明、done 字段、提交存在都不能关闭偏差。
- exported task 可交给第二客户端。收到的原完成结果进入 importedHistory，状态回到 received，未核实提交/验证不能直接继承；本机已有任务不覆盖。
- 存储 CAS、版本/会话绑定、失败保留、原授权重放拒绝与过程历史已覆盖测试。

## 最短运行

Python 3.10+ 和 Git，不增加运行依赖：

```sh
python -m unittest discover -s tests -p 'test_archloop_d_*.py' -v
python -m tests.architecture_loop_acceptance.run --run-d-fixture --output /absolute/new/d-evidence
```

第二条创建全新的临时测试资料目录，实际运行 HTTP/Git/SQLite：观察 B 绕过 C → 接手 → 独立分支只修 flow.py → 回挂 → 再测 → TEST_ONLY 人确认。
`dFixture: PASS` 仅证明 D 测试夹具。collector 退出 2 表示整个产品 T01–T28 未全部验收，不能改报整体 PASS。
输出包含完整 SHA、HTTP 请求/响应、同版核对、规划包、交接 Markdown、任务与 machine-readable report/failures。
session/CSRF/confirmation token 不进入交付证据。测试文件里的 C_TEST_DOUBLE 不是实际 C 推理。

A 提供已集成且干净的准确 checkout/完整 SHA/运行实例后：

```sh
python -m tests.architecture_loop_acceptance.run \
  --target-checkout /absolute/verified-checkout --target-head FULL_SHA \
  --base-url http://127.0.0.1:YOUR_PORT --run-d-fixture \
  --output /absolute/new/product-evidence
```

collector 只核查实际目标，前后检查 SHA/工作区；不改目标仓库。写测试仅在新 fixture。
`--ui-evidence` 可带准确目标/地址/操作者/时间/逐项截图来源的浏览器观察记录；这仍是参与者观察，不是独立审计。
T01–T28 各有状态、证据与局部检查；缺少接口/真实 AI/UI/设备时分别记 BLOCKED/NOT_RUN。

## 给 A 的接入

```python
from extensions.continuity.store import Store
from extensions.continuity.fix_tasks import FixTaskService
from extensions.continuity.fix_gateway import FixTaskGateway, RequestContext
from extensions.handoff.architecture import build_version_handoff
from extensions.handoff.archloop_backend import create_archloop_backend

# 路径均为服务端配置，不从候选/导入 JSON 读取。
service = FixTaskService(configured_continuity_store,
    architecture_repo=configured_architecture_clone,
    code_repositories=configured_code_clones,
    verification_provider=configured_trusted_D_C_verifier)
gateway = FixTaskGateway(service, configured_loopback_origin)
```

A 从真实 peer/Host/Origin/Cookie/X-CSRF-Token 构造 RequestContext。
会话创建检查本机同源，action 调用检查会话及 CSRF，verification confirmation 再绑定任务/版本/会话。
实际生产观测提供者返回 in-process `VerificationReceipt`，包含任务版本、提交、图版本、命令/退出码/证据摘要/时间/观察/C 复核引用。
不接受从 HTTP JSON 传来的 receipt、测试命令、仓库路径或 actor 覆盖。没有 provider 返回 BACKEND_UNAVAILABLE，保留待验证。
fixture-only verifier 有新建夹具标记和根目录保护，不运行 ProjectMind 正式代码仓库的修复命令。

`create_archloop_backend(service, workspace_provider)` 可登记到 A AdapterRegistry 的 handoff capability。
provider 以 A workspaceId 读取 B 的精确 version export，生成同版包，并绑定实际操作者、任务范围、偏差 ID 与接续/日志引用。
A 的请求 mapRevision 必须和 B 确认版本一致。不要用 A 草稿的另一个摘要冒充 B 版本，不凭目录名推断 codeRepoId。
共享 schema/身份转换和受保护公共路由归 A；这不是 D 已接通公共界面的证明。

### 公开接口安全边界

旧 ExtensionContext 没有真实会话/CSRF/版本 service，因此 `archloop_contract_info` 返回 CONFIGURED_ADAPTER_REQUIRED，故意不冒充自动可注册的 `contract: CONTRACT_V1`。
旧 handoff 的生成与 UNKNOWN 保持不变；旧扩展 POST 不开放 create/submit/verify/import 新写操作，返回 403 PUBLIC_ADAPTER_REQUIRED。
新受保护 Gateway/直接 adapter 由 A 接入。不要为了自动探测方便绕过 Gateway 把 JSON 当成可信 request metadata。

### 机器错误映射

D 使用 INVALID_INPUT(400)、NOT_FOUND(404)、STALE_CONTEXT/REVISION_CONFLICT/EVIDENCE_MISMATCH(409)、
DIRTY_WORKSPACE、SOURCE_REQUIRED、CODE_REQUIRED、SCOPE_MISMATCH、BRANCH_REQUIRED、LOCAL_REFERENCE_REQUIRED、
REQUEST_FORBIDDEN/HUMAN_REVIEW_REQUIRED/VERIFICATION_REQUIRED(403)、BACKEND_UNAVAILABLE(503)、VERIFICATION_FAILED(409)。
A 当前错误字典不包含全部 D code；adapter 将未登记 code 投影到现有 BAD_REQUEST/EVIDENCE_MISMATCH，并在 details.dCode 保留原 machine code。
最终共享合同仍由 A 定稿，普通 UI 只解释用户可采取的操作。

## 本轮边界

- 真实 B service 已在独立副本运行；D 已读取其真实 existing/planning 发布版本与第二 clone Git 字节。
- A/B 共用 schema、身份、审核授权仍有接线差异；继续核查已读取 C 的 55ea6466583d98e0f466e5d4055922ef4aeecb12，并实际运行其过程偏差函数，最新结果见 RESUME_DELIVERY.md。
- 浏览器下载失败（无有效 ZIP），不能伪造截图或用 HTTP 顶替 UI。真实 AI 未配置，跨设备未执行。
- 自查不称独立审计；最终 AUDIT_PENDING，USER_MODEL_REVIEW_PENDING。
- productmind-model 的任务指定两份方向文档在尝试的 GitHub 路径返回 404；本轮依据当前用户任务书，不猜其缺失内容。

## D 的实际 B/C 消费验收

可选组件 probe 在含真实 B/C 模块、干净且固定 SHA 的隔离验收 checkout 执行：

```sh
python -m tests.architecture_loop_acceptance.probe_candidates --source-checkout /absolute/validation-checkout --output /absolute/new/c-component-evidence
```

产生真实临时 Git 轨迹，调用实际 C 过程函数，通过 D FixTask 接手/受限修正提交/再验证；同时报告 C 缺证/身份/候选与 B 契约问题。仅测试夹具人审，不是正式图批准、公共 UI 或生产 C 接线。存在 finding 返回 1，禁止把测试函数成功当主线全部通过。
