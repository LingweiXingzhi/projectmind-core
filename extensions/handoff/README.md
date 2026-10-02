# D 首版：交接包（待团队审核）

模块：D / Handoff；关联 Issue #23。

实现基准：core/main `7484d44ddeac3c054ca3ba68f92293d965bb615c`。状态：Draft，待团队审核和共同基线确认。

## 功能目标

把当前项目的代码版本、功能证据、变化与未确认项整理成一个文件，让别人不用翻聊天记录就能继续核查。

## Mac 运行

检出本 PR 分支后，在仓库根目录执行 `python3 app.py`，打开 http://127.0.0.1:8765/ext/handoff 。

1. 填入真实仓库来源。目录名不能代替来源地址。
2. 可选填写另一个完整提交 SHA，生成真实比较；留空时明确说明没有比较，不能说没有变化。
3. 可选粘贴 `/api/explain` 的完整成功响应组成的 JSON 列表；无 AI 结果时留空。
4. 点击生成，预览后下载 JSON 或 Markdown。

页面会核对刚才看到的代码 SHA。服务端代码版本变化时拒绝旧请求，刷新版本后须重新生成。地图目前没有正式核查版本，始终明确写 UNKNOWN。

## 验证

`python3 -m unittest discover -s tests -v`

首版验证覆盖：可选输入缺失、错误比较/AI 版本、虚构 AI 引用、缺失证据、本机路径提醒、输入不变性、真实宿主加载及真实 HTTP 页面/生成/400 错误。合成样例中的 AI 结果不是在线调用证明。

验证结果：20/20 项测试通过，页面脚本语法检查通过。HTTP 回归使用从固定基准源码恢复的本地 Git 验证快照，其 SHA 不代表远端基准提交。

尚待：真实浏览器下载操作、非作者盲接手、A 的地图来源补丁对接、真实 AI 输出接入。当前不调用模型、不写正式地图。

## 给审核者的盲接手任务

只读导出的交接包，回答：仓库从哪取得？代码对应哪个完整提交？地图是否核查？哪个节点待复核？证据在哪？下一步先查什么？记录实际通过/失败，不靠作者口头补充。

## 数据入口

POST `/api/extensions/handoff`：

```json
{"expectedRevision":"完整当前 SHA","sourceLocator":{"kind":"git_remote","value":"显式仓库地址"},"baseRevision":"可选完整基准 SHA","aiCandidates":[]}
```

省略可选字段即可；响应为 `{handoff, markdown}`。`build_handoff(snapshot, source_locator, comparison=None, ai_candidates=None)` 可独立使用；AI 候选原样复制并检查对应比较、版本和证据，不生成新结论。页面输出通过文本展示，不执行输入中的 HTML。

Project Model Impact：UPDATE（建议）。新增可运行交接扩展，建议团队审核后登记职责与代码映射；本 PR 不直接修改正式 Project Model 或人工地图。
