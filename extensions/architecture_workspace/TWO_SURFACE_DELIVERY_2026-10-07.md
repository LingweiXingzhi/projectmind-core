# B 双面接口 · 实现、自检与交付

## Result

本轮把 B↔A 操作面、B↔C/D 协作面的设计实现为可选 Python facade，
完成真实 SQLite/Git 与合成 HTTP 验证，代码已上传王海宁独立分支。
B_IMPLEMENTATION_CANDIDATE / LOCAL_DONE；公共 CONTRACT、INTEGRATED、D_VERIFIED、
最终 A 独立审计和真实 Project Model 人工批准仍 pending。

固定基线仍是 c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db。
实际测试代码本地提交：13a6c3b20393eb33e1bacb2acf9f1c983a4b65ed。
对应远端代码提交：4d03906976c41a25e361f515f0f06a2d6a9484d3。
两者完整代码树一致：2322c4de651310d79cacdd92c44ab5bcf73e78a1。
后续证据提交只添加本文件、日志、实际 fixture JSON 和 README 索引；
最终 121 个已追踪 Python 文件 SHA256 仍与被测代码一致，不把文档追加说成另一次全仓执行。

本轮 A/C 真实分支已有进展，但不是单一冻结合同：
A/integration b75ad820e0d31e3dadf842b414f6950b5aa46102，
C 55ea6466583d98e0f466e5d4055922ef4aeecb12。
按任务范围实现 B 独立部分，保留 V1，不把 actor-only POST 接成发布授权。
完整差异见 AC_ALIGNMENT_2026-10-07.md。

## Files Changed

- surfaces.py：受保护操作面、限定 C/D 角色/工作区/精确版本的读取面，原始授权不向浏览器输出。
- proposals.py：八字段 context、固定候选摘要、初图/patch、完整接受/修改/拒绝映射与组内顺序。
- service.py：兼容旧入口；候选固定/草稿/选择审计同事务；创建/打开完整上下文 CAS。
- fixture_http.py：仅专用合成仓库的临时 loopback HTTP 适配例，不注册 Core 路由。
- surface_smoke.py：新 CLI，全流程 21 次真实 facade 调用、planning/mixed 与固定版本双 clone。
- 四份 test_archloop_b_* 新测试、接入/合同差异说明、实际 fixture 与原始归一化测试日志。

仅改 B 目录和 B 测试。app.py、extension_host.py、共享 web、A/C/D 文件、公共合同、
正式 Model、main 和其他成员分支均未由本轮修改。
历史原型、旧展示归档和原不可变版本未覆盖。

## Verification

在代码提交 13a6c3b20393eb33e1bacb2acf9f1c983a4b65ed 执行完整回归与新 CLI。

| 检查 | 实际结果 |
|---|---|
| B 组合测试 | 127 tests / 44.407 秒 / OK，无 skip；其中新增 81 项 |
| 完整项目回归 | 731 tests / 182.570 秒 / OK，22 skipped、709 实际执行 |
| 新 HTTP 测试 | 已计入两套测试；16 项（14 真实 socket，2 启动限制）通过 |
| 独立 CLI | 21 次实际调用、17 项检查 PASS；当时 Git 工作区干净 |
| 固定版本 | 发布原包、D 导出、第二真实代码/架构 clone 的 immutable packet/六字段引用一致 |
| planning→mixed | null 代码设计版本保留；关联后新草稿仍需审阅，旧设计历史未覆写 |
| 源码一致性 | 121 个 Python 文件内容摘要在测试后未变化；上传树与本地核对 |

实际 HTTP 检查包含缺省/错误 Origin、错误 Host、CSRF、重复 cookie/header、
跨会话确认/发布、body 伪造、完整发布、严格 JSON/大小/长度/超时和无请求日志。
测试用 HTTP 真实 peer/cookie/header，不能把这里的 PASS 当 A 公共 handler 已接通。

最初 15 项 HTTP 检查为 14 PASS/1 FAIL：一项测试误要求底层 V1 私有 SQLite 完全没有
publicationToken。既有 intent 私有存储保存原重试响应，文件权限 0600；
改为检查公开响应/实际提交版本/源文件无原授权，session/CSRF 不落盘以及无请求日志。
没有为迁就断言改变旧授权算法。原失败记录保留在 verification/two-surfaces-summary.json。
子代理沙箱曾阻止 TCP bind；根代理正常上下文实际运行，未把阻塞称为通过。

并行源码审阅推动修复并测试：mixed 上下文、完整上下文创建竞态、旧批准重放的 canPublish、
候选组内顺序、旧代码/旧正式基线的编辑提示、128 项预览缓存和累计拒绝项上限。
累计拒绝上限在保存前原子拒绝，避免已保存的合法草稿无法预览；失败保留此前记录。
这属于实现者与并行代理自检，不填写最终独立 A AUDIT PASS。

日志保留旧测试 ResourceWarning，不隐去失败/跳过；只替换本机根/临时/运行时路径。
本机完整原日志与 source manifest 在仓库外 evidence/two-surfaces/root，未上传私人路径。
公开证据：verification/two-surfaces-b-tests.log、two-surfaces-full-regression.log、
two-surfaces-summary.json、examples/two-surfaces-actual-fixture.json。

复现：

```sh
TMPDIR=/private/tmp python -m unittest discover -s tests -p 'test_archloop_b_*.py' -v
TMPDIR=/private/tmp python -m unittest discover -s tests -v
python -m extensions.architecture_workspace.surface_smoke --test-fixture-only --output /absolute/new/surface-fixture
```

Python 3.10+ 与 Git，无新第三方依赖。最后命令不接受已存在/相对/仓库内目录。
所有人审与 C/D 候选都是明确夹具；不批准真实 ProjectMind 项目。

## Project Model Impact

MINOR。

Reason：B 现有的草稿、审阅、不可变版本和协作治理职责内增加适配与一致性校验；
保留 V1 图/版本语义与 owner 边界，没有改正式 Model。
最初交付的 UPDATE 建议继续等待人工批准，不被本轮自检自动定稿。

## Risks / Follow-up

1. A 草案的图/仓库/图版本/草稿 CAS 和 actor-only 发布请求与 B 不同，A 需确认统一合同并接真实会话。
2. C 新纯函数尚未接 extension dispatch；候选字段/目标与固定证据需统一，不能猜节点或丢失未知项。
3. D 产品同版交接、实际 A UI、真实 C 推理、新主线 T01–T28 和 Windows 原生未执行。
4. facade 的授权引用绑定在内存；V1 私有数据库的原响应不恢复新会话权。重启后保留冻结现场，
   受控跨会话恢复待 A 确认；不能清库/reset/凭同名 actor 自动发布。
5. 正式版本仍复用相同语义的原版本/审阅记录；新选择审计保存在本机，完整候选离线追溯需三方冻结。
6. 同 OS 账户任意代码执行不在 facade 隔离保证内；本机 actor 仍为 local_operator_declaration。

分支：feat/50-architecture-workspace-b-wang-haining。
草稿 PR：https://github.com/LingweiXingzhi/projectmind-core/pull/51。
维持 Draft，不合 main/旧 integration。至少两位队友明确确认及明确合并指令后才可能合并；
测试、CLEAN/MERGEABLE 和自动上传都不是合并授权。
