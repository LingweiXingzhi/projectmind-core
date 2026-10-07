# Role C: 复用调查矩阵 (REUSE_MATRIX)

本矩阵记录基线 (c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db) 已有能力、现有证据及本轮缺口开发计划。

| 能力领域 | 现有证据 / 模块 | 复用动作 | 本轮缺口 (需新增开发) |
| :--- | :--- | :--- | :--- |
| **六类规则提案** | `extensions/map_proposal/engine.py` 的 `suggest_map`<br>`extensions/map_proposal/model.py` | 完整复用现有规则分析逻辑；保持 `no_map_write` 只读约束 | 输出适配到新的 Canonical Operation Schema，增加与版本图 (B) 的对比 |
| **代码事实提取** | `extensions/map_proposal/facts_adapter.py`<br>`repo_index/` 静态符号/导入 | 完整复用已验收的 Python AST 与代码变化读取 | 接入两版本 diff 的有界邻接分析，不全仓重复扫码 |
| **CA 架构规约接纳** | `extensions/map_proposal/ca_adapter.py`<br>`extensions/map_proposal/convergence/` | 复用 Context Pack 解析逻辑 | 主线真正串联 CA Pack，记录 admissible / blocked / unknown 日志 |
| **拓扑关系分析** | `extensions/map_proposal/relations.py` | 复用基于 import 的关联分析 | 区分静态引用与期望执行顺序，禁止将 import 伪装为运行链 |
| **无图初图生成 (Bootstrap)** | *当前缺失* | 参考 `suggest_map` 的粗粒度聚类 | 新增 `existing_project` / `planning` / `mixed` 三种模式的生成入口 |
| **自然语言局部纠偏** | *当前缺失* | 无 | 新增根据局部自然语言输入生成局部 Patch 预览的能力，保留未选中 ID |
| **期望过程偏差** | *当前缺失* | 无 | 对照图上步骤与测试/追踪证据，输出可验证偏差或如实 UNKNOWN |
| **真实 AI 传输适配** | *当前缺失* | 等待 A 提供服务端公共 transport | 接入 transport，支持 UNCONFIGURED / NOT_RUN_AWAITING_CONFIGURATION 降级 |
