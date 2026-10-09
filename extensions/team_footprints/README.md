# 团队足迹

Issue #47；独立分支 `feat/47-team-footprints`，从远端 D `86d1e2d8f2d27187e2e707eaa99f41643aaf1601`（tree `1161b4dc5eb4b3e1b6f3bf92830d1d5d6389735c`）建立。不依赖实验版分支，不改原产品或公共路由。

## 运行与用户体验

Fetch origin，切到本分支，保留未提交改动，关闭旧服务后运行 `python3 app.py --port 8765`。打开 http://127.0.0.1:8765/ext/team_footprints 。团队拓展自动发现“团队足迹”。

选择整个团队或某位参与者、年份、时区；默认北京时间、AI 不计入。外层日历显示全年活动密度，点击某天看日志/进展/问题/结束记录与说明和依据；“趋势”显示月度折线，零数据也正常呈现。任务事件可打开“工作接力”，查看这份本机任务由谁留下了哪些记录；来源页入口供继续查阅。足迹独立分支若读取到实验版记录但未安装其扩展，提示切换分支，不给出失效的来源页按钮。图表按钮支持键盘访问，响应式小屏保留可横向滚动的日历；名字/说明用纯文本展示。

没有记录时真实空白，不生成演示贡献。可以先到原工作日志保存一条记录，再刷新。切换 Git 分支不会清空同一仓库记录；如果使用新 clone，原 `.git` 数据不会自动带过来。

## 什么算活动

| 类别 | 计数条件 |
| --- | --- |
| 工作记录 | 有内容变化的日志版本；无变化保存不计；原日志副本的初次带入不计 |
| 交出资料 | 本机新建的接续任务有停止位置/下一步；导入任务不冒充新交出 |
| 工作进展 | note 有说明或依据；单纯点接手不计 |
| 问题记录 | question/block 有实际说明 |
| 问题处理 | 本机事件顺序中曾 block，之后 claim/resume 有处理说明 |
| 本次结束 | finish_session 有结果、停止位置与下一步 |
| 任务完成记录 | complete 有说明和依据；仍是参与者记录，不认证完成 |

同一日期、来源、记录、类别、参与者只计一项，重复有意义版本可在当天详情看见但不会重复加深颜色。跨天实际编辑可以再次计数。颜色固定阈值：0/1/2–3/4–6/7+，表示活动密度，不加权打分、不排名、不比较劳动价值。

日历用服务保存/事件的带时区时间转换到所选 IANA 时区；手填日志 date 不用作活动日期。无时区/错误时间明确排除并显示数量。AI 默认排除，勾选后为候选来源；同名人工与 AI 分开。导入 importedHistory 不计本机新活动，不回写、不自动验证；远端缺失记录不推断成员没有工作。

## 只读范围与云端准备

SQLite 使用 `mode=ro`，不存在的库不会创建。读取当前目标仓库 Git 公共目录下：原 `projectmind-worklog` / `projectmind-continuity`；如果已运行 GitHub 实验版，也读取 `projectmind-worklog-github` / `projectmind-continuity-github`。不会修改它们，不跟随其他 clone 的数据。每个来源最多 20,000 行、约 32 Mi 字符；达到限制显示 partial，不能称全量统计。可用但空库、缺失库和不可读库分开处理。

当前“团队”是本机可用资料的汇总，不是已部署的云端团队空间。成员 `local:<hash>` 由规范化名称和来源类型产生，稳定但只是自行声明：同名不同人可能合并、同人改名可能拆开，不用于权限或排名。未来由 A 的账户/团队层提供稳定 memberId 与名称映射，不能把本地名字 hash 当已认证用户。

`collect_activity(repo, timezone)` 与 `summarize(dataset, year, member_id, include_ai, details)` 是可复用纯统计边界，页面独立；未来云端 provider 可产生同形 events/coverage 供 summarize 消费，不需要复制统计规则。事件包含 id、原记录 ID、来源、带时区时间、成员/可信状态；旧事件 ID 是含来源及原记录的内容指纹，不是服务器签发身份。未来新事件应由云端分配不可变 ID，迁移旧记录需保持来源和去重关系，不在本次修改旧 schema。

## 主页面接入接口（供 A 使用）

GET `/api/extensions/team_footprints?year=2026&timezone=Asia/Shanghai&memberId=&includeAi=false`

返回 schemaVersion=1、scope=local_available_records、成员、365/366 天的 count/eventCount/metrics、12 个 trend 点、覆盖来源、partial、忽略数及计数 policy。summary 不携带完整事件正文，适合主页日历/卡片；主页无需解析数据库。

GET `action=day&date=2026-10-06`（同 year/时区/成员条件）返回当天最近 200 条事件、totalEvents 和 truncated；GET `action=relay&recordId=...&source=continuity` 返回该本机任务接力（最多 300 条，带 truncated）。POST 返回 405。无效日期/年份/时区受控 400；不存在的成员 404；数据库暂时不可读 503。

A 可以先在主页放总项数/活跃天数和热力日历，再用 day 接口展开；本 PR 不编辑 A 的主页面。两个新分支分别只新增各自扩展和测试，A 接入二者时不会互相覆盖产品文件。

## 依赖：IANA 时区数据库（部署数据）

本扩展按所选 IANA 时区换算事件时间，默认 `Asia/Shanghai`。CPython 的 `zoneinfo` 读取**操作系统**的时区数据库；Windows 不自带，因此缺少 `tzdata` 包时任何 IANA 键都会失败：

```powershell
python -m pip install tzdata
# 验证：
python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Shanghai'))"
```

仓库根 `requirements.txt` 已声明该依赖（`tzdata; sys_platform == "win32"`，上游说明见 <https://docs.python.org/3/library/zoneinfo.html#data-sources>）。

缺少时区数据库与"用户填了非法时区"是两回事，返回也不同：

| 情况 | 响应 |
| --- | --- |
| 本机没有任何 IANA 数据（连 `UTC` 都无法解析） | **503**，文案说明这是部署缺口并给出安装步骤 |
| 本机有时区数据、但所选键非法 | 400，文案为"请选择有效的 IANA 时区" |

## 验证与限制

```bash
python3 -m unittest discover -s tests -v
node tests/check_team_footprints_ui.js
node tests/check_continuity_ui.js
```

测试用解释器同样需要 `tzdata`（本机两个内置解释器都缺）；缺失时相关用例会以环境原因失败，属部署缺口而非产品缺陷。

本轮 Python 58 项通过（原 53 项 + 5 项），覆盖真实库的只读字节不变、无记录不建库、重复保存/同日上限、时区跨日、手填日期隔离、导入/AI 排除、问题处理、本次结束、闰年、个人过滤、仓库隔离及真实 HTTP/405。Node 执行实际日历/图表函数，检查色阶、366 天、日标签、纯文本名字、12 个趋势点和零值无 NaN；不是浏览器视觉验收。脚本语法与 Python 编译通过。本机无 Chromium，完整视觉、小屏和主页接入尚待实际验收。

Project Model Impact = UPDATE（建议）：新增只读活动视图和统计入口，提交给团队登记；未修改正式地图。原图仍 UNKNOWN，AI 与日志/参与者记录状态未升级。
