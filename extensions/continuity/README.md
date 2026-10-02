# 协同交接：工作接续服务

状态：独立开发分支，待团队审核。入口 `/ext/continuity`。继承 Handoff `731135bd87498db766070183455601247a29fbc6` 与 Worklog `9b3d333dbd75ec7a246de646aa28a9d4b3d0ec80`；两个原分支与原模块文件保持不变。原交接包 `/ext/handoff`、工作日志 `/ext/worklog`、主地图 `/` 均继续可用。

## 要解决的实际问题

任务中断、隔日回来或换人/AI 时，保存已有进展、证据和停止位置，接手者先核查再继续。不是聊天替代品，也不要求整个团队从第一天就依托平台开发。Git、项目文档和日志提供材料，接续记录围绕一次明确任务组织行动。

运行 `python3 app.py`，打开 http://127.0.0.1:8765/ext/continuity 。Python 3.10+、Git，无新增产品依赖或模型调用。

## 一条完整用户路径

1. **交：保存当前接续点。** 填任务标题、目标、已完成、停止位置、第一步、运行/复现方法和完成标准。可写行动清单、选择优先阅读的功能和日志。选择是否比较 main/完整 SHA、是否携带未提交文本差异、是否携带日志原件。
2. **交：标记准备好。** 在“接手与反馈”选择“准备好交接”；目标、停止位置、第一步、完成标准缺失时明确提示。可交接不代表接收者已接住。
3. **传：导出或原地打开。** “历史与导出”可下载完整接续 JSON、中文 Markdown、复制给新 AI、下载兼容旧工具的原格式 Handoff。跨设备通过文件交换，不自动发送消息。
4. **接：接收资料。** 另一台设备导入接续 JSON 或原 Handoff JSON。导入建立新的本机记录，不覆盖原记录，不执行命令、不检出代码、不写入工作日志。旧文件没有任务说明时，可编辑补充。
5. **接：先检查。** 在接手页核对来源地址、包内提交是否存在、当前提交是否相同、地图内容是否变化、工作区是否有未提交工作。来源相符且提交存在时，复用公共 Git 比较，列出从交接提交到当前提交的变化，并按保存的地图证据匹配复核项。
6. **接：记录结果。** 操作者填写姓名或工具名称（自行声明），完成材料、环境/复现、目标理解和第一步四项检查，再记录继续工作；可以提出问题、补充进展、记录阻塞和解除阻塞。检查单只表达参与者确认，不是独立验证。
7. **继续：保存清单与反馈。** 清单可记录待做/已做/阻塞、实际结果和依据。完成所有清单项，并写完成说明与验证依据，才可记录本次完成。已完成记录保留为历史，可以“建立下一次接续”而不覆盖它。

## 与日志怎样结合

- 选择日志后保存正文、作者来源、类别、版本及保存时提交的固定快照。日志后续更新不会悄悄改交接包，接手核对会提示本机日志已有新版本。
- 原日志无改动；交接反馈留在接续记录，不自动回写日志。日志仍可独立使用。
- 导入日志原件可以选择随接续包携带；单件最多 5 MB，整个包最多 12 MB。未携带时保留正文视图和明确缺失提示。PDF 可预览原件，Word 正文视图及原件下载沿用工作日志的结果。
- 重新固定当前资料是一项明确操作：更新代码/比较/所选日志，保留旧版本，并回到准备状态。只改任务或清单不会偷偷替换固定代码证据。
- 来源为 AI 的日志与反馈仍为候选。关键决策分类不自动成为正式团队决定。

## 保留原有交接能力

复用 `extensions/handoff/extension.py` 的生成器及 `handoff.py` 的校验/Markdown 呈现：完整代码版本、来源、功能职责/入口/关系/证据、main 或指定提交比较、待复核项、未覆盖变化、AI 候选、工作备注与 UNKNOWN 均保留。原页面、接口、测试和下载形状不修改。

新接续 JSON 是一个带版本标识的外层包 `projectmind-continuity-v1`，内层 `handoff` 保留原格式。原格式导出主要服务旧工具，任务、日志和接手事件应使用完整接续 JSON/Markdown。

