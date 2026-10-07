# B：架构草稿、人审和不可变版本

本轮依据：2026-10-07 ABCD 完整任务书的 B 节。代码基线：
`c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db`。

此目录是 B 的实现与交换合同候选，HTTP 和主页面接线由 A 负责。
状态分开记录：B 本地验证见 DELIVERY.md；INTEGRATED、D_VERIFIED、
最终独立审计与真实负责人模型批准未完成，不写产品整体 PASS。

## 运行

Python 3.10+、Git；新增零第三方依赖。项目根目录：

```sh
python -m unittest discover -s tests -p 'test_archloop_b_*.py' -v
python -m extensions.architecture_workspace.smoke --test-fixture-only --output /absolute/new/fixture-directory
```

第二条只在新建测试仓库内模拟人审，不能用它批准真实项目。
目录已经存在时拒绝覆盖。结果为 FUNCTION_SMOKE.json，含实际代码/架构
Git SHA、正常交换包、三种机器错误和第二 clone 的读取结果；不输出令牌。
可追加 `--legacy-code-repo /absolute/projectmind-checkout`，仅导入其旧六节点
地图为 unconfirmed，不审核、不发布该旧图。

## 服务与隔离

`WorkspaceService(explicit_absolute_data_root, code_repositories=[...],
architecture_repo=..., architecture_branch="architecture/candidates/...")`。
每个运行副本配置自己的外部数据根。数据根、代码仓库和架构仓库禁止相互重叠；
代码只读已提交 Git 对象。架构副本必须是普通独立 Git 仓库、干净工作区，
已有指定候选分支与初始化提交、可用本机提交身份。服务不 clone/fetch/push，
不切换分支，也不合并任何 main。A/负责人配置来源，不能让 HTTP JSON 任意选磁盘路径。

存储是私有 SQLite 文档表，BEGIN IMMEDIATE 锁与事务实现线程/进程原子 CAS。
不是共享团队数据库。图在候选架构 Git 中持久保存后可被第二客户端导入。
发布日志先持久保存；写文件采用临时文件、fsync 和 replace。失败保留现场，
通过原发布令牌重试；发布期间冻结该草稿及工作区版本推进。未知脏文件不会被
reset/clean。Git commit 后存储尚未收口时，重试只认精确的单文件直接后继提交。
不承诺故障磁盘/断电恢复；SQLite 与 Git 的正常进程中断恢复已测试。

## 人审边界

AI/规则 worker 只取得服务和只读快照，不取得 HumanReviewGateway、
会话令牌或 publicationToken。服务不会从 actor="human" 推断批准。
Gateway 从 A 提供的真实网络请求元数据检查 loopback、Host、Origin、
服务端本机会话、CSRF 与会话过期；预览绑定草稿版本、旧图、目标代码、
操作、拒绝理由、coverage 和限制，再由显式确认产生发布令牌。

A 必须从 HTTP request/cookie/header/peer 取这些值，不能从 JSON 或 AI 结果取；
会话端点需本机同源 POST，cookie 使用 HttpOnly/SameSite，密钥/令牌不入日志。
不要把 service.record_review 或私有 _preview 直接暴露成普通扩展 POST。
这是本地操作者声明，不是密码学人工身份，也不防有同一操作系统账户权限的
任意 Python 进程读取数据库或调用内部方法；没有实现多用户认证/RBAC。

现有 ExtensionContext 不含完整请求上下文/防伪令牌，所以 extension.py 的
旧 seam 只读，所有 POST 返回 403 PUBLIC_ADAPTER_REQUIRED。未配置
PROJECTMIND_ARCHITECTURE_DATA_ROOT 时 GET 如实返回 integration_pending。
该读入口依赖旧 map 模式；无地图新 workspace 路由由 A 接线，未删除 MAP_REQUIRED。

## 语义与迁移

- IDs 由服务随机生成或严格校验；重命名保留 ID。引用校验失败拒绝整批，
  没有隐藏级联；需要删除引用者时由 UI 明确预览完整操作批次。
- 草稿 revision 每次保存递增，包括布局。操作带 expectedDraftRevision、
  baseMapRevision、proposalId。历史恢复是新的未确认草稿。
- mapRevision 对规范化图、mapId、代码绑定、确认性质、核查覆盖和限制计算摘要。
  对象列表按 ID 排序；过程步骤数组保留顺序。布局、操作者、时间、本机
  workspaceId、来源 Git SHA 和生成来源不改变语义摘要。布局单独保存在草稿，
  不进入正式语义包。相同语义复用原版及原审查记录，不能覆盖不可变文件。
- codeRepoId 来自配置仓库的 origin URL 摘要；无 origin 时为本机路径身份。
  同名目录不算同仓库。两客户端使用完全相同来源 URL；SSH/HTTPS URL 的别名
  不自动合并，本机无 remote 的仓库不假装有跨机器稳定身份。
- planning 的 codeRepoId/codeRevision/verifiedCodeRevision 为 null。
  confirmed_design 不表示 implemented。associate_code 显式关联并保留设计历史，
  关联后仍需新核查。
- 正式包 origin 保留生成方式；confirmation 分别列出已确认/未确认对象，
  implementationStatus 与 verifiedCodeRevision 是独立信息。
  confirmed_cognition 表示人审版本存在，不等于所有节点/代码/运行行为已证实。
- reviewCoverage 与 limits 永远随包携带；部分批准不成为全仓 verified。
  静态引用、功能协作、期望先后是三类关系；过程标 expected，不能伪装运行轨迹。
- 旧人工图只能导入为 legacy/unconfirmed；证据不存在、路径坏或引用坏受控拒绝，
  不从工作树补证据。明确未知证据保留 unknownReason，不进入代码核查证明。
- 新代码提交只标需复核证据、节点/过程，verifiedCodeRevision 不变；非后继分支
  或另一仓库为 STALE_CONTEXT，不能因祖先关系直接扩展核查。
- 包文件不含 mapSourceRevision。它从实际架构 Git commit 读取，并置于
  provenance envelope；读取固定 Git 对象并校验内容摘要/审查绑定，
  不等于认证作者或证明架构解释真确。

函数、字段、A/C/D 调用顺序与错误见 B_CONTRACT_CANDIDATE_V1.md。
正式公共 CONTRACT_V1 由 A 汇总，B 不修改公共接口或正式 Model。
