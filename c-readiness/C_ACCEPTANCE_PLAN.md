# C_ACCEPTANCE_PLAN — Map Proposal 验收计划(20 fixtures + 通过标准)

> 今晚不写 C;本文件把 fixtures 和通过标准定死,Stage 0–6 每步都有可运行的验收。

## 通用验收环境

- 固定 repo fixture:一个小型 git 仓库(含预先构造的 commits),不依赖 projectmind-core 本体(避免 main 漂移导致 fixtures 失效);projectmind-core 真实 diff 只做冒烟。
- 每个用例 = (SuggestMapRequest 输入, 期望输出断言)。断言检查 proposals/unresolved/no_proposal 三个桶,不比较自由文本全文。
- 全部用例必须确定性:同输入两次运行输出一致。

## Fixtures(F1–F20)

| ID | 场景 | 期望 |
|---|---|---|
| F1 | 新增模块文件(新目录+新 class,地图无对应 node) | 1×NODE_ADD,evidence 含 git_diff+code_fact,confidence≥low,human_required=true |
| F2 | 已有 node A 的文件新增 import 到已有 node B 的文件 | 1×RELATION_ADD(from A→B),rationale 引用两侧 node |
| F3 | A→B 的 import 被删除 | 1×RELATION_REMOVE_CANDIDATE(候选,不武断) |
| F4 | 文件改名(old→new),内容不变 | 1×IMPLEMENTATION_LINK_CHANGE 指向受影响 node;不得产生 NODE_ADD |
| F5 | 文件移动到子目录 | 同 F4 类(路径更新候选);若地图 evidence path 匹配失败必须列出 unresolved |
| F6 | 内部重构(函数体改,声明签名/位置不变) | no_proposal(或 0 proposal);可给出显式原因 |
| F7 | 仅注释变化 | no_proposal + reason=comments_only |
| F8 | 仅格式化(空白/引号) | no_proposal + reason=formatting_only |
| F9 | 同一职责文件内新增 class | 不产生 NODE_ADD(职责未变);可选产生 unresolved=信息提示;**不得**建新 node |
| F10 | 文件内新增 helper function | 同 F9:无 proposal |
| F11 | 地图过期:文件早已删除但 node 还在,evidence path 全部 404 | NODE_REMOVE_CANDIDATE(候选用词)+ rationale 说明地图可能过期 |
| F12 | Context Pack 带 known_conflicts 的 key 与本差异相关 | 该 key 不得进入任何 proposal 的依据;输出 limits 注明 conflict 被排除 |
| F13 | B 返回 skipped 文件(解析失败)恰好是变化文件 | unresolved(NEEDS_HUMAN_REVIEW),不得基于猜测生成 NODE_ADD |
| F14 | 证据缺失(新文件但 code_facts 无条目且 diff 无内容可引) | 0 强 proposal;unresolved 输出 UNKNOWN/NEEDS_HUMAN_REVIEW |
| F15 | base==target(无变化)但地图内容与上次不同 | 0 proposal + limits 注明"same revision, map drift is not C's scope" |
| F16 | node entryPoint 指向的函数被改名 | 1×RESPONSIBILITY_CHANGE(候选)或 IMPLEMENTATION_LINK_CHANGE,rationale 引 code_fact 行号 |
| F17 | 变化可匹配多个 node(两个 node 的 evidence 都含该文件) | proposals 生成候选但 confidence≤medium 且 uncertainty 必须列"multiple candidate nodes";或落 unresolved |
| F18 | 无任何交叉信号(diff 文件与地图/code_facts 无关联) | no_proposal(0 proposal、0 unresolved 强结论) |
| F19 | 依赖样信号但证据不足(字符串拼接 import、动态路径) | unresolved(NEEDS_HUMAN_REVIEW);不得 RELATION_ADD |
| F20 | 人工否决记录存在(输入带 prior_decisions:同 subject 上一轮被 REJECT 且理由不变) | 默认不重复生成同类 proposal;或在 limits 声明被抑制(实现二选一,验收按其声明) |

## 分阶段验收门槛

| Stage | 必须绿的 fixtures | 额外验收 |
|---|---|---|
| 0 读 Context Pack | — | pack validate 失败 → 拒绝消费(单测注入毒包=poisoning P05 同款,必须硬停止) |
| 1 接 Git diff | F15, F18 | diff 口径与 A 的 /api/compare 一致(同 revision 双跑对比) |
| 2 接 B Code Facts | F13, F10 | revision 不匹配拒绝;skipped 不进事实 |
| 3 candidate evidence model | F14, F17, F19 | evidence 链 schema 校验(结构测试) |
| 4 产生 MapProposal | F1, F2, F3, F4, F5, F6, F7, F8, F9, F16, F11 | 输出全 JSON 可解析;status/human_required 恒定;同输入双跑字节一致 |
| 5 human accept/reject flow | F20 | proposal_id 稳定;状态只由人翻转 |
| 6 A integration | 冒烟:真实 core diff 一轮 | extensions/map_proposal 被 ExtensionHost 发现;不破坏 172 既有测试 |

## 反目标(验收也查)

- 输出含 position 修改建议 → FAIL
- proposal.status ≠ PROPOSED → FAIL
- evidence 为空仍给出强结论 kind → FAIL
- 用 research/proposal/historical/stale claim 作为 rationale 支撑 → FAIL
