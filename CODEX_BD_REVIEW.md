# CODEX_BD_REVIEW — 第一轮独立审核记录(Codex,READ ONLY)

- 审核对象:`integration/bd-v1` @ `405d6635b0c4ff004b5093e16231da84e7b481b4`
- 执行方式:`codex exec -s read-only`(codex-cli 0.160.0,177,384 tokens)
- 原始输出:`G:\jiagou\overnight-logs\codex-bd-round1-raw.log`
- **CODEX_VERDICT: FAIL**

## Codex 7 问回答(摘要,详见原始日志)

1. B+D 真实集成:**是**(merge 拓扑、ExtensionHost 实载、真实 B 调用均核验)。
2. 隐藏 merge/ownership 错误:未发现(reflog/ls-remote/内容比对)。
3. 测试充分性:有真实测试但不足以支持全面通过(只读环境未能复跑写盘测试;发现 harness 弱检查)。
4. security blocker:未发现已证实 BLOCKER。
5. 不该改的文件:未发现(34 文件全部为新增,Core 公共文件零触碰)。
6. 数据丢失:未发现覆盖;但带备注交接包导入失败(确定缺陷)。
7. C base 适配性:可作为已核验代码起点,但应先修复交接导入缺陷并补回归。

## Findings(原样)与 ZCode 逐条核验结论

| # | 级别 | Finding(摘要) | ZCode 独立核验 | 处置 |
|---|---|---|---|---|
| 1 | **HIGH**(Spec) | 带备注导出包的正常交接路径失败:`work_notes={}` 或实际备注生成的 Handoff/Continuity 包导入 400;根因 handoff.py:86 给 workNotes 加 `status`,continuity 导入路径拒绝该键 | **已复现确认**:带备注导入 400"工作备注只支持 completed、pending、blockers、nextSteps";无备注 OK | **已修复**(见下 FIX-1) |
| 2 | MEDIUM(Standards) | 同根因:合法工作备注不满足导入兼容承诺(continuity README 备注保留承诺) | 同上 | FIX-1 |
| 3 | MEDIUM(Standards) | D 证据读取未禁止惰性取件(inspection.py git() 无 `--no-lazy-fetch`),partial clone 下 `git show` 可能联网写对象库 | 源码核实属实 | **已修复**(FIX-2) |
| 4 | MEDIUM(Standards) | 自动来源地址改变协议:ssh:// 远程被改写为 https://(Codex 内存复现) | 源码核实属实,且发现**第三处同类位点**(extension.py config 动作,Codex 未列出) | **已修复**(FIX-3,三处全改) |
| 5 | LOW(Standards) | worklog `category: []` → TypeError → 500,契约应为 400 | **已复现确认**(实测 500"扩展运行失败") | **已修复**(FIX-4) |
| 6 | MEDIUM(Spec) | harness 弱检查:S3.4 bad-date/null-title 因非法 category 提前失败;S3.16 用错字段未达 base64 解码;S15.1 键唯一性恒真 | 核实属实(三处均为验证脚本缺陷,非产品缺陷) | **已修复**(FIX-5) |

## 修复内容(全部在 integration/bd-v1,不改 D 原分支)

- **FIX-1(HIGH)**:`extensions/continuity/model.py` validate_handoff — 导入时把 workNotes 过滤为 4 个备注键(丢弃导出方加盖的 `status` 溯源键)再进 build_handoff;导出格式不变。效果:带备注交接包导出→导入闭环恢复,备注内容保留。
- **FIX-2(MEDIUM)**:`extensions/continuity/inspection.py` git() — 加 `GIT_NO_LAZY_FETCH=1` 环境隔离 + `--no-lazy-fetch` + stdin=DEVNULL;旧版 git 返回 129 时给出升级提示(与 B 的 facts.py 同款防护)。
- **FIX-3(MEDIUM)**:`extensions/continuity/inspection.py` remotes() 保留原始 URL(`url` 键)与规范化 address 并存;extension.py config 与 inspection.py capture 两处 sourceLocator 构造优先用原始 URL,不再重建协议(canonical address 的相等性比较用途不变,inspection.py:156 逻辑未动)。
- **FIX-4(LOW)**:`extensions/worklog/store.py` metadata() — category 先做 isinstance(str) 检查,非字符串 → 400。
- **FIX-5(MEDIUM,harness)**:S3.4 改用合法 category(直达目标校验);S3.16 改为有效 uploadId + 正确字段 `base64`/`offset` 直达 base64 解码器,新增 S3.17 未知会话;S15.1 改为 listing ids 与扩展目录的一致性检查(去恒真);新增 S21.1–S21.4 四项修复回归检查。

## 回归证据(修复后)

- 新增 `tests/test_bd_integration.py`(6 项):备注 roundtrip ×2、远程 scheme 保留 ×2、no-lazy-fetch 钉住 ×1、category 400 ×1。
- `python -m unittest discover -s tests`:**83 项,81 PASS,2 ERROR(仅原 2 项 Windows 环境限制,失败集 md5 与修复前逐字节一致)**。
- `verification/verify_bd.py`:**63/63 PASS × 3 轮**(S21.1 HIGH 修复直测通过)。
- 三轮 unittest 失败集 md5:`3a1eda05aaeb2b4a2d1eb73cbd3da698`(×3,与修复前相同)。

---

## 第三轮(gate 最终轮)状态:受阻于 Codex 用量额度

- 时间:2026-10-04 02:53(+0800);`codex exec` 启动后返回 usage limit 错误(05:09 AM 重置),未产生任何审核结论。
- 26,963 tokens 消耗后中止;raw 日志:`G:\jiagou\overnight-logs\codex-bd-round3-raw.log`(未入库,避免与真实审核混淆)。
- 请求文件已就绪并推送:`CODEX_BD_REVIEW_ROUND3_REQUEST.md`(基线 `c32d300`)。
- 处置:按指令 §29 写 `CODEX_UNAVAILABLE.md`,STOP BEFORE C;恢复程序见该文件与 checkpoint。
- Gate 状态:**PENDING FINAL ROUND**(r1 FAIL→fixed; r2 FAIL→fixed; r3 blocked)。
