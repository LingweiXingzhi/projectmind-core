# C_DO_NOT_ASSUME — C 实现者禁读/禁假设清单

> 每一条都有今晚实验的实证编号。写 C 时把这个文件当作 checklist 放进 PR 描述。

## 关于 Context Pack

1. **不要**以为 `validate_context_pack` 通过 = 内容真实。校验只保证结构一致(guarantee=structural_consistency_only);相干伪造能通过(poisoning P03/P05/P07/P09/P10 实证)。
2. **不要**把 `current` 投影当作完整事实——multi-scope key 会静默消失,读 `current_by_scope`(FINDING-02/RT-A)。
3. **不要**把行级 `freshness=verified` 当作"值内所有字段已验证"——只有 `verified_fields` 列出的字段经过 live 验证(FINDING-03/RT-C)。
4. **不要**解析 `do_not_assume` 里的数字(计数文本与 sections 可能不一致,validator 不查数字,FINDING-04/RT-I);只用固定禁令语义。
5. **不要**用"重新生成 pack 对比 digest"验证 pack——时间戳导致 digest 不可复现(FINDING-01);用 validator。
6. **不要**假设 pack 覆盖全部 PR——registry 只登记了 PR21/22;PR24/26/27/29/31 都不在(holdout h11-h13/h21 实证)。
7. **不要**把 `PR_OPEN` 当"可以等它合并就行"——PR22 实为 Draft(FINDING-07);合并状态判断必须独立查。
8. **不要**从 conflicts 里选边——CONFLICT 恒 HUMAN_REQUIRED(C 选边=把人裁决自动化,违反 V1 分工)。

## 关于 B(Code Facts)

9. **不要**假设 B 提供依赖/调用/签名/入口——契约明文没有;C 的依赖信号只能来自 Git diff。
10. **不要**假设 `skipped` 文件"大概没变"——skipped 的变化文件必须落 NEEDS_HUMAN_REVIEW。
11. **不要**绕过 revision 一致性检查(`CodeFacts.revision == Snapshot.revision`)。
12. **不要**假设 B 契约冻结在 PR22 版本——PR31 已在演进(facts.py 移入正式目录+SHA-256 测试);运行时以实际扩展为准。

## 关于地图与角色

13. **不要**写 `position`——那是查看布局,不是语义(README 明文);C 的 proposed_change 永远不含 position。
14. **不要**把演示图(data/project-map.json)当"团队批准的正式架构"——note 字段自述非正式;team_approved=false。
15. **不要**用 main 上的 COLLABORATION_CONTRACT 读角色——那是 pre-V1 旧映射;V1 决议在 pack 的 team.roles.v1(HUMAN_DECISION)。
16. **不要**把 MERGED 当 TEAM_APPROVED,把 merged 的地图补丁当"已接受架构"(mapSource 提案仍 PROPOSED)。
17. **不要**引用 RESEARCH(cat-file 性能)作为 C 的设计需求——它是研究建议,不是契约。
18. **不要**假设 A/B/C/D 责任位=人员;也**不要**替人决定 proposal 的接受。

## 关于自身输出

19. **没有 evidence 不出强结论**——证据不够就 UNKNOWN/NEEDS_HUMAN_REVIEW(F14/F19 fixtures)。
20. **同输入必须同输出**——不嵌入时间戳/随机数;确定性是 C 被信任的前提(resolver 同款标准)。
