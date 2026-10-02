# 工作日志（D 独立扩展）

关联 Issue #25。状态：Draft，待团队审核。实现参考 Core main `7484d44ddeac3c054ca3ba68f92293d965bb615c`。本扩展不依赖交接扩展；记录可持续保存，无需先生成交接包。

## 运行与验收

检出 `feat/25-worklog`，在仓库根目录运行 `python3 app.py`，打开 http://127.0.0.1:8765/ext/worklog 。重启服务后主页面侧栏自动出现一级入口“工作日志”。二级分类：每日工作日志、关键决策、当前目标、待解决事项。

1. 新建记录，填写标题、日期、作者、来源和正文；保存后在列表打开，切换分类并搜索标题、正文或作者。
2. 编辑记录并保存，打开“修改历史”检查旧正文仍可查看。两位浏览器同时打开同一记录，第一位保存后第二位保存应得到冲突提示，第二位草稿保留；复制草稿后重新打开最新版再整理。
3. 在目标分类点击“导入文件”，选 MD、DOCX、DOC 或 PDF；导入后直接展示正文或 PDF 原文，可下载原件。文件大小上限 10 MB。导入默认来源为人工记录，AI 文件导入后应编辑来源为 AI；新建编辑器中的来源、日期、作者和分类也会用于导入。
4. 停止服务并重启，检查记录、原件和修改历史仍存在。
5. 点击“导出备份”，下载包含所有记录、历史及原件的 JSON。首版没有备份恢复页面；导出可保留数据供后续恢复工具使用。
6. 在窄屏检查分类、列表、阅读和编辑操作。实际浏览器 PDF 展示、下载及旧 DOC 转换需要在目标设备验收。

## 文档展示

- MD：UTF-8，标题、段落、列表、引用和代码块的安全正文视图；复杂 Markdown（表格、内联样式、链接）保留文字，不执行 HTML，也不加载外部图片。
- PDF：浏览器原生 PDF 原文预览，保留原文件；扫描件不做 OCR。浏览器不支持嵌入预览时可下载查看。
- DOCX：标准库读取 Word 正文段落，保留原件。正文视图不复现图片、分页和复杂版式；原件可在 Word 中打开。
- DOC：旧版 Word 使用 macOS 自带 `textutil`；其他平台需要已安装的 LibreOffice/soffice。未找到转换器、文件损坏、加密或转换超时会明确提示，失败不创建日志。转换调用只处理临时原件，不执行宏或调用模型。
- 正文视图最多展示 200,000 字符，超出时明确提示；原件保留完整内容。直接编辑的附加正文上限 15,000 字符。

## 保存、身份与历史

记录保存在当前目标仓库 Git 公共目录下 `projectmind-worklog/records.sqlite3`，不会被普通 Git 提交上传。普通仓库位于 `.git/projectmind-worklog/records.sqlite3`；同一仓库的 worktree 共用，不同仓库隔离。切换分支或重启不会丢记录；删除整个仓库或 `.git` 会丢失，应先导出备份。本机保存不是多人同步服务；作者字段由填写者声明，不是已验证的登录身份。

SQLite 事务保证记录和历史同时保存；`expectedVersion` 防止覆盖较新的编辑。每次保存记录完整版本，修改历史只读。原件不被编辑覆盖，编辑正文可用于附加解释。导入的文件名只是显示标签，文件存入数据库，不按文件名写磁盘路径。

`codeRevision` 表示保存时当前仓库提交，为关联线索，不证明日志正文已经由代码验证。人工记录标记 `contributor_record`，AI 来源标记 `ai_candidate`，两者均未独立核实。关键决策分类不自动成为团队正式决定，不写人工地图或正式 Project Model。首版不自动吸收 Git、聊天或交接记录，也不保证没有录入的工作已被记录。

## 独立 API（固定样例）

`GET /api/extensions/worklog` → `{entries: [...], categories: {...}, note: ...}`。

`GET ?action=get&id=<记录ID>` → `{entry: ...}`；`action=history` → `{history: [...]}`；`action=file&id=<原件ID>` → `{file: {id,name,kind,mime,base64,preview,note}}`；`action=backup` → `{format:"projectmind-worklog-backup-v1",exportedAt,entries,history,files}`。

`POST /api/extensions/worklog`，JSON 新建示例：

```json
{"action":"save","category":"daily","date":"2026-10-02","title":"接口验证","body":"验证步骤与实际结果","author":"Tester","origin":"human"}
```

响应 `{entry: {id,version,category,date,title,body,author,origin,status,createdAt,updatedAt,codeRevision,attachment}}`。修改时额外传 `id`、`expectedVersion`，旧版本得到 HTTP 409；输入格式错误 400，记录/原件缺失 404。日期为 ISO 日期，标题 1–200 字符，作者最多 100 字符，正文最多 15,000 字符。category 为 daily/decision/goal/issue；origin 为 human/ai。

导入遵守宿主单请求 65,536 字节上限：

1. POST `{action:"import_start",category,date,title,body:"",author,origin,filename:"log.md",size:<原件字节数>}` → `{uploadId,chunkBytes:24576}`。
2. 按顺序 POST `{action:"import_chunk",uploadId,offset:<从0开始的字节位置>,base64:<该分片>}` → `{received:<累计字节>}`；最多 32,768 个 Base64 字符。错序或重复分片 409，超过声明大小 400。
3. POST `{action:"import_finish",uploadId}` → `{entry: ...}`；完整校验/转换成功后事务保存原件、日志与历史。重复完成不会重复创建日志。
4. 出错时 POST `{action:"import_cancel",uploadId}` 清理分片；未完成会话 24 小时后清理，最多 8 个进行中的会话。

新增 API 仅属于本扩展，不改变 ABC 或现有 Handoff 字段。无第三方 Python 依赖，无模型调用。

## 验证与项目模型影响

运行 `python3 -m unittest discover -s tests -v`。新增测试覆盖持久化、历史、冲突、并发写入、仓库隔离、分片大小/顺序、UTF-8、DOCX、PDF 校验、DOC 转换适配器与真实 HTTP。DOC 转换适配器测试使用可控响应，不能当作目标 Mac 的真实 DOC 转换验收。

Project Model Impact：UPDATE（建议）。新增 D 项目工作记录与接续入口；建议地图维护者审核后登记 `extensions/worklog/extension.py`、`store.py`、`index.html` 的职责与映射，本 PR 不批准或修改正式模型。
