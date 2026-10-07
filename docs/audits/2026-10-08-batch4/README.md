# BATCH-4 问题交接：2×P1 + 4×P2

本目录按用户要求发布问题与既有证据，供另一位队友分析。**六条问题尚未修复，最终判定仍为 `CHANGES_REQUESTED`。** 本次发布仅增加文档及冻结证据，不修改产品代码、运行中的控制器或正式 Project Model。

- 分析任务：[Issue #57](https://github.com/LingweiXingzhi/projectmind-core/issues/57)。分析负责人由用户指定。
- 被审产品提交：[`803c6736d1ab01bee004a77c2d2b3b140b28cb12`](https://github.com/LingweiXingzhi/projectmind-core/tree/803c6736d1ab01bee004a77c2d2b3b140b28cb12)。
- 原集成分支：`integration/architecture-loop-v2-ZCODE-CLOSE-20261007-1757-K7`。
- 对照提交：`c62b5c0789879fa585824471396246ab21161106`；累计起点：`b75ad820e0d31e3dadf842b414f6950b5aa46102`。
- 本轮执行者状态：`STOPPED_REQUIRES_DECISION`、`AUTO_REVIEW_LOOP_STOPPED = YES`、`BATCH_5_CREATED = NO`、`accepted_sha = null`。

本次文档提交会产生新的 SHA；**它不是 BATCH-4 的审计目标**。复核产品时请固定到上面的完整产品 SHA。

## 先读哪些材料

1. [BATCH-4 原始回复](evidence/batch4-reply.md)：包含六条 finding、实际复现范围、测试结果与未验证项。
2. [判定文件](evidence/batch4-verdict.json)及[结果文件](evidence/batch4-result.json)：均为执行者离线恢复的回执，恢复来源见下节。
3. [控制器冻结快照](unattended/controller.py)：控制器原本位于产品仓库外；现在作为审查材料归档，不是新的产品模块或可部署入口。
4. [审查输入](evidence/audit-prompt.md)、[上一批回复](evidence/batch3-reply.md)及[上一批判定](evidence/batch3-verdict.json)：解释上一批修复要求及回归来源。
5. [执行者完整收口报告](evidence/executor-final-report.md)：原文包含历史阶段说明，请以末尾“最终状态与分类”理解最后状态。
6. [manifest.json](manifest.json)：每份材料的原控制目录相对路径、字节数和 SHA-256；[发布者检查](publisher-check.json)记录本次检查范围。

原始材料按字节复制；其中本机绝对路径是来源说明，其他设备应使用本目录对应文件。快照中的 `BASE` 随路径变化，**不要在本目录运行控制器的 `tick`、自动审查或进程管理命令**。

## 判定恢复与证据边界

执行者报告：审计子进程完成并留下完整结构化 `reply.md`，但控制器后处理崩溃。执行者在原控制目录内使用控制器的 `parse_verdict` 离线生成 `result.json` / `verdict.json`，没有再次调用模型。

`exit_code=0` **不是原始进程退出码记录**；它依据事件流末尾 `turn.completed` 和完整回复推断。原 `result.json` 的 `exit_code_source`、`recovered_offline`、`recovery_note` 均原样保留。发布者读取了本地事件流的完成事件，仅上传[事件元数据摘录](evidence/event-provenance.json)及原文件哈希；完整事件流与 stderr 不在本包中。

本次发布者只核对材料、产品/远端 SHA、干净状态、控制器快照一致性，执行了合成输入的凭据键名检测对照。没有重新调用模型、重跑自动审查或独立重跑六条完整复现。下文其他复现结果来自 BATCH-4 审计回复或执行者报告，不能改称本次发布者实测。

## 六条问题

| ID | 原级别 | 位置（固定产品提交或冻结控制器） | 实际缺口 | 执行者分类 |
| --- | --- | --- | --- | --- |
| GEN-01 | P1 | `archloop/context_pack.py:59–81` | 缩写 camelCase 名如 `clientAPIKey` 未识别为凭据键 | 下一阶段前必修 |
| G-02-RUNTIME | P1 | 控制器 `781/810/828/840` | 正常后处理未赋值；schema 回退重复启动同一线程 | 下一阶段前必修 |
| G-02-STOP | P2 | 控制器 `744–748` | 快速子进程退出后没有复查失租事件 | 执行者建议积压，待复核 |
| G-02-RETRY | P2 | 控制器 `904–916` | 调用前失租后未把 RUNNING 恢复为可重试 | 执行者建议积压，待复核 |
| G-02-RELEASE | P2 | 控制器 `650–653`、`469` | 读租约与删锁分离；队列释放没有传 lease | 执行者建议积压，待复核 |
| ACCEPTANCE-01 | P2 | `archloop/acceptance.py:542/548–549` | T24 用响应提供的版本作为 expected_revision，自我比较 | 执行者建议积压，待复核 |

P2 的“可积压”是执行者的分类，不是本次发布对竞态、归属或判据安全性的确认；请分析队友复核影响和修复顺序。

### GEN-01：缩写 camelCase 凭据键名漏检

[产品源码](https://github.com/LingweiXingzhi/projectmind-core/blob/803c6736d1ab01bee004a77c2d2b3b140b28cb12/archloop/context_pack.py#L59)只拆小写/数字到大写的边界；`clientAPIKey` 拆成 `client`、`apikey`，末词不在凭据组件表中。

BATCH-4 使用 `CONFIG={"clientAPIKey":"SYNTHETIC_TEST_CREDENTIAL_1234567890"}`，旧 `c62b5c0` 检测为 true，目标提交为 false；模拟 Git 输入后，实际上下文包保留合成凭据。`service.py:352` 和 `generate.py:151` 的模型输入路径消费该包。**未调用真实模型，没有实测真实凭据外发。** 执行者报告当前未配置真实 AI；配置前应修复。

在目标产品提交的仓库根目录可进行无模型、无网络的最小检查：

```powershell
python -B -c "import json; from archloop.context_pack import _key_name_is_secret, _looks_like_secret; print(_key_name_is_secret('clientAPIKey')); print(_looks_like_secret(json.dumps({'clientAPIKey': 'SYNTHETIC_TEST_CREDENTIAL_1234567890'})))"
```

当前预期输出为两行 `False`。修复方向供讨论：补充 `apikey`、`accesstoken`、`clientsecret` 等连写词，或完善缩写大小写边界拆分。复验需同时保住普通配置名及占位符，不得仅覆盖这一反例。

### G-02-RUNTIME：控制器结果落盘与回退崩溃

冻结快照中 `returncode = proc_returncode`（828 行）仅在 schema 回退分支赋值，正常路径在 840 行使用该变量，会触发 `UnboundLocalError`。781 行与 810 行重复进入同一个 `LeaseWatchdog`，schema 参数失败后回退时再次启动已启动的线程，触发 `RuntimeError: threads can only be started once`。

BATCH-4 复现使用真实函数，子进程/文件接口为替身，结果写入数为 0；实际本轮回执也因后处理崩溃未自动落盘。需修复后才能恢复无人值守使用。建议补两条检查：正常完成写下真实退出码及判定；schema 回退期间看门狗生命周期合法且能继续监控。

### G-02-STOP：快速完成绕过失租判定

`_run_child` 在 `proc.wait` 成功后直接返回，未再读取失租状态。审计用真实、无害的 0.3 秒 Python 子进程和真实 `LeaseWatchdog`，锁存储模拟易主，得到 `watchdog_lost=true`、`returncode=0`、`reported_lease_lost=false`。这条没有实测文件系统并发，影响应与结果归属、围栏以及落盘行为一并分析。

### G-02-RETRY：调用前围栏失败使包滞留 RUNNING

`tick_audit` 先设置 RUNNING，再检查调用前围栏，失败时直接返回。内存复现得到 `package_status=RUNNING`、`controller_state=RUNNING`、`attempts=0`，未启动审计；`newest_pending` 随后不会选择它。执行者收口报告还记录了本轮曾有包卡在 RUNNING。建议分析恢复状态时的租约归属，避免旧持有者覆盖新持有者状态。

### G-02-RELEASE：释放锁的读—删竞态

`release_lock` 读到自己的租约后，在 `unlink` 前可能已有新持有者；内存交错复现得到 `release=true`、`foreign_lock_survived=false`。`mutate_queue:469` 还存在未传 lease 的释放调用。本轮未验证实际文件系统并发，修复建议应说明归属检查与删除如何保持一致，而非只加一次读取。

### ACCEPTANCE-01：T24 没有独立验证当前 HEAD

[T24 调用位置](https://github.com/LingweiXingzhi/projectmind-core/blob/803c6736d1ab01bee004a77c2d2b3b140b28cb12/archloop/acceptance.py#L542)从响应 identity 取得 `local_head`，然后作为预期版本传入。提交存在和文件计数一致只能证明响应对应一个真实提交，不能证明它就是仓库当前 HEAD。

审计在真实 HEAD 为 `803c673…` 时提供真实旧 `c62b5c0` identity/coverage（248/139），仍被判 PASS；当前目标提交树计数为 249/140。原 35 PASS / 2 NOT_RUN 验收文件的 T24 记录本身绑定的是 `c62b5c0`，执行者说明验收时 HEAD 也是它。**不要把这份记录当作独立完成了 `803c673…` 全量验收。** 建议从本地 Git 独立取得 HEAD，并加真实旧提交不能冒充当前提交的检查。

## 测试记录与未验证项

| 来源 | 记录 | 解读 |
| --- | --- | --- |
| 执行者专项测试 | [144 OK / 1 skipped](evidence/archloop-a-batch3repair.log) | 既有日志，本次未重跑 |
| 执行者全量测试 | [800 ran / 3 errors / 1 skipped](evidence/full-suite-batch3repair.log) | 执行者称三项与起点环境错误一致；本包未上传起点日志，发布者未独立复跑对照 |
| 执行者验收 | [35 PASS / 2 NOT_RUN](evidence/acceptance-a-side-batch3repair.json) | T01/T23 真实 AI 未配置；T24 记录为旧 `c62b5c0` |
| BATCH-4 指定测试 | 原始回复：33 ran / 14 errors | 19 通过；14 个 `No usable temporary directory found`，与上述三项环境错误不是同一组 |
| 控制器自检 | [selfcheck.json](unattended/selfcheck.json)，`ok=true` | 未覆盖 `run_codex_audit` 后处理路径，不能反驳 G-02-RUNTIME |

以下 BATCH-4 `unverified` 原样保留：

1. 指定测试受临时目录限制，未完整运行磁盘集成测试；未重跑完整验收。
2. 未调用真实 AI、操作真实浏览器或验证 D 模块及其独立验收。
3. 未执行新发布、跨设备或实体第二副本验收，也未测试发布事务极端中断。
4. 控制器子进程测试使用真实新建 Python 进程；锁文件、归档和状态存储替为内存，未验证实际文件系统并发或完整 Codex 调用。
5. 未独立构造 SHA256 仓库验证64位提交路径。

执行者浏览器证据属于参与者观察；上述独立审计并没有完成浏览器验收。原控制目录保留原始事件流、其他批次未验证项及运行状态，本包只是精选的问题交接材料。

## 分析队友需要给出的结果

- 对每条 finding 给出成立/不成立/证据不足、复核位置、实际影响与优先级。
- 分开判断产品侧 GEN-01、验收工具 ACCEPTANCE-01 和无人值守控制器四条问题；判断控制器同族问题是否应一起修。
- 提出最小修复范围及能证伪原问题的复验步骤，注明需要真实文件系统并发或完整子进程链路的部分。
- 保留真实 AI、D 接入、UI 集成和跨设备的未完成状态，不勾选未确认内容，不把候选架构批准为正式 Project Model。

[D PR #54](https://github.com/LingweiXingzhi/projectmind-core/pull/54)和[UI PR #56](https://github.com/LingweiXingzhi/projectmind-core/pull/56)在发布前均为 OPEN / Draft，尚未接入/合并。本次没有改变它们，也没有推进 BATCH-5。Project Model Impact：**NONE**。
