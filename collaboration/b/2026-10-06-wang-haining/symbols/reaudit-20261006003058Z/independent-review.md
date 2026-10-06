# B 符号解析独立复审记录

## 审查对象与范围

结论：PASS，未发现需要修复的具体问题。

- Checkout：<B_CODE_CHECKOUT>
- Branch：feat/repo-explorer-symbols-v1
- HEAD：c3e08a9f41248d32f1c22383204aa99f44a08056
- BASE_COMMIT：1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d
- 产品审查范围：repo_index/symbols.py、tests/test_repo_index_symbols.py、docs/repo-explorer/SYMBOLS.md。
- 完整阅读 B任务.txt、PROJECTMIND_REPO_EXPLORER_4_PERSON_PLAN.md、checkout 的 AGENTS.md 和 docs/standards/AGENT_STANDARD.md；同时读取本轮共同约定要求的 README 和协作规范。

这是已完成审查的补存记录。以下输出从本次实际工具返回结果记录，未作为当时通过重定向保存的原始 stdout 文件声称。本次补存没有增加或重跑测试。

## 已检查的关键风险

- 输入输出字段、状态、五种 kind、.py/.pyi 扩展名判断。
- 最近定义作用域、嵌套函数/类、控制块不增加作用域，退出定义后的作用域恢复。
- AST 起止行、装饰器排除、重名保留、按 start_line/qualified_name 稳定排序。
- docstring 清理后按字符截至 2,000；恰好 2,000 不截断，超过时提供 warning。
- 解析失败清空符号，warnings 给出简短原因及可获得的行号，NUL 按 LF/CRLF/CR 定位。
- 模块只解析输入字符串，没有文件/Git 读取或执行目标源码。
- 所属测试使用明确源码和独立预期，未由被测解析器生成期望。
- 文档示例、字段、作用域、源码范围、限制和 A 接入步骤与实现相符。
- Git 差异严格限于 B 三个文件；git diff --check 无输出且退出码 0。

## 实际执行的独立 probe 命令与源码

执行时的工作目录：

~~~text
<B_CODE_CHECKOUT>
~~~

执行时的 shell 命令使用下列 here-doc 形式：

~~~text
<BUNDLED_PYTHON> -B - <<'PY'
（此处的实际 stdin 源码全文已原样补存到同目录 independent-probes.py）
PY
~~~

上述括号中的文字是记录中的说明，不是当时传入 Python 的代码。实际 stdin 内容就是 independent-probes.py 全文；该文件在审查完成后才创建，没有执行这个新保存的文件。

七个固定 probe 的预期名称、kind、限定名和行号由审查者直接指定，没有调用 ast 或 parse_symbols 生成期望。probe 仅 import 被审查的解析模块，将目标源码作为字符串传入；目标源码没有执行。

## 本次实际工具输出的记录

运行环境 Python 3.12.14；命令退出码 0：

~~~text
Python: 3.12.14
while/with/else scope restored: PASS
match/case nearest class: PASS
empty docstring remains empty: PASS
docstring limit after cleanup: PASS
indentation error line: PASS; Parse error at line 3: unindent does not match any outer indentation level
mixed newline NUL location: PASS; Parse error at line 4: source code string cannot contain null bytes
surrogate source guarded: PASS; Parse error at line unknown: 'utf-8' codec can't encode character '\ud800' in position 16: surrogates not allowed
~~~

7 个 probe 全部通过。其中 surrogate 错误没有可靠行号，受控返回 parse_error 和 unknown，与文档限制一致。

## Git 核查记录

执行过：

~~~text
git status --short
git rev-parse HEAD
git diff --stat 1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d..HEAD
git diff --check 1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d..HEAD
git log --format='%H %s' 1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d..HEAD
git branch --show-current
git merge-base 1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d HEAD
~~~

差异统计：

~~~text
 docs/repo-explorer/SYMBOLS.md    | 126 +++++++++
 repo_index/symbols.py            |  82 ++++++
 tests/test_repo_index_symbols.py | 558 +++++++++++++++++++++++++++++++++++++++
 3 files changed, 766 insertions(+)
~~~

提交记录：

~~~text
c3e08a9f41248d32f1c22383204aa99f44a08056 fix(symbols): report NUL lines and complete contract checks
6e81e715cfd46b840cc9b3f01b007778a1637f21 feat(symbols): add source-only Python definition parser
~~~

审查结束时再次执行 git status --short 和 git rev-parse HEAD：工作区无状态条目，HEAD 仍为 c3e08a9f41248d32f1c22383204aa99f44a08056。没有修改产品文件、Git、main 或其他分支。

## 验证限度与 Project Model

独立审查没有运行历史全套测试、应用服务或 UI，也没有复跑 root 已运行的所属测试。本结论限于 B 解析模块及以上 7 个固定边界样例；没有验证 Python 3.10/3.11 等其他解释器版本。没有读取凭据、联网、push 或提交。

Project Model Impact = NONE：只读代码审查和审查证据补存。
