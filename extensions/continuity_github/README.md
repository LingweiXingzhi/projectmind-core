# 协同交接（GitHub 实验版）

Issue #46；独立分支 `feat/46-continuity-github`，继承 D 体验改进的远端 `86d1e2d8f2d27187e2e707eaa99f41643aaf1601`（tree `1161b4dc5eb4b3e1b6f3bf92830d1d5d6389735c`）。不改原 handoff、worklog、continuity 或公共宿主。

## 用户路径

1. Fetch origin，切换本分支，核查/保留未提交改动；关闭旧服务，运行 `python3 app.py --port 8765`。
2. 打开 http://127.0.0.1:8765/ext/continuity_github 。团队拓展入口名称为“协同交接（GitHub 实验版）”；原入口仍在。
3. 顶部“实验工作日志”打开同一接口内的独立日志编辑器。可新建、导入 MD/DOCX/DOC/PDF、编辑和读历史；也可“带入原日志 · 副本”。复制显式进行，原数据库只读，复制附件有新 ID；编辑副本不会改变原记录。
4. 写日志时在关联栏每行粘贴一个 Issue、PR、完整提交或固定版本源码 URL，后面可写 ` | 为什么关联`。也可点击“关联当前代码提交”，免抄完整 SHA；无法对应 GitHub 来源时明确提示。这不是 GitHub 登录或同步，不保存令牌。
5. 在日志阅读页点击“选入新的交接”，回到准备端并勾选该日志。填任务、停止位置、下一步和清单，保存。日志的关联随固定版本快照带入，后来编辑日志不改旧交接。
6. 交接也可直接关联工作项。阅读页显示任务及日志的引用；“核查本机提交 / 查看代码”先检查本机 remote 是否对应链接仓库，再读完整 SHA 的提交/文件。不对应时不读取，不把碰巧相同的 SHA 当来源证明。
7. 顶部“工作项索引”按同一链接归拢实验日志和交接；点击记录打开对应材料。Issue/PR 只显示链接与参与者说明，不显示猜测的远端状态。
8. 原接手、问题、进展、结束本次接手、任务完成、清单、历史及文件导入导出沿用。接续 JSON、Markdown、AI 接手文本保留链接；在实验版重导入，链接仍未核实。原 UI 不支持新关联字段，使用原工具导入后再导出会丢失这些可选字段。

源码链接样式：`https://github.com/owner/repo/blob/完整40位SHA/path.py#L1-L20`。提交链接为 `/commit/完整40位SHA`。不接受移动分支、短 SHA、凭据、查询参数、其它站点、越界路径或任意 URL；只作为定位文本，不自动执行。

## 数据和接口

Git 公共目录下两个全新目录：

- `projectmind-worklog-github/records.sqlite3`：实验日志、历史、原件。
- `projectmind-continuity-github/records.sqlite3`：实验交接、历史、导入会话。

不会自动迁移、覆盖或同步原库。原日志副本的 `sourceRecord` 保存原 ID/版本及 copied_unverified；保留来源关系不认证记录。Git 普通提交不包含业务数据库；同仓库 worktree 共用数据，另一个 clone 不带入旧数据。若要把业务数据交给另一人，用完整接续 JSON；实验日志导出备份沿用原格式且包含可选 references，首版没有备份恢复页面。

原 continuity API 的操作名及 shape 在本扩展独立路径 `/api/extensions/continuity_github` 提供；新字段 `references` 最多 30 项，每项 `{url,label?,reason?}`。服务端重新规范化，添加稳定链接 ID、种类、仓库、固定 SHA/路径，状态始终 `user_link_unverified`，不信任导入的“verified”。实验日志通过同一 API 的 `log_` 前缀操作：list/get/history/file/backup/save/import_start/import_chunk/import_finish/import_cancel。

新增操作：

- GET `log_page`：嵌入的实验日志 UI；不是第二个拓展入口。
- GET `original_logs`：最多 1000 条原日志，只读；POST `copy_original_log` `{id,references?}`：完整副本与附件写入实验库。
- GET `reference_index`：`{items:[{reference,logs,tasks}],note}`，只汇总实验记录。
- POST `verify_references` `{references}`：链接规范化及本机核查，结果 `link_only/repository_unconfirmed/commit_present/code_present/preview_unavailable/missing`；原远端链接 status 不升级。

本机源码预览最多 12,000 字节；二进制及超过 1 MiB 文件不预览，始终使用固定 Git 版本，不执行代码。仍需要支持 `--no-lazy-fetch` 的 Git。沿用原模块冲突处理、请求与导入上限、附件格式限制；任务说明中的命令不执行；地图 UNKNOWN、AI 候选、日志及反馈未独立核实继续保留。

实验目录内的 continuity store/inspection/UI 是从固定基线继承的隔离版本；新模型包装复用原校验和行为，日志 Store 复用原实现。升级原功能时先比较这份实验副本，不直接覆盖原代码。明确隔离是本次用户要求，不是第二套正式架构批准。

## 验证和待验收

```bash
python3 -m unittest discover -s tests -v
node tests/check_continuity_ui.js
node tests/check_github_experiment_ui.js
```

本轮 Python 59 项通过（原 53 项 + 6 项实验行为），覆盖引用校验、真实 HTTP 发现/核查、独立数据库字节不变、日志与附件导入/快照、导出/重导入、版本冲突、原日志显式复制。Node 执行实际函数检查关联输入、去重、安全文本、草稿标记及预览逻辑；原 UI 逻辑检查通过，页面脚本语法/编译检查通过。不是浏览器视觉验收；执行环境没有 Chromium。目标 Mac 嵌入日志编辑器、选入交接、PDF/DOC 和窄屏视觉需要实际走一次。

Project Model Impact = UPDATE（建议）：新增实验扩展和关联能力，职责与路径需团队登记；不更新正式地图。GitHub OAuth、自动获取 Issue/PR 状态、远端写入、多人同步不在首版；本版提供可用的关联与本机代码核查。
