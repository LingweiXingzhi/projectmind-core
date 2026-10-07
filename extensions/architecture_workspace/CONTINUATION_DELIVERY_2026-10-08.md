# B 持续推进交付与复查（2026-10-08）

## Result

实现候选选择的只读预演、当前正式基线事务校验与审阅会话生命周期保护。
在独立组合目录完成最新 A/新 B 接续，以及 B 发布原包被实际 D 消费。
这是组件与隔离整合验证；不是远端整合已更新、真实模型已批准或公网部署成功。

## Files Changed

- review.py / fixture_http.py：过期会话原位回收、默认 128 活跃容量、并发分配锁；
  有效授权不逐出，错误 CSRF/来源拒绝，返回会话副本。
- service.py / surfaces.py：previewSelection、共用操作求值器、零数据库写入；
  validateProposal 在单个事务核对八字段与当前正式基线，避免旧基线仍返回有效。
- surface_smoke.py：加入实际选择预演、零写入及与保存一致的断言。
- d_handoff_smoke.py：使用本轮固定 D 文件的实际 build/inspect，对 B 真发布包与第二 clone 核查。
- tests/test_archloop_b_review_sessions.py（12）、test_archloop_b_selection_preview.py（15）；
  test_archloop_b_surface_http.py 新增 1 项真实 HTTP 预演测试。
- 部署准备方案、实施说明、历史 A/C 差异更新标记、本轮证据。
  A 的 app.py/archloop/web、C/D 源码、公共合同与正式 Model 未修改。

## Verification

### 固定来源与组成

| 来源 | SHA / 核查 |
|---|---|
| 原 B 开发基线 | c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db |
| 本轮开始的远端 B | 8315c2e67aef2fa532869595441e68c29ae1beb3 |
| 本轮测试的本地 B 代码提交 | 4cce0bf165e71b55920a6affcb56c06e29159c87 |
| A 整合固定来源 | 803c6736d1ab01bee004a77c2d2b3b140b28cb12 |
| D 实际组件固定来源 | c8b942a8d724b1bd0509f61b2db6ec642a117181 |
| 最终 D 演练的本地合成源码提交 | 80c4495a269f550050cf186474d44c392aa9952d |

A 整合快照 249 个文件逐个核验 Git blob，原快照未覆盖。
演练目录拷贝该快照，只覆盖 B 自有文件，再共装逐 blob 校验的 D 组件和验收夹具。
合成源码提交不是团队仓库分支提交；测试时，全部 23 个 B Python/测试文件与
合成源码相同。证据记录源码 fingerprint；D smoke 还固定校验三个实际消费依赖 blob。
不能用 D 的历史报告代替本轮执行。

### 实际命令与结果

统一环境：TMPDIR=/private/tmp、PYTHONDONTWRITEBYTECODE=1、Python 3.12。

| 执行 | 结果 | 用时 |
|---|---|---:|
| 本地 B：unittest discover -s tests -p test_archloop_b_*.py -v | 155 executed passed，0 skipped | 58.515s |
| 本地全仓：unittest discover -s tests -v | 759 total，737 executed passed，22 skipped | 201.059s |
| A803c 原版相关 A/B 测试基线 | 97 total，96 passed，1 skipped | 20.429s |
| 最新 A + 本轮 B 的相同相关测试 | 97 total，96 passed，1 skipped | 22.951s |
| 共装 D 组件与验收诚实性测试 | 32 passed，0 skipped | 27.846s |
| surface_smoke CLI（D 演练中先执行） | 22 actual calls，19 assertions passed | 实际日志 |
| d_handoff_smoke CLI | 12 assertions passed，PASS_COMPONENT_REHEARSAL | 实际日志 |

A/B 的一项跳过原因：rule-based candidate has no process steps to compare。
全仓 22 skipped 原因保留在日志，不把 skipped 当作 pass。
本轮 B HTTP 共 17 项：15 项真实 socket 请求检查与 2 项夹具边界检查。
这些统计含重叠测试，不能相加当作独立用例总数。

