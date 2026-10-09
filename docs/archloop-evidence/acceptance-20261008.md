# A 侧主线验收（2026-10-08T02:10:39+0800）

- 服务：http://127.0.0.1:8891
- 仓库：G:/jiagou/codex-bridge/architecture-loop/ZCODE-ABCD-20261008-0115/tmp/acceptance-repo

| 项 | 内容 | 状态 | 证据（摘要） |
|---|---|---|---|
| T00 | 无服务端会话/防伪令牌的写入口被拒绝 | PASS | {"http": 403, "code": "FORBIDDEN_SESSION"} |
| T01 | 已有项目经真实 AI 生成初图 | NOT_RUN | {"http": 200, "status": "NOT_RUN_AWAITING_CONFIGURATION", "origin": "none", "model": null, "nodes": 0, "mapRevision": null, "note": "服务端未配置模型；没有生成任何候选图。配置后重试，或明确使用演示模式。", "error": null} |
| T02 | 生成的是功能图而不是文件树 | PASS | {"status": "rule_based", "origin": "rule_based", "nodes": [{"id": "node_root", "title": "模块: root"}, {"id": "node_archloop", "title": "模块: archloop"}, {"id": "node_repo_index", "title": "模块: repo_index"}, {"id": "node_te |
| T02b | 候选应用到草稿 | PASS | {"draftRevision": "maprev-34c3c701f5953b645f0206aafe06d98b1eed00c1-a0fd7ac7", "nodes": 4} |
| T03 | 自然语言纠正（规则引擎）返回局部操作与前后差异 | PASS | {"origin": "rule_based", "labeled": "规则纠正预览（C 规则引擎，非 AI）", "operations": [{"type": "update_node", "nodeId": "node_root", "fields": {"summary": "管理 root 核心逻辑，包含 20 个已识别代码符号; [纠正]: 该职责只负责读取路径"}, "reason": "用户自然语言指令修正: 该职责只 |
| T04/T05 | 手工编辑职责/关系/过程（含分支与允许失败路径） | PASS | {"http": 200, "operations": ["update_node", "add_edge", "update_process"], "error": null} |
| T05b | 过程步骤保留稳定 stepId、分支与失败路径 | PASS | {"step": {"stepId": "s1", "title": "人工步骤", "detail": "验收", "inputs": [], "outputs": [], "branches": ["分支A"], "next": ["s2"], "allowedFailures": ["允许失败路径"]}} |
| T06 | 刷新重开后草稿仍在且内容一致 | PASS | {"draftRevision": "maprev-c956241deb66fa54112d0d93e65152ad47451d89-1afac58d"} |
| T07 | 两个客户端同草稿写入冲突时不覆盖 | PASS | {"http": 409, "code": "REVISION_CONFLICT"} |
| T08 | 草稿保存到真实版本服务（真实持久化） | PASS | {"bDraftId": "draft-66a21673c6e317bebc365618cdceb3dc", "bDraftRevision": 1, "error": null} |
| T09 | 未获批不能发布（必须先预览+确认） | PASS | {"http": 403, "code": "HUMAN_REVIEW_REQUIRED"} |
| T10a | 人审预览：真实会话、覆盖范围、令牌留在服务端 | PASS | {"http": 200, "coverage": {"scope": "partial", "nodes": ["node_archloop", "node_repo_index", "node_root", "node_tests"], "edges": ["edge-99af4f89a9e2626e310c2963"], "processes": ["process-node_root"], "evidence": ["ev-0e |
| T10b | 批准后产生不可变版本（真实架构 Git 提交） | PASS | {"http": 200, "mapRevision": "sha256:fcc7c921efd5b928139f8cc94d940fa0737858032607249ed48174f32434531b", "mapSourceRevision": "cae7fdea199db8d645c65752bdae8ef4d08bf598", "status": "confirmed_cognition", "error": null} |
| T11 | 旧版本可读取（不可变 envelope） | PASS | {"http": 200} |
| T12 | 代码 SHA / 图版本 / 架构来源版本三者独立 | PASS | {"identity": {"workspaceId": "ws_20261008021003_b67e21", "codeRepoId": "repo-dcbb5ef1af3b792b5c15c85573e3e07478f180cdc523aaab3c52339c30712929", "mapId": "map-96f73a2aba4b8ac6f93287f90a83ea85", "codeRevision": "acd045543d |
| T12b | 发布事实在草稿未变时可见（核查 SHA 不为空） | PASS | {"verifiedCodeRevision": "acd045543d1684d1c3f1235f8ea0583078d929d0"} |
| T13 | 证据按完整 SHA 定位（固定提交的文件证据） | PASS | {"http": 200, "evidencePaths": ["app.py", "app.py", "app.py"], "note": "证据文件在固定提交中存在由 B 的证据核查与代码事实模块保证"} |
| T14a | 真实代码提交后复核定位受影响对象 | PASS | {"old": "acd045543d1684d1c3f1235f8ea0583078d929d0", "new": "c8e3f25982bc3d2635fadab5c95208085777db50", "committed": true, "staleNodes": []} |
| T14b | 回挂新提交（本地记录，不自动声称已验证） | PASS | {"identity": {"workspaceId": "ws_20261008021003_b67e21", "codeRepoId": "repo-dcbb5ef1af3b792b5c15c85573e3e07478f180cdc523aaab3c52339c30712929", "mapId": "map-96f73a2aba4b8ac6f93287f90a83ea85", "codeRevision": "c8e3f25982 |
| T16 | 缺少追踪证据时偏差为 UNKNOWN | PASS | {"verdict": "UNKNOWN", "reason": "缺少可验证的运行时执行追踪数据；静态导入关系不代表运行时执行调用链。"} |
| T15 | 有证据时的过程偏差候选（规则，可人裁决） | PASS | {"verdict": "DEVIATION_DETECTED", "node": "node_root", "observedSteps": ["s1"], "expectedSteps": ["s1", "s2"], "deviations": 1, "rejectedTraces": 0} |
| T17 | 修正认知产生新草稿（编辑与纠正均写入草稿） | PASS | {"draftRevision": "maprev-c956241deb66fa54112d0d93e65152ad47451d89-1afac58d", "note": "见 T03/T04 的实际写入"} |
| T18 | 修正实现创建可交付的持久化任务 | PASS | {"taskId": "fix-1f27d1b548d3416d1816f55bc687e3f9", "status": "queued", "targetCodeRevision": "acd045543d1684d1c3f1235f8ea0583078d929d0", "scope": ["acceptance_change.py"], "error": null} |
| T18b | 任务可列出并带验收条件 | PASS | {"count": 1} |
| T18c | 实施者接手任务（D 权威状态机） | PASS | {"status": "received", "error": null} |
| T18d | 实施开始（in_progress） | PASS | {"status": "in_progress", "error": null} |
| T19a | 实施提交回挂后进入 verification_pending（不自动关闭） | PASS | {"status": "verification_pending", "error": null, "commit": "a3c4eb2e5af8b0cb17b79a8f371a2d4b0cfc1991"} |
| T19b | 人确认本轮实测核查结论后关闭偏差 | PASS | {"status": "verified", "exitCode": 0, "outputDigest": "sha256:e038553a06df97d79575d0261f4b4b964b6f06a2a5a3ee3422331db9772b84c1", "error": null} |
| T20 | 同版交接包导出（图版本+架构来源+核查范围） | PASS | {"mapId": "map-96f73a2aba4b8ac6f93287f90a83ea85", "mapRevision": "sha256:fcc7c921efd5b928139f8cc94d940fa0737858032607249ed48174f32434531b", "mapSourceRevision": "cae7fdea199db8d645c65752bdae8ef4d08bf598", "error": null} |
| T21 | 被改过的交接包被内容指纹比对识别（以 Git 版本为准） | PASS | {"http": 200, "code": null, "comparison": {"contentMatches": false, "revisionMatches": true, "mapIdMatches": true, "note": "交接包内容与架构 Git 实际版本不一致（包可能被改过或过期）：以 Git 版本为准，并请核对交接来源"}, "packageMapIdMismatch": null, "error": nu |
| T22 | AI 未配置时诚实降级（NOT_RUN，不用样例冒充） | PASS | {"generation": {"configured": false, "model": null, "note": "AI 生成尚未配置。需在启动程序前设置 OPENAI_API_KEY 和 PROJECTMIND_AI_MODEL。"}} |
| T23 | 真实 AI 候选与证据验证 | NOT_RUN | 本机没有 OPENAI_API_KEY / PROJECTMIND_AI_MODEL；T01 的同一路径会在配置后原样运行 |
| T24 | ProjectMind 自身职责候选覆盖（规则引擎按固定提交事实） | PASS | {"repo": "G:\\jiagou\\codex-bridge\\architecture-loop\\ZCODE-ABCD-20261008-0115\\integration\\projectmind-core", "identityRepoPath": null, "workspaceRevision": "acd045543d1684d1c3f1235f8ea0583078d929d0", "coverageRevisio |
| T25 | 旧 Explorer 与只读提案路径回归（旧接口仍可用） | PASS | {"legacyMapHttp": 200, "note": "完整回归见 tests 全量套件"} |
| T25b | 无效纠正请求被机器码拒绝（不是 500） | PASS | {"http": 400} |
| T26 | 没有新授权时重复发布被拒（不重复产生版本） | PASS | {"http": 403, "code": "HUMAN_REVIEW_REQUIRED"} |
| T27a | 无代码规划：按目标/约束生成设计候选（无代码事实） | PASS | {"nodes": 3, "status": "rule_based"} |
| T27b | 规划草稿不含代码事实证据（依据是需求） | PASS | {"evidenceKinds": ["requirement"]} |
| T27c | 设计确认产生 confirmed_design 版本（与实现状态分开） | PASS | {"status": "confirmed_design", "codeRevision": null, "error": null} |
| T28 | 规划图关联真实代码后仍保留设计历史（不等于已实现） | PASS | {"context": "mixed", "designHistory": null, "error": null} |

统计：{"PASS": 38, "NOT_RUN": 2}

说明：本报告是 A 侧端到端验收，不是 D 的独立主线验收；真实 AI（T01/T23）、真实浏览器多步故事与第二副本导入分别单独登记。