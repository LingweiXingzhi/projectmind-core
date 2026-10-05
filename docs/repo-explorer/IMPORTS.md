# Python 静态导入解析模块 (Role C)

## 模块入口
`repo_index.imports.parse_imports(path: str, source: str) -> dict`

## 契约字段说明
- `path`: 归一化后的文件相对路径（使用 `/` 分隔）。
- `language`: 当前仅支持 `python`。
- `status`: `ok` | `parse_error` | `unsupported`。
- `imports`: 导入条目列表，每项包含：
  - `kind`: `"import"` 或 `"from"`
  - `module`: 导入模块名称（相对导入无模块时为 `""`）
  - `level`: 相对层级整数（绝对导入为 0）
  - `name`: 导入项名称（`import` 语句为 `null`，通配符为 `"*"`）
  - `alias`: 别名字符串，无别名时为 `null`
  - `line`: 声明起始行号
  - `end_line`: 声明结束行号
- `warnings`: 解析警告列表（如语法错误原因、未展开通配符提示等）。

## 边界与语义约定
1. **纯 AST 静态解析**：仅记录源码中出现的 import 语法结构，不执行源码，不保证运行时模块实际存在或必然被执行。
2. **通配符导入**：`from pkg import *` 保持 `name="*"`，不展开子项。
3. **依赖解析归属**：模块与文件真实对应关系、反向调用关系由 A 模块在仓库范围内统一处理。