相关 A/B 模块：
tests.test_archloop_a_backend_b、tests.test_archloop_a_stage23、
tests.test_archloop_a_batch1_fixes、tests.test_archloop_a_batch2_fixes、
tests.test_archloop_a_batch3_fixes、tests.test_archloop_a_final_fixes。

D 模块：
tests.test_archloop_d_handoff、tests.test_archloop_d_fix_tasks、
tests.test_archloop_d_adapter、tests.test_archloop_d_http、tests.test_archloop_d_acceptance。

在核验过的共装目录内复现 D：
```sh
python -m extensions.architecture_workspace.d_handoff_smoke --test-fixture-only --output /absolute/new/b-d-fixture
```

### 核验要点

预演的数据库字节、文档记录、草稿、代码/架构 HEAD 与现有人审授权保持原样；
实际保存与预演图一致。缺文件/工作树补文件/错误行号/坏引用受控拒绝。
预演不锁定 revision，另一客户端写入后保存仍冲突。C/D 不能调用受保护图预演。
新正式图发布后，旧草稿的 C 校验和预演均拒绝；错误的 currentContext 不再返回旧草稿基线。

D 的实际函数读取 B 的不可变包及真实第二 clone，六字段引用完全一致。
planning 三个代码绑定字段保持 null；已保存的规划来源对象在第二 clone 本地 fetch 后核验。
不同来源仓库、脏工作区、不存在的固定来源拒绝；未保存内容保留。
D 没有写正式图，代码工作区不变。真实 A 浏览器操作、真实 AI 和公网均未在本轮验证。

### 失败及修正记录

- 第一轮 D smoke 夹具重复给已经 clone 的架构仓库添加 origin，Git 拒绝；
  修正为已有 origin 用 set-url、无 origin 才 add，换全新目录重跑 12 项通过。
  不是 D 消费函数失败，旧现场和日志保留。
- diff 检查发现三个新文件末尾多空行；最终移除。
  全套测试运行于上述本地代码 SHA；之后应用 Python 文件字节全部不变，
  只有会话测试文件末尾空行改变，124 个 Python 文件的 AST 全部一致。
  最终证据/说明提交不声称重新跑了全套测试。
- 可发布的日志只规范化本机运行根和临时目录，保留警告、跳过与实际结果。
  私有 SQLite、会话/CSRF/原授权令牌不上传。

原始详情对应 verification/continuation-2026-10-08-*。
verification-summary.json 包含来源、每项结果、源码 hash 与修正记录。

## Project Model Impact

MINOR。

Reason：仍在 B 的草稿、候选校验、人审与版本治理职责内。
没有改变正式图版本包、语义摘要、成员所有权或已确认 Project Model。
公网权限方案为待确认设计；原先的新职责 UPDATE 建议也仍需负责人在真实界面批准。

## Risks / Follow-up

1. A803c 已有真实 B Service/Gateway 适配及 C 函数转换；远端整合只纳入较早 B，
   本轮新 surface/预演/会话修复仍需 A 将自己的 B 追加提交纳入新整合分支。
   BackendB.REF 的旧来源文字也由 A 更新。
2. 公共合同仍为 CONTRACT_V1_DRAFT；不能把隔离组合 pass 当作共同冻结。
3. A 每次 review_preview 新建会话；B 不逐出有效会话，到 128 时受控拒绝。
   A 需要协调真实浏览器会话复用/注销，不能从 actor 名称续权。
4. A 的同版 handover/FixTask 仍有兼容格式；实际 D 入口未在 A803c 公共路由注册。
   D 调用须绑定 B 正式 mapRevision，不能把 A maprev-* 当正式版本。
5. 公网尚未部署。按 PUBLIC_DEPLOYMENT_PREPARATION_2026-10-08.md 协调：
   A 的 HTTPS/Host/Origin/登录/代理边界、B/D 的受信会话适配、云主机域名和持久目录。
   不能通过重写 Origin 为 localhost 绕过现有安全判断。
6. 跨会话/重启后的可信发布恢复和完整候选离线追溯协议仍待 A/C/D 协调。
   T01–T28、跨网络设备访问、真实 AI 与真实负责人模型批准仍不写完成。
7. 仅上传自己的 B 分支和 Draft PR51。main 与他人分支不改；没有 merge 授权。
