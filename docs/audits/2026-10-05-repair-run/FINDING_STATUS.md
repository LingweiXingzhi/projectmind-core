# FINDING STATUS — 审计发现对账表

基线: G:\jiagou\PROJECTMIND_FINAL_INDEPENDENT_VERIFICATION.md / .json (AUDIT_BASELINE = VALID)
冻结审计基线 SHA: C=4d1b3fc D=8f00be38 BCD=deb9b9ff UI=674c70f (其余为依赖基线)

状态词汇: OPEN / FIXED_PENDING_REVIEW / CLOSED_BY_CODEX / DEFERRED_WITH_REASON
规则: 新测试绿 ≠ CLOSED。只有 Codex 独立 Review 通过才可 CLOSED_BY_CODEX。

终态（2026-10-05，依据最终 Codex review 与最终审计游标）:
全部 15 个 finding 已完成终态对账：14 个 CLOSED_BY_CODEX，1 个 HOST-01 为 DEFERRED_WITH_REASON。
最终游标: c=65a7c480e7fa2656e55771c3cc001cf8117f59ad, d=2ed56da28403d5703cb6e3ec3af20bbc1e7360eb,
bcd=1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d, ui=d4e3f2a71f07af358bd6d0e262bfc210c420084b（详见 REVIEW_CURSOR.json）。

## HIGH

| ID | 主题 | 状态 | 备注 |
|---|---|---|---|
| C-01 | 关系删除只证一个 target 文件却宣称整个 target domain 消失 | CLOSED_BY_CODEX | 439ed5b：节点级双向域证明 + 每对一次 verdict |
| C-02 | B skipped 准入未覆盖完整提案证据域 | CLOSED_BY_CODEX | d27a434：domain_gate 集中准入 + wanted 扩域 + 可见 HUMAN_REQUIRED |
| C-03 | CA T3 head 校验不区分主体，可能错误释放冲突 | CLOSED_BY_CODEX | ba4a78d：subject-aware typed head 语义 |
| V-01 | acceptance_matrix 将 SkipTest/缺测试/弱 INPUT_HASH 记为 PASS | CLOSED_BY_CODEX | f31521c：显式结果分类 + 真 S30 绑定 + 全量 INPUT_HASH；矩阵 30/30 两轮稳定（证据见 artifacts/matrix_c_v1.md） |

## MEDIUM / validation

| ID | 主题 | 状态 | 备注 |
|---|---|---|---|
| C-04 | entries=[] 可支撑 NODE_ADD | CLOSED_BY_CODEX | 3abfc75：缺失记录与空 declarations 一并 HUMAN_REQUIRED |
| C-05 | 尾名匹配混淆完整符号身份 | CLOSED_BY_CODEX | 3abfc75：全点分身份匹配；oracle 保留（入口符号真消失仍触发） |
| C-06 | 不支持的 import 语义静默消失，无 UNKNOWN | CLOSED_BY_CODEX | 3abfc75：直接/别名 import_module 为动态信号；src-layout 等未解析内部 import 可见 limit+HUMAN_REQUIRED；65a7c48：命名空间包（无 __init__.py）目录段匹配补丁，终审复验通过 |
| C-07 | 缺失/skipped base-B 对比沦为普通 no_proposal | CLOSED_BY_CODEX | 3abfc75：地图域内比较不可用 → 可见 HUMAN_REQUIRED（A8/G-3） |
| C-08 | facts/entryPoint 路径校验不完整 | CLOSED_BY_CODEX | 3abfc75：supplied facts 路径与可解析 entryPoint 路径全部 validate_path（S28） |
| V-02 | mutation_runner 错分类 INVALID/ANCHOR_DRIFT | CLOSED_BY_CODEX | 7d70955+db4349f：语义分类词汇 + 合法性管线（parse+绿基线）+ M2/M3/M4 重定义到当前源；实测 SEMANTIC_CAUGHT 6/6（artifacts/mutations_c_v1.json） |
| D-01 | Worklog store 受继承 GIT_* 环境影响 | CLOSED_BY_CODEX | a507541：显式 repo 恒胜，GIT_* 全清洗，共享 repository_storage_folder；终审 CLOSED（无保留，注入 GIT_DIR/GIT_WORK_TREE/GIT_COMMON_DIR 三向验证） |
| D-02 | Continuity 存储位置依赖 Worklog Store 构造副作用 | CLOSED_BY_CODEX | 26bc398：直接用无副作用 context；Worklog 库损坏不再波及 Continuity |
| UI-01 | added/deleted/renamed 证据链接用错源 | CLOSED_BY_CODEX | d4e3f2a：纯函数 evidenceTargetsFor（A/M→target、D→base、R→old@base+new@target、未声明不渲染链接）+ node 回归 + 受控 404 契约测试；终审 CLOSED（无保留，真实 HTTP 200/404/400 验证） |

## LOW

| ID | 主题 | 状态 | 备注 |
|---|---|---|---|
| D-03 | 畸形 checklist state → 裸 TypeError/500 | CLOSED_BY_CODEX | 2ed56da：先类型校验再集合成员判定；worklog category 同类加固；终审 CLOSED（无保留，10 次畸形输入全受控 400） |
| HOST-01 | 载入期 BaseException 隔离窄于运行期 | DEFERRED_WITH_REASON | LOW：加载期 GeneratorExit/KeyboardInterrupt 隔离需保留操作员中断语义，按 §22 不盲目扩捕获；已列入 NEXT_TEAM_DIVISION 的 A 队 NOW 项 |
