# Python 符号解析：B 交付

本轮任务来源：2026-10-05 编写的 PROJECTMIND_REPO_EXPLORER_4_PERSON_PLAN.md。新模块从指定基线 1cc2fd8cb890aa94e48bb9957d846411dc2c9d4d 开发。它描述技术定义，不推断已确认的业务职责或运行调用关系。

## 导入与调用

Python 3.10+，仅使用标准库。repo_index 使用 namespace package；此交付不创建 __init__.py，也不依赖 A/C/D 的新增文件。在包含 repo_index 的 checkout 根目录运行：

```python
from repo_index.symbols import parse_symbols

source = (
    'class Service:\n'
    '    def run(self):\n'
    '        "执行处理。"\n'
    '        return 1\n'
)
result = parse_symbols("pkg/service.py", source)
assert result["status"] == "ok"
assert result["symbols"][1] == {
    "name": "run",
    "qualified_name": "Service.run",
    "kind": "method",
    "start_line": 2,
    "end_line": 4,
    "docstring": "执行处理。",
}
```

公共接口：

```python
parse_symbols(path: str, source: str) -> dict
```

输入均为字符串。path 是调用方提供的仓库内相对文件路径，source 是调用方已经解码的源码文本；这个模块不读取 path。调用方负责路径安全、解码、大小限制，以及所选仓库/提交的一致性。不符合字符串输入前提时抛出 TypeError，不把调用方类型错误冒充 Python 语法错误。

## 严格输出

```json
{
  "path": "pkg/service.py",
  "language": "python",
  "status": "ok",
  "symbols": [
    {
      "name": "Service",
      "qualified_name": "Service",
      "kind": "class",
      "start_line": 1,
      "end_line": 4,
      "docstring": null
    },
    {
      "name": "run",
      "qualified_name": "Service.run",
      "kind": "method",
      "start_line": 2,
      "end_line": 4,
      "docstring": "执行处理。"
    }
  ],
  "warnings": []
}
```

上面是调用示例的完整结果。顶层字段固定为 path、language、status、symbols、warnings；符号字段固定为 name、qualified_name、kind、start_line、end_line、docstring，不添加 Git/HTTP 上下文字段。

- .py、.pyi 可解析，扩展名大小写归一后判断；成功 status=ok。
- 其他扩展名 status=unsupported、symbols=[]，warnings 说明不支持。language 始终为 python，表示此解析器的语言，不声称其他类型文件是 Python。
- 有效空文件或没有定义的有效 Python 源码返回 ok、symbols=[]，区别于失败或不支持。
- SyntaxError 返回 parse_error、symbols=[]；warnings 包含解析器报告的行号和简短原因，不包含整份源码。NUL 错误的首个位置从输入字符串准确定位，支持 LF、CRLF 和 CR 换行；解析器没有提供可靠位置的其他文本/资源错误使用 unknown，不虚构行号。
- warnings 始终是字符串数组。提示文本用于人阅读，调用者应按 status 判断，避免依赖具体措辞。

## 词法作用域和类型

| 定义 | kind |
|---|---|
| class | class |
| 普通函数 | function |
| async 函数 | async_function |
| 最近定义作用域为 class 的普通函数 | method |
| 最近定义作用域为 class 的 async 函数 | async_method |

限定名按词法定义作用域拼接。示例：Outer.run.helper 是方法内嵌套的 function；Outer.run.Inner.work 是方法内嵌套类的 method。if/try/for/with 等控制语句不创建新的定义作用域，因此 class 的条件块中定义的函数仍为 method。

即使函数所在条件不会运行，声明仍可出现在结果中。这是 AST 的静态定义，不证明运行可达性；不计算动态属性赋值、继承后运行归属、装饰器效果、调用链或业务职责。lambda 不输出为有名定义。

同名定义全部保留，不使用名称作为唯一键。结果按 (start_line, qualified_name) 稳定排序；调用方可用路径、限定名和行号区分。

## 源码范围与文档字符串

- 行号从 1 开始，end_line 包含在范围内。
- start_line 来自定义节点 lineno，从 def/async def/class 开始，不把前置装饰器计入。
- end_line 来自对应 AST end_lineno；多行签名和多行定义体覆盖到真实末行。
- 无 docstring 时为 null；存在但清理后为空的 docstring 保留空字符串。
- 使用 ast.get_docstring(clean=True) 清理缩进；普通字符串、注释或稍后赋值给 __doc__ 不视为定义 docstring。
- 清理后最多保留 2,000 个 Python 字符；超过时截断并在 warnings 指出限定名、定义行和截断限制。正好 2,000 字符不截断。

## 测试

在该 checkout 根目录使用项目所要求的 Python 版本：

```text
python -B -m unittest discover -s tests -p test_repo_index_symbols.py -v
```

测试源码和预期名称、类型、限定名、起止行号独立指定，不执行目标源码，也不从解析结果生成期望。覆盖普通/异步定义，条件块方法，方法内嵌套函数/类，装饰器，多行定义，同名声明，中文和长 docstring，空文件、语法错误、不支持类型以及伪定义/源码不执行。

本轮执行命令、环境、实际结果和完整提交 SHA 放在本地交付报告；A 集成后应在自己的确切 HEAD 再执行此测试。此测试不启动应用或 HTTP 服务，不访问正式仓库的 Worklog/Continuity 数据库。

## A 接入

1. 核对本交付基于指定 BASE_COMMIT，差异只包含 B 的三个文件。
2. 按交付报告中的两个完整 SHA 顺序接入自己的开发分支。
3. 从 A 的 Git 读取/解码层取得同一仓库、同一完整 SHA 的源码字符串，调用 parse_symbols(path, source)。
4. A 在 symbols HTTP 响应包装 projectId/revision/parser="python_ast_v1"；B 不生成这些字段，不替代现有 CodeFacts 协议。
5. A 用符号的 start_line/end_line 打开同版本源码范围，并展示 status/warnings；失败/未支持不包装为成功空结果。

此交付没有改动 app.py、web、repo_index/__init__.py、公共类型文件、历史 Code Facts/C/CA/D 模块或正式 Project Model；完整应用和页面接通由 A 验证。

## 限制与 Project Model 影响

解析语法由实际运行的 Python 版本决定。新版本 Python 语法需要相应解释器；没有跨全部 Python 版本验证。输入大小限制属于 A，本模块不复制 Git 索引、网络、LLM 或资源治理层。

Project Model Impact = UPDATE：新增实现入口 repo_index.symbols.parse_symbols 和技术解析能力。提出记录其职责“已解码 Python 文本的词法定义/源码范围/docstring”，注明它不读取仓库、不执行项目代码、不裁定业务架构。依据为本模块、测试及本次任务书；正式 Project Model 未修改，集成/批准状态由团队确认。
