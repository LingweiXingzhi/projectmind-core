# B 复用核查

固定起点 c3d524dc2c61b03e6df55ed416d3cefaf2cbb4db。
开工前 GitHub refs/PR 只读核验：32 分支、现有 PR 至 #49，无新 architecture_workspace。
集成 ref 仍为该 SHA，main 仍为 7484d44ddeac3c054ca3ba68f92293d965bb615c。
打开的 #39/#41/#43/#48/#49 不代表成果未集成；实际代码已在起点。

| 能力 | 已有证据 | 复用/缺口 |
|---|---|---|
| Python 符号、静态导入、固定 SHA 浏览 | repo_index/**；#39 已含在基线 | 保留，不重写 parser |
| Git 固定对象与环境隔离 | repo_index/gitio.py | 直接复用 read runner、root 校验，代码无写操作 |
| legacy map/snapshot | app.py load_map/build_snapshot；data/project-map.json | 只读导入六节点图为未确认草稿 |
| 独立扩展 seam | extension_host.py、EXTENSION_INTERFACE.md | 新目录自动发现；旧 seam 无人审元数据，只开放读 |
| 候选与 CA | extensions/map_proposal/**、context_authority/** | C 使用只读快照；不改六类规则、registry 或其权限 |
| 地图来源建议 | MVP_INTERFACES 的 digest/confirmedForRevision:null | 继承“代码 SHA 不证明图版本”；新增语义/来源/核查三身份 |
| 交接/接续 | handoff/continuity mapRevision=UNKNOWN | 给 D 不可变 Git 版本包；不修改其现有实现 |
| 持久图、人审、版本/冲突 | 基线无 architecture_workspace 和七个新入口 | 本轮 B 的新增范围 |

Model 仓库 main 只有 README；产品方向文件位于 docs/open-source-mvp-proposal：
docs/drafts/PRODUCT_INTENT.md（blob ec0e7072a7369d8591f98e0b70a414fe1b33e87c）、
docs/PROJECT_ANALYSIS.md（blob 05909bda0388dc4c7e3bad3f1f0d2664705296bb）。
其状态为产品意图/整合与提案，不是批准的长期工程 schema。
旧“编辑待确认”已被本轮明确任务更新。正式 Model/main 不在 B 写入范围。

访问记录：Git CLI ls-remote exit 128，未获 CLI 凭据；
通过正常授权 GitHub connector 读取完整固定文件树，逐 blob/树/提交摘要验证，
构建精确浅 Git checkout，含基线及其父提交，未声称下载全部原始历史。
原有 checkout 未更新或覆盖。本轮只新增 B 自有目录/测试。