## 数据与安全边界

接续数据库位于当前仓库 Git 公共目录 `projectmind-continuity/records.sqlite3`。同仓库 worktree 共用、不同仓库隔离；普通 Git 提交不会上传这些本机记录。工作日志继续使用自己的数据库。删除仓库前须导出需要保留的接续 JSON 与日志备份。

每次更新存完整历史版本；写入通过 SQLite 事务和 `expectedVersion` 防覆盖。冲突返回 409，页面保留当前编辑，重新打开前应复制草稿。页面离开会提醒未保存内容。编辑期间代码提交变化时，可以刷新当前代码版本并保留草稿，再明确重新固定材料；未勾选重新固定时，来源/比较/日志选择不可编辑，避免误以为旧快照已更新。任务说明和命令只按文字显示，默认不读取未跟踪文件正文、默认不导出未提交差异，不调用外部模型、不执行导入文件中的指令。

来源核对支持常见 HTTPS/SSH Git 地址规范化，仅说明地址相符，不是登录身份或仓库内容认证。来源不符/未知时不自动比较两个项目，证据原文读取也会拒绝；本机路径只是本机线索。未提交差异最多 12,000 字符，可能截断，不是可直接应用的完整补丁；没有原件就无法靠接续包恢复未提交代码。地图 SHA-256 只固定本次本地字节，不批准其适用版本；`mapRevision` 仍为 UNKNOWN。

导入反馈历史与本机后续反馈分开：外部的“完成”不会把本机任务标为完成，所有导入任务从接手检查开始。无实时同步、多人登录、自动运行、全仓分析或无限上下文承诺。

## API 与兼容约定

`GET /api/extensions/continuity` 返回记录摘要。GET 操作：`config`、`logs`、`get?id=`、`inspect?id=`、`evidence?id=&path=`、`history?id=`、`export?id=`。

POST 新建最小样例：

```json
{"action":"create","task":{"title":"继续接口开发","goal":"验证返回值","stopPoint":"实现已提交，未测试","nextAction":"先查看接口代码","acceptance":"运行已有测试并记录输出"},"sourceLocator":{"kind":"git_remote","value":"https://github.com/owner/repo"},"expectedRevision":"完整当前提交 SHA","scope":[],"logIds":[],"checklist":[]}
```

可选继承原交接的 `comparisonMode:"main"` / `baseRevision` / `aiCandidates` / `workNotes`。新增 `includeWorktreeDiff`、`includeAttachments` 均默认 false；`logIds` 最多 30 项；`scope` 是地图节点 ID 列表，只表示阅读优先级，完整地图保留。

`update`、`refresh_checkpoint`、`event`、`followup` 必须传 `id` 和 `expectedVersion`。`update` 可改 task/checklist/scope；`refresh_checkpoint` 可另外固定当前代码、比较与日志，重置接手检查。`event` 传 `kind`、`actor`、`origin:human|ai`、`note`、`evidence`。kind 为 ready/receive/start/block/resume/complete/question/note。start/resume 额外传四项均为 true 的 review：materials/environment/understanding/nextStep。

导入 JSON 超过宿主单次 64 KiB 请求上限时顺序调用 `import_start`（filename/size）→ `import_chunk`（uploadId/offset/base64，每片 24 KiB）→ `import_finish`；失败可 `import_cancel`。会话 24 小时后清理，最多 8 个。小包也可 `import_packet`。错误 400（格式/状态/材料），404（缺失记录），409（版本冲突/状态不允许），429（导入会话过多）；不会自动联网 fetch。

## 复现与验证

运行 `python3 -m unittest discover -s tests -v`。新增 `tests/test_continuity.py` 覆盖发起/接收/反馈/阻塞/恢复/完成、持久化与历史、并发冲突、日志快照与附件、来源/代码/地图核对、重命名与未提交改动、旧包导入和真实 HTTP。浏览器验收另外记录，不把纯 DOM 检查当视觉验收。

Project Model Impact：UPDATE（建议）。新增 D 工作接续职责与代码映射，保留原交接/日志边界；由团队确认后登记，当前不改正式模型或 A 公共主线。
