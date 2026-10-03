# B_CONTRACT_BOUNDARY_AUDIT — Track E: Contract Boundary Systematics (PR #22)

> EVALUATION ASSET。依据:B 交付 README(`collaboration/b/2026-10-01-wang-haining/README.md`,简称 CONTRACT)+ 本会话全部实测证据(E1)。
> 立场:对 AMBIGUOUS 项不替团队裁决,仅列证据与影响。

## 逐项边界表

| # | 维度 | 定界 | 证据(CONTRACT 引文/实测) | 下游影响 |
|---|---|---|---|---|
| 1 | 函数签名(参数表) | OUT | CONTRACT:「当前数据不含函数体、参数、调用关系或功能说明」 | C 不能凭 B 判断签名兼容性;需源码兜底 |
| 2 | 装饰器 | OUT(名称不计)但影响 kind 分类 | CONTRACT:line 非"装饰器行号";装饰器不产生 entries | C 若依赖 @route 等装饰器发现入口,必须另建通道 |
| 3 | 基类 | OUT | entries 只有 name/kind/line | 继承关系需 snapshot/diff 补 |
| 4 | 调用图/依赖 | OUT | CONTRACT:「不直接表示功能职责、运行时可达性」;adapters 记 deps={} NOT SUPPORTED | 依赖迁移类问题 C 不可用 B 回答 |
| 5 | 入口发现 | OUT | PROPOSED-B 无 entry-point 概念 | 路由/入口变化检测需 A 层或其他扩展 |
| 6 | 顶层常量/路由表 | OUT | 实测(Track 2/3):赋值从不产生 entries | ROUTES= 型事实不在 B 内 |
| 7 | 注解 | OUT(值不进 entries) | Track 1 U61-U105 注解族全过(注解不产生假条目) | typing 信息 C 拿不到 |
| 8 | docstring | OUT | Track A:docstring 内伪代码不产生 entries | — |
| 9 | 符号范围 | IN | def/async def/class 三类;lambda/赋值/type 别名均不计(实测) | C 的"符号"口径须与此对齐 |
| 10 | 限定名 | IN | 全链词法限定(Client.request.poll 实测正确) | C 可按词法聚合;但词法≠调用关系 |
| 11 | 行号语义 | IN | def/async def/class 关键字行,1 起;装饰器不计(实测 50 例) | C 做行级 diff 映射时以此为准 |
| 12 | 嵌套符号 | IN | 全链报告;async-in-method 等组合正确 | — |
| 13 | 重定义 | IN | 多重集语义,同名多条全报(U14/C 系列实测) | C 消费时须按多重集而非 set |
| 14 | 条件定义 | IN | if/elif/else/try 分支内定义全报(X01/X02 实测) | 词法≠运行时可达,C 需自知 |
| 15 | 动态定义(exec/create) | OUT | 语法层面不可见是契约前提 | C 对动态生成代码零覆盖,须声明 |
| 16 | 生成代码/非 .py | OUT | 非 .py → skipped+reason(实测) | skipped 通道即"不可见面"的显式清单 |
| 17 | 其他语言 | OUT | 「首版仅支持 .py Python 文件」 | C 的跨语言事实需求完全外置 |
| 18 | revision 语义 | IN | 完整小写 40/64 位 SHA、直接 commit;HEAD/短/大写/不存在均拒绝(47/47 实测) | C 必须先取 Snapshot 的完整 SHA 再调 B |
| 19 | paths 语义 | IN | 精确相对路径、去重、排序、[] =全不选、目录/通配/越界拒绝 | C 的批量用法受 2000 文件/1MiB/16MiB 上限约束 |
| 20 | skipped 语义 | IN | 存在但不可解析/不支持的进 skipped 且 reason 非空(实测) | C 必须消费 skipped,否则把"没看见"当"不存在" |
| 21 | worktree 污染 | IN(免疫) | SHA 读取;dirty/untracked 不影响(实测) | C 不可用 B 看未提交内容(设计使然) |
| 22 | 稳定性 | IN | 同 repo+SHA 重复调用一致(实测);输出含 revision 可自校验 | C 应核对 CodeFacts.revision==Snapshot.revision |

## AMBIGUOUS(需人工决策,已按影响排序)

1. **GET paths="" 空串语义**:实测=「未指定→全量扫描」。契约未明文;若 C 期望"空=全不选"会反转语义。影响:低(POST 是主路径)。**Human decision required: 建议契约补一句。**
2. **零声明合法文件**出现在 files[](entries=[])而 skipped[] 只收"存在但读不了"的文件:C 若用 `files` 判断"文件被分析过"需接受空 entries 形态。**建议 C 侧文档明确。**
3. **kind 枚举的权威来源**:B README 已枚举五种 kind(本会话按此断言全绿);但 MVP_INTERFACES 的 PROPOSED-B 文本未同步枚举。**Human decision required: 把 README 的枚举回写进正式接口文档。**

## 窄职责是否足以支撑 C?

**部分支撑,不是充分支撑。** 用 C 的 proposed input needs 对照:B 覆盖"什么符号在哪一行"(充分);C 的典型下游问题中,符号增删/移动类可由 B+git diff 回答(SUFFICIENT),而依赖变化/入口变化/职责迁移类问题 B alone=INSUFFICIENT、Git diff+B=PARTIAL。详见 B_TO_C_READINESS_REPORT.md 的 30 问分级。
