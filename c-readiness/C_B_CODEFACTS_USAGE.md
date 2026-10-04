# C_B_CODEFACTS_USAGE — C 如何消费 B(Code Facts)

## B 的真实输出(已独立核验,PR22 README@0c46747 + registry 契约)

```
collect_code_facts(repo, revision, paths=None) -> dict
顶层字段(仅 3 个):revision / files / skipped
entry: {path, language, entries:[{name, kind, line}]}
kind ∈ {function, async_function, class, method, async_method}
name = 词法点分限定名(Class.method、outer.inner)
line = def/async def/class 关键字所在 1-based 行,不是装饰器行
skipped = 存在但不可解析/不支持的文件 [{path, reason}],其余继续
不存在的指定路径 / 无效输入 → 整个请求失败
输入限制:≤2000 文件、单文件 1 MiB、单次 16 MiB、Git 超时 10s、POST 65,536B
revision = 直接指向 commit 的完整 40/64 位小写 hex(拒 HEAD/短 SHA/大写/tag)
```

## C 从 B 得到什么 / 不得到什么

| 得到(FACT) | 不得假设(B 不提供) |
|---|---|
| 某 revision 下某文件有哪些 def/class 声明及行号 | 依赖图 / 调用关系 / import 列表 |
| 类-方法结构(通过限定名) | 函数签名 / 参数 / 返回类型 |
| 哪些文件解析失败(skipped+原因) | entrypoints / 职责 / 架构归属 |
| 声明级规模信号(文件里有哪些名字) | 任何"意图"信息 |

**C 的 import/依赖信号必须来自 Git diff(diff 中的 +import 行),不是来自 B。** B 给"现在有什么声明",diff 给"这次变了什么",两者在 evidence 里分开标注 kind。

## 消费规则

1. **revision 一致性**:`code_facts.revision == request.target_revision`,不等即拒绝(建议照抄 suggest_map 的既有约束)。
2. **skipped 处理**:变化文件落在 skipped → 该文件的差异落 unresolved(NEEDS_HUMAN_REVIEW),不得基于文件名猜测职责生成 NODE_ADD。
3. **evidence 的 kind 用 `code_fact`**,并带 `revision + path + name + line`,可回放(拿同 revision 重新跑 B 应能复现)。
4. **行号语义**:若 C 的 rationale 提到"entryPoint 变了",必须用"关键字行"口径与地图 node.entryPoint 对照(地图引用的函数名可能对应装饰器下的真实 def 行,对照时允许 ±装饰器行数偏差,并在 uncertainty 注明)。
5. **PR31 演进注意**:registry 契约钉在 PR22 README;PR31(draft)把 code_facts 移入正式目录并新增 SHA-256 仓库测试。C 读取 B 时**以实际安装的扩展行为为准**,契约 claim 用于理解,不用于运行时断言(除 revision 一致性外)。

## 调用形态建议

Stage 2 起优先**进程内函数调用**(import PR31 合入后的 `extensions/code_facts`),HTTP POST 形态留给跨进程演示。理由:2000 文件/16MiB 限制在进程内同样成立,但避免了 64KB 请求体与序列化开销;错误处理(不存在路径→失败)两边一致。

## 一个最小调用样例(Stage 2 验收用)

```python
facts = collect_code_facts(repo_root, target_revision, changed_paths)
assert facts["revision"] == target_revision
skipped = {s["path"] for s in facts["skipped"]}
for f in facts["files"]:
    # f["entries"]: C 的 candidate evidence model 的 FACT 层输入
    ...
```
