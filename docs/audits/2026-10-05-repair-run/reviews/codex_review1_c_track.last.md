结论：**FAIL**。C-01/C-02 的核心修复通过受限执行复核；C-03 仍可误判外来主体并释放冲突候选，V-01/V-02 仍存在已复现的假成功分类。

审查仅覆盖 `4d1b3fc..db4349f` 的 9 个文件及指定五项 finding。结束时 HEAD 未变、工作树干净，无文件修改、commit、push 或 merge。

### 逐 finding 判定

| Finding | 判定 | 实际执行证据与观察 |
|---|---|---|
| **C-01** | **CLOSED_WITH_RESERVATIONS** | 用 `python -` 内联脚本执行当前 engine/AST，重建 `import pkg.b` 被删除而 `import pkg.b2` 保留的内容：没有关系删除候选；全部 import 消失时，仍发布唯一 `RELATION_REMOVE_CANDIDATE na->nb`。将 `git show 4d1b3fc:extensions/map_proposal/relations.py` 的原实现载入内存后，残留目标成员测试失败，证明 oracle 能检出旧攻击。保留意见：Git blob/tree 读取使用内存适配，未完成真实临时 Git 仓库复现。 |
| **C-02** | **CLOSED_WITH_RESERVATIONS** | 运行真实 B collector，仅将 Git 传输换成内存内容。未变化 target 的真实语法错误、辅助源真实超过 1 MiB 均进入 B skipped；C 不发布强关系候选，产生包含成员及真实原因的 `HUMAN_REQUIRED`。部分 facts 同样阻断；全 eligible 正例正常发布 `RELATION_ADD`。新增测试本身只注入 skipped，我额外执行了真实 parser/预算判断。保留意见同上：未完成真实 Git 端到端执行。 |
| **C-03** | **NOT_CLOSED** | 运行真实 CA registry loader、builder、resolver、validator 和 C admission；registry 内容通过内存对象提供。合法 global baseline==base 被确认且冲突继续压制；错误 baseline 产生矛盾；普通 component/PR head 保持 UNKNOWN、不释放冲突。但外来前缀和不同 scope 仍能绕过，详见下方 HIGH。 |
| **V-01** | **NOT_CLOSED** | 普通 `run_selection` 的 SkipTest、零匹配和导入失败分类得到改善；10 项 meta-test 在仅替换临时包存储的内存运行中全部通过。但 S30 的真实 SkipTest 子进程退出码为 0，现有路径仍报告 PASS；部分 selection 零匹配也能被其余通过项掩盖。 |
| **V-02** | **NOT_CLOSED** | 六个变异锚点在当前源码均唯一，替换后 `ast.parse()` 全部成功，守卫包含对应行为断言。但亲跑 `evaluate()`：代码完全未改变、真实守卫全绿，仍返回 `SEMANTIC_CAUGHT, failing=[]`。runner 分类不能支持“6/6 捕获”结论。 |

此外，保留现有测试断言、仅替换 Git 夹具传输后，C-01/C-02/C-03 标准案例及关系正例共 **17 项通过**。载入审计 base 的关系实现后，12 项中 **7 项失败**，未发现这些新增关系测试通过弱化 oracle 造绿。

### 新发现

**HIGH — C-03 的主体分类仍忽略 scope，并使用宽泛前缀。**  
[ca_adapter.py:276](/G:/jiagou/projectmind-c-audit-fixes/extensions/map_proposal/ca_adapter.py:276)

真实 CA 校验通过的以下两种 claim，均被 C 当成自身 base 的矛盾：

- `implementation.baseline_router.head`，scope=`global`
- `implementation.baseline.head`，scope=`component:router`

两包各有一个真实 architecture conflict。执行后，C 标记 pack 矛盾，原本被压制的候选重新保留。subject/scope 隔离仍未成立。

**HIGH — S30 仍把 SkipTest 当 PASS。**  
[acceptance_matrix.py:234](/G:/jiagou/projectmind-c-audit-fixes/tests/acceptance_matrix.py:234)

真实子进程输出 `Ran 1 test`、`OK (skipped=1)`，退出码为 0。将该真实结果输入现有 S30 路径后，得到 `result: PASS`。10 项 meta-tests 没有覆盖此路径。

**HIGH — mutation runner 将“守卫全绿”当作捕获。**  
[mutation_runner.py:181](/G:/jiagou/projectmind-c-audit-fixes/tests/mutation_runner.py:181)

`run_guards()` 返回的是 `all_green`，调用方却将它命名为 `caught` 并直接判为 `SEMANTIC_CAUGHT`。无变化替换加真实绿守卫已复现假捕获；后续分支也未区分环境失败与语义失败。

**MEDIUM — selection 缺失及 INPUT_HASH 绑定不完整。**  
[acceptance_matrix.py:154](/G:/jiagou/projectmind-c-audit-fixes/tests/acceptance_matrix.py:154)、[acceptance_matrix.py:268](/G:/jiagou/projectmind-c-audit-fixes/tests/acceptance_matrix.py:268)

- 一个 selection 通过、另一个零匹配，整体仍为 PASS。
- 加入零匹配 selection，`INPUT_HASH` 不变。
- S30 的 `INPUT_HASH` 是固定说明文字；加载失败则退化为 NOT_RUN，未区分 INVALID_TEST。

### 实际命令与回归限制

执行了以下要求命令：

```text
python -m unittest tests.test_acceptance_runner tests.test_w3_relations tests.test_w4_ca_trust -v
python tests/acceptance_matrix.py
python tests/mutation_runner.py
python -m unittest discover -s tests -p "test_*.py"
```

观察结果：

- 原始 meta/攻击测试受临时目录创建失败阻断。
- acceptance matrix：**8/30 PASS，22 FAIL，两轮稳定**；S30 实际绑定四个具名 A30 行为测试，结果为 FAIL。
- mutation runner：创建临时目录前失败，未完成六变异端到端运行。
- 完整回归：**147 tests，72 errors，退出码 1**。临时目录写入被禁止是已确认的失败原因，不能据此宣布代码回归通过。

这是当前沙箱的硬性写入限制，包括系统临时目录；内存复核没有被当作真实 Git 端到端验证。Project Model impact：**NONE**。

CODEX_VERDICT: FAIL