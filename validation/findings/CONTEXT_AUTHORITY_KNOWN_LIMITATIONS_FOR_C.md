# CONTEXT_AUTHORITY_KNOWN_LIMITATIONS_FOR_C

> 定位:产品 bug / 已知问题 与 C blocker 的区分清单。8 条 finding 均有明确 consumer-side boundary,因此结论为 **C_CONSUMABLE_WITH_LIMITS**,而不是"Context Authority 没问题"。
> 行为规则版(给 C 代码执行用)见 `c-readiness/C_CONTEXT_SAFETY_RULES.md`。

| Finding | Issue | Severity | Blocks C? | C workaround | Suggested CA fix later |
|---|---|---|---|---|---|
| F01 | `verify=true` 时 `verified_at` 时间戳进入 digest,同一 registry 两次生成的 pack digest 不同;字节级确定性仅 `verify=false` 成立(语义级确定性始终成立) | LOW | **NO** | 验证 pack 用 `validate_context_pack`,不用"重新生成对 digest";需要可复现基线时用 `verify:false` + 显式 revision | 把 `verified_at` 排除出 digest 输入,或 digest 只覆盖语义投影 |
| F02 | 同 key 多 scope 均 ACTIVE 时,键从 `current_state.current` 便捷投影中**静默消失**(数据仍在 `current_by_scope`),conflicts=0、do_not_assume 无提示 | MEDIUM | **NO** | 只把 `current` 当索引,**一律读 `current_by_scope`** | build_do_not_assume 增加 multi-scope key 告警规则 |
| F03 | 部分 live 验证:verifier 只核 value 的部分字段(如 code_facts 的 status/pr/head),其余字段随值透传进 current,行级 `freshness=verified` 不反映字段级范围;字段级范围只在 `evidence[].live_verification.verified_fields` | MEDIUM | **NO** | 对 implementation.* 值中非核心字段,回 evidence 查 `verified_fields`;查不到的字段按 UNVERIFIED 处理 | current 行级增加 `verified_fields` 或 freshness=partial |
| F04 | `do_not_assume` 中的计数文本使用全 registry 计数,sections 是 task-domain 过滤后的;validator 的后缀匹配不校验数字(伪造包可写任意数字) | MEDIUM-LOW | **NO** | 不解析 do_not_assume 里的数字;只依赖固定禁令语义(OPEN≠merged、PROPOSAL≠架构等) | 计数按过滤后 sections 生成;validator 强制数字一致 |
| F05 | verifier 抛 `SystemExit`/BaseException 可穿透 `resolve()` 与 `ExtensionHost.run`(两者只 catch Exception;load 路径已修)——内置 verifier 不会触发,第三方 verifier 场景有风险 | LOW | **NO** | 与 C 无关(C 不注册 verifier) | `run()` 与 `_verify` 改 catch (Exception, SystemExit) |
| F06 | pack 的 `project_revision` 在包内无 evidence 锚定(孤立 SHA),仅凭 pack 无法自证 revision 绑定 | LOW | **NO** | C 消费时必须自己 PIN `expected_revision` 并传入 validator(holdout 中所有 agent 均正确存疑) | 可选:pack 内加一条 self-describing revision claim |
| F07 | PR verifier 不读取 GitHub `draft` 字段——PR #22 实为 Draft,pack 只显示 `PR_OPEN` | MEDIUM | **NO** | 对"PR 是否可合并/已交付"的判断,独立查 `gh api pulls/N` 的 draft/merged 字段 | verifier 返回值增加 `draft: bool`(schema 0.2) |
| F08 | 个别 claim 的 `source.ref` 章节级定位失准(claim-team-approval 引"§开场状态",实际文档无此章节;文件级定位正确) | LOW | **NO** | doc 类 source 做文件级核验即可,不依赖章节锚 | registry 数据修正(append-only 追加新 claim) |

## 统计

- 已知 finding:8;阻塞 C:0;建议 CA 修复:5(见 VERDICT §3)。
- 另有 2 项**非 bug 的覆盖性限制**(不属于 finding,但 C 必须知道):
  1. registry 只登记 PR21/22 head;PR24/26/27/29/31 无 claim——"pack 里没有"≠"不存在"。
  2. B 的 PR31 正在演进 code_facts(移入正式目录、--no-lazy-fetch、SHA-256 仓库测试),CA 的 `contract.code_facts_shape` 证据仍钉 PR22 README@0c46747;PR31 合并后应追加 supersedes claim。
