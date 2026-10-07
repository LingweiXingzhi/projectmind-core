# D 任务接续交付 · 2026-10-07

## 恢复核查

GitHub 原分支/Issue #52/PR #54 均存在；PR 头为 6c51f666a9f5377995953d13e95b4d91397c2184，open/draft/mergeable。D 工作区干净；原 38 文件均在 D owner 范围。没有重建分支或重复 Issue/PR。

新增可复用来源：B 8315c2e67aef2fa532869595441e68c29ae1beb3 已实现双侧 facade；C 55ea6466583d98e0f466e5d4055922ef4aeecb12 已新增候选/偏差函数。固定源码按 Git blob SHA 核对，仅装入临时验收副本；非 D 的运行结果/设计不复制进 D 产品分支。原证据目录保留历史结果，新结果在 evidence/resume/。

## 本次 D 继续完成

- 新增 D 验收器 probe_candidates.py，实际调用 C 的过程偏差函数，以真实 Git 轨迹而非 canned response 驱动 D FixTask。
- 实际观察 A/B 缺 C → C 检测偏差 → D 接手/工作 → 独立分支仅改 flow.py → 真实修正提交 → 测试及实际 C 再核验 → 测试人确认完成。C 再核验已从先前替身升级为实际组件调用，但公共主线/C 模型推理/真实人审仍未完成。
- 实际 B surface smoke 21 次调用/17 断言通过；D 消费 existing/planning 精确包与第二 clone 字节。B 临时 fixture 的原架构 origin 不一致先被 D 拒绝，显式登记这两份测试 clone 的同一 example.invalid 来源后成功；缺后续规划提交时显式同步本地测试 Git，D 导入本身不 fetch。
- 冻结组合 SHA 52085a115f4aaf8457683a18d34875ec1dfd896c 的真实 A 公共 HTTP、Git/SQLite D 演练、T01–T28 状态已重跑；此 SHA 是 D 隔离验收镜像，不是 A 已集成交付。
- D 专项 30 OK；B/C/A/D 专项 222 OK；冻结版本全量 826 项 OK（14 skipped），原始结果见 evidence/resume/full-regression.log。真实 HTTP finding 3 项、实际 C/B 契约 finding 4 项，分开于单元测试通过。

## 集中失败清单（复现证据齐备，按 owner 修复）

| ID | owner | 已观察结果 / 需要修复 |
| --- | --- | --- |
| D-A-01 HIGH | A/B | 同来源不同 clone 的 codeRepoId/mapId 不同；统一稳定来源身份。 |
| D-A-02 HIGH | A | 不带会话/CSRF 的新增 POST 仍 200；公共 handler 接实际保护。 |
| D-A-03 BLOCKER | A | adapter.registered={}；接入真实 B/C/D 后端和服务端上下文。 |
| D-C-01 HIGH | C | 无关轨迹、错仓/错 SHA、缺预期步骤返回 ALIGNED；需检查身份/覆盖并保留 UNKNOWN。 |
| D-C-02 HIGH | C | 相同 workspace/目标条数，内容不同的 planning 图仍同 proposalId；身份须绑定语义内容。 |
| D-BC-01 BLOCKER | A/B/C | 实际 C planning 输出被实际 B validate_proposal 拒绝；冻结统一候选格式，不在 D 猜转换。 |
| D-C-03 HIGH | C | 自身候选图声称 c3d 基线已有 candidates.py，但该 Git blob 不存在；目录引用不能替代准确文件证据。 |

C 的无轨迹 UNKNOWN 正常；已观察实际绕过/修复链可复核。自然语言函数当前只是把 prompt 拼入 role、规则生成按包路径分组；本次不声称真实 AI 语义纠正或功能职责图主线完成。B/C 的现有实现均未由 D 改写。

## D 完成条件与真实剩余

同版/规划交接、修正任务/回挂/验证与独立克隆组件已交付；T01–T28 每项有追溯状态，但“主线关键项全通过”仍不满足。A 公共集成与 schema 契约、C 缺证/身份问题均有具体复现，需对应 owner 在新 integration 修复。真实 AI 未配置、浏览器无可执行文件、物理跨设备无环境，分别 NOT_RUN。截图/录屏没有伪造；自身候选图 T24 证据失败未提升正式模型。最终独立审计 AUDIT_PENDING，不把自查称独立审计。

D 本次只追加验收工具和证据说明，仍复用原交接/日志，不接管 A/B/C 实现或旧 integration/main。#52 保持 open、PR #54 保持 Draft，直至 A 提供新已集成 SHA 后跑真正公共主线复验。

## 最短重跑

```sh
python -m unittest discover -s tests -p 'test_archloop_d_*.py' -v
python -m tests.architecture_loop_acceptance.run --run-d-fixture --output /tmp/new-d-output
# 含固定 B/C 的隔离验收 checkout：
python -m tests.architecture_loop_acceptance.probe_candidates --source-checkout /absolute/validation-checkout --output /absolute/new/c-evidence
```

D fixture PASS 不能代替完整产品，收集器退出 2；C probe 找到问题退出 1。这些是诚实的验收结果，不是可改成 PASS 的成功输出。

Project Model Impact：UPDATE。新职责只提候选，UNKNOWN、AI candidate、contributor log unverified 均保持。
