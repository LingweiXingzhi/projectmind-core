# PROJECTMIND_BD_C_DEMO — 体验指引

## 启动

```powershell
cd G:\jiagou\projectmind-map-proposal
python app.py
```

浏览器打开 <http://127.0.0.1:8765>。该分支 = B(Code Facts)+ D(handoff/continuity/worklog)+ CA(Context Authority)+ C(Map Proposal)全部集成。

## 能看什么

| 模块 | 入口(/ext/ 页面) | 体验点 |
|---|---|---|
| 主图 + Git 变化 | `/`(首页) | 节点职责/关系/evidence;选择 base 提交做 compare |
| B 代码事实 | `/ext/code_facts` | 输入完整 40 位 SHA → 该提交的 Python 声明(kind/限定名/行号);非法输入显式报错 |
| 交接包 D | `/ext/handoff` | expectedRevision 锁定版本,生成交接 Markdown / AI 上下文;支持工作备注(4000 字符内,导入自动截断摘要并保留全文) |
| 工作日志 D | `/ext/worklog` | 四分类记录;导入 MD/DOCX/PDF |
| 协同接续 D | `/ext/continuity` | 任务接续点(checklist/事件/状态机),导出→导入 roundtrip |
| Context Authority | `/ext/context_authority` | claims/状态/conflicts;POST validate_context |
| **C 地图建议** | `/ext/map_proposal` | 新增:粘贴请求 JSON(见下)→ 证据化 proposals/unresolved/no_proposal/limits |

## C 最小体验请求(调试视图或 POST /api/extensions/map_proposal)

```json
{
  "action": "suggest",
  "request": {
    "base_revision": "<40位基准SHA>",
    "target_revision": "<40位目标SHA>",
    "changed_paths": [{"path": "extensions/map_proposal/engine.py", "status": "added"}],
    "current_map": { ...data/project-map.json 的内容... }
  }
}
```

省略 `changed_paths` 时可传 `"comparisonMode"` 风格?——不支持;C 需显式 changed_paths(与 /api/compare 同口径,可先调
`/api/compare?base=...&target=...` 把 changes 转成 status: added/modified/removed/renamed 再粘贴)。
不给 `context_pack` 时 C 以 DEGRADED_NO_CONTEXT 运行(limits 会注明)。

## 期望行为

- 新增含 class 的 .py → 1 条 NODE_ADD(git_diff+code_fact+map_node 三重证据,confidence=low,human_required=true)
- 仅注释/格式/函数体改动 → no_proposal(显式理由,不编造)
- 跨模块新增 import → RELATION_ADD 候选;动态 import → unresolved NEEDS_HUMAN_REVIEW
- C **绝不**写地图:所有输出 status=PROPOSED,接受与否由人决定

## 已知限制

- B 在 Windows 下 2 个单测环境受限(字面 `*.py` 文件名/symlink 特权)——Linux 预期全绿
- 旧版 DOC 预览需本机 LibreOffice(textutil);缺省时优雅 400
- C 的 RELATION 解析只对地图证据域∪变更集内路径生效
