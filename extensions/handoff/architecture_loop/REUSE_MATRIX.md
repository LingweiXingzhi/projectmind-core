# D 复用矩阵

固定产品基线：c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db。
远端来源核对经 GitHub API；CLI ls-remote 因无凭据退出 128，未当作同步成功。
177 个 baseline blob/tree 按 Git 对象哈希校验，精确恢复 commit metadata；独立副本没有覆盖旧 checkout。
本地基线是明确 shallow boundary，不宣称完整历史。初次回归的浅边界/本地 clone 异常按真实结果保留。

| 能力 | 既有证据 | 复用 | 本轮新增缺口 |
|---|---|---|---|
| 固定代码与来源 | handoff/handoff.py、continuity/inspection.py | Git 环境隔离、来源、不执行导入命令、原 UNKNOWN | B 版本 envelope、图来源 Git 对象、第二 clone 一致性 |
| 交接与接手 | continuity/store.py、model.py | 原 SQLite/连接、原接续任务 ID、参与者反馈与历史 | 同版包引用、FixTask CAS、任务传递与回挂 |
| 工作日志 | worklog/store.py 的 get/history | 原固定日志版本只读 | snapshot refs 与任务/交接关联，不重做格式或 UI |
| GitHub 关联 | continuity_github/* 已在 baseline | 保留实验入口及数据，不升格为正式身份体系 | 新同版来源仍严格独立于未验证 GitHub 链接 |
| 足迹 | team_footprints/* 已在 baseline | 原样保留 | 本轮无新增热力图工作 |
| 代码事实/浏览/旧提案/CA | repo_index、code_facts、map_proposal、context_authority | 不重写，运行必要回归 | 新主线与旧能力的验收结果分开 |
| B 精确版本 | PR #51 b58fee7455bf8348f50e3863759e53bbd711dc6d | export_version、canonical semantic hash、真实 Git publication | D 的受限消费/核查，不另造发布服务 |
| A 工作台 | b75ad820e0d31e3dadf842b414f6950b5aa46102 | 新 adapter seam 与 machine code | D 注册 factory、缺字段拒绝与接线清单，不改 app/web |
| C 新候选与真实 AI | 本轮可见集成缺实际实现/配置 | 原只读提案继续保持 | 非 D owner；缺少时 BLOCKED/NOT_RUN |

旧 PR 仍 open 不证明未集成：#39/#41/#43/#48/#49 及 CA/早期 BCD 均已在基线树。
现有验收文件指向外部 codex-bridge 证据目录。本机未取得 r51/D3 原件，不复述成新执行 PASS。

写入 owner：extensions/handoff、extensions/continuity、tests/test_archloop_d_*、tests/architecture_loop_acceptance。
没有修改 app.py、extension_host.py、web、B/C、worklog、data/project-map.json、旧 integration 或 main。
