# B 10 月 7 日交付

任务记录：#50。负责人：王海宁。基线：
c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db。

## Result

LOCAL_DONE：单一 service 的七个入口、图 schema、原子草稿/CAS、
受保护的人审边界、不可变语义版本、架构 Git 发布/恢复、历史恢复、
planning/mixed、第二 clone 导入以及只读 legacy adapter。

INTEGRATED=PENDING；D_VERIFIED=PENDING；CONTRACT_V1_A_REVIEW=PENDING；
最终独立精确 SHA 审计 AUDIT_PENDING；USER_MODEL_REVIEW_PENDING。
本地自查结果不写成外部 Codex 审计 PASS，不写整条产品主线已完成。

## Files Changed

仅 extensions/architecture_workspace/** 与 tests/test_archloop_b_service.py。
不改 app.py/extension_host.py/web/C/D/parser/公共合同或正式 Model。

## Verification

环境：macOS，Python 3.12，Git；数据/测试仓库独立，代码只读。

1. 开工基线：
   `python -m unittest discover -s tests -v`
   604 tests，22 skipped，1 failure + 1 error。
   failure 是既有 Mac 临时目录 /var 与 /private/var 断言差异；
   error 是初始浅 checkout 未取得 HEAD~1。原记录见
   verification/baseline-initial.log，本机原始未归一化日志独立保留。
   随后通过授权 connector 补入真实父提交 a1169188d972a604bceb05991bc9804e4ee825d5
   及其树，逐摘要核验；不改相关旧测试。
2. B 最终专项：
   `TMPDIR=/private/tmp python -m unittest discover -s tests -p 'test_archloop_b_*.py' -v`
   37 tests，18.553 秒，OK。见 verification/b-tests.log。
   包含两进程 CAS、跨会话/Origin/CSRF、过期/跨图/跨仓库审核、
   真实 Git 身份配置造成的 commit 失败及重试、中断后恢复、
   脏文件保留、不可变历史、规划/关联与真实第二 clone。
3. 完整回归：
   `TMPDIR=/private/tmp python -m unittest discover -s tests -v`
   641 tests，154.985 秒，OK（22 skipped），见 verification/full-regression.log。
   TMPDIR 是宿主路径别名调整，不声称修复旧模块或原 baseline 非绿状态。
4. 实际函数 smoke：
   `python -m extensions.architecture_workspace.smoke --test-fixture-only --output <new-absolute-directory> --legacy-code-repo <fixed-core-checkout>`
   PASS；七入口调用，实际架构 commit，独立代码与架构 clone 同版，
   纯规划不伪填 SHA，三种实际冲突。旧六节点图导入为 unconfirmed，
   没有对真实项目审核/发布。examples/exchange-fixture.json 是实际夹具输出。
5. 真实 Core HTTP：
   独立 loopback 18832、测试 repo/map/data-root；5 checks PASS。
   扩展 discovery ready，GET 版本/快照与后端包一致；普通与跨站 POST
   都 403 PUBLIC_ADAPTER_REQUIRED。见 verification/http-readonly-smoke.json。
   这不证明 A 的新受保护写路由或主页面闭环已完成。
6. git diff --check 与 B 范围/凭据字面量/本机绝对路径检查通过。

公开日志只归一化 CHECKOUT/RUN_ROOT/TEMP 路径，测试名、错误与结果保留；
完整原始日志在本机本次 evidence 目录。不是重跑 r51/D3，
也不是新主线 T01–T28 通过。真实 AI 未调用；Windows 原生环境 NOT_RUN。

## Project Model Impact

UPDATE。新增草稿/人审/版本/冲突治理职责，证据及候选见
MODEL_IMPACT_CANDIDATE.md。正式 Model 等负责人在 UI 批准，不直接更新。

## Risks / Follow-up

- A 汇总合同、配置新 workspace 路由/会话/CSRF，并接可操作编辑/审核/历史 UI；
  旧扩展写入口明确禁用。
- C 接初图/自然语言/增量候选与 B 操作；D 接同版交接、FixTask 回挂及独立验收。
- 部分确认/核查只覆盖列明 ID；Git 摘要与本机 actor 声明不认证人工身份。
- 本地无 origin 的代码身份不能跨机器，调用方须配置同一来源 URL。
- 日志与夹具只证明本次本机行为，不代表正式产品/Model 已发布。
- Draft PR 仅用于审阅和追加到 A 的新集成分支；不得合并 main，
  不回写旧 integration。至少两位队友确认且收到明确合并指令后再考虑合并。
