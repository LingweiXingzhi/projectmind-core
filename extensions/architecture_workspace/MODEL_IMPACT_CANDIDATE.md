# Project Model Impact：UPDATE / USER_MODEL_REVIEW_PENDING

工程实现新增架构工作区，不再把代码事实解析与正式认知治理合为一个职责。
以下仅是给 C/A/负责人的职责更新候选，开发 Agent 未批准真实 Project Model。

| 候选职责 | 已有代码证据 | 与其他职责的边界 |
|---|---|---|
| 架构草稿与稳定身份 | service.py open_workspace/create_draft/apply_draft_operations；schema.py | C 产生候选，B 保存受校验的内容；布局不是职责变化 |
| 人审事务与核查边界 | review.py HumanReviewGateway；service.py record_review | A 提供用户会话/真实请求，B 绑定实际预览；worker 没有发布令牌 |
| 认知版本与 Git 来源 | service.py publish_reviewed_graph/get_version/export_version；git_publication.py | 架构 Git 候选分支独立；代码只读；负责人决定正式发布/main |
| 共享/恢复/冲突保护 | storage.py BEGIN IMMEDIATE/CAS；service.py import_git_version/graph_snapshot | D 消费同版包并验收；B 不接管其 FixTask/接续实现 |

接口：B_CONTRACT_CANDIDATE_V1.md 与 examples/exchange-fixture.json。
C 可按 Git 提交中这些实现生成带代码证据的新职责候选；文件/符号放详情，
不把每个文件变成主功能节点。确切代码 SHA 和追加提交来源见对应 Draft PR。
正式图内容由人在 A 的工作台审核；尚未实现该 UI 的接线，不冒充已批准图。

测试夹具的 confirmed_design/confirmed_cognition 仅针对 example.invalid 的小仓库。
正式 Model 仓库、data/project-map.json 和产品 main 保持原状。
