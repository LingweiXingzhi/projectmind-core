# B 自检与代码审查 · 2026-10-07

## Result

针对 PR #51 首交付进行差异审查和真实 Git 失败恢复验证。
新增 5 项测试在原实现全部复现失败（3 failure、2 error），修复后
B 专项 42 项通过。不是独立外部审计；AUDIT_PENDING 和 A/C/D 接入状态不变。

| 问题 | 后果 | 修复 / 对应回归测试 |
|---|---|---|
| P1 发布期间仍可消费另一有效预览 | 覆盖审核、原发布授权失效，或提交与审核状态不一致 | publishing/published 冻结新决定；finalize 核对冻结状态与 reviewId；test_pending_publication_cannot_be_rejected_by_an_older_preview |
| P1 原子 replace 前进程退出留下工作树临时文件 | 重试因额外脏文件被拒绝 | 临时文件写入同卷 .git；子进程真实 os._exit(73) 后重开恢复，仅产生一份提交；test_process_exit_before_atomic_replace_is_recoverable |
| P2 重导入自身版本误报冲突 | reader 附加说明被当作历史内容修改 | 同包、同 Git source 复用原 envelope；test_reimport_own_version_preserves_original_immutable_envelope |
| P2 发布锁连接失败泄露 sqlite 异常 | 调用方得不到约定机器错误 | 连接失败转换 PUBLICATION_FAILED；test_publication_lock_open_failure_has_controlled_error |
| P2 操作含不适用字段却成功 | 调用方以为字段生效，实际参数被忽略 | 按动作严格校验、整批回滚；test_operation_action_rejects_ignored_fields_without_partial_edit |

## Files Changed

仅 B 的 service.py、git_publication.py、tests/test_archloop_b_service.py，
本目录候选合同、DELIVERY、自检报告及验证日志。未改公共入口或其他成员代码。

## Verification

- 原问题复现：verification/self-review-reproduced.log，5 项全部失败。
- 修复后专项：verification/self-review-b-tests.log，42 tests / 21.439 秒 / OK。
- 新完整回归：646 tests / 159.107 秒 / OK（22 skipped），
  见 verification/self-review-full-regression.log；624 项实际执行。
- 新 fixture function smoke PASS；独立代码/架构 clone 同版，3 种冲突，planning null SHA；
  实际身份摘要见 verification/self-review-function-smoke.json。
- 新实际 Core 只读 HTTP 5 checks PASS；记录含三种版本身份，
  见 verification/self-review-http.json；服务仅在测试期间运行于 loopback 18833。
- diff、B 范围、秘密字面量和本机绝对路径检查；上传后核对完整树及受保护分支。

复现命令（Python 3.12 / macOS / Git）：

```sh
TMPDIR=/private/tmp python -m unittest discover -s tests -p 'test_archloop_b_*.py' -v
TMPDIR=/private/tmp python -m unittest discover -s tests -v
python -m extensions.architecture_workspace.smoke --test-fixture-only --output /absolute/new/fixture-directory
```

日志仅归一化本机路径，原失败与结果保留；原始日志在独立本地 evidence。
本次新夹具与初次 examples 的 fixture SHA 不同，不能混用两组交换包。

## Project Model Impact

MINOR：本轮修复审核冻结、恢复、导入与输入校验的内部行为，职责边界未变。
依据是原候选合同的人审/不可变版本/失败可恢复要求与上述实际复现。
首交付的 UPDATE 候选仍待人批准，未修改正式 Project Model。

## Risks

- publishing 失败后保留日志及原授权，恢复成功前不能切换审核或代码上下文；
  放弃/撤销发布的独立 UI 操作未纳入本轮。
- 硬退出可能留下 .git/architecture-publication-* 临时文件，但不进入 Git
  工作树或提交、不阻塞重试；不自动删除未知文件。本测试不证明断电级持久性。
- actor 仍为本机操作者声明；Git/hash 校验不认证人工身份。
- 真实 AI、新公共写 HTTP/UI、Windows 原生、主线 T01–T28、最终独立审计未验证。

## Follow-up

同一 Draft PR #51 更新；A 汇总合同和公共接线，C/D 联调后继续验收。
仅供审阅和追加到 A 的新集成分支；不得合并 main 或旧 integration。
