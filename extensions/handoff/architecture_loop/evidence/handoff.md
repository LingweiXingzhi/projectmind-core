# 同版架构交接

状态：待本机 Git 核对；参与者记录不等于独立验收。

- codeRepoId: repo-d1e316215a868ed17930b570a252c08967c4f92817f15b24565a33dcfb942978
- mapId: map-fixture
- codeRevision: b409a98e019a9de492cd542cca72990d181657a8
- mapRevision: sha256:1e535b8c077338aba76d7d22163200469035eb27836214b0046db63f47107d67
- verifiedCodeRevision: None
- status: confirmed_cognition
- mapSourceRevision: a7b8e554bfa7e451d2276cc80388ab42d5df592d

下一步：核查来源与固定版本

核查范围：{"scope": "all", "nodes": ["node-A", "node-B", "node-C"], "edges": [], "processes": ["process-ABC"], "evidence": ["code-flow", "goal-process"]}

未知与限制：
- TEST_ONLY_SIMULATED_HUMAN
- 核查仅适用于列明覆盖；不证明运行时全流程
- 传输摘要仅检查内容一致，不认证来源或操作者。
- 日志/候选/反馈保留参与者记录状态；未核查运行行为为 UNKNOWN。
