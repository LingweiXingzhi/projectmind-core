# evidence/ — 复现所需的原始证据

只保留"可复现验收结论"的最小集;其余派生/临时产物未上传。

| 文件 | 用途 |
|---|---|
| `holdout/GROUND_TRUTH_FROZEN.jsonl` | 24 题 Hidden Holdout 的冻结标准答案(在派发 agent 前冻结;h19 后被 PR31 证据部分推翻,见验证报告 §4) |
| `holdout/QUESTIONS.jsonl` | 24 问问题清单(无答案版,派发给 agent 的原文) |
| `poisoning/POISON_MANIFEST.json` | P01–P10 毒包清单:毒化内容 + validator 结果(PASSES_VALIDATOR / REJECTED 原因) |
| `poisoning/build_poison_packs.py` | 毒包构造脚本:在 validated head 上重跑可再生成 CLEAN + P01–P10 |
| `redteam/redteam_resolver.py` | 11 组独立红队探针(RT-A~RT-K) |
| `redteam/redteam_results.json` | 探针结果(含 5 个 finding 的实证输出) |

**未上传(派生/临时)**:poisoning 的 11 个 pack JSON(CLEAN.json + P01–P10,各约 92KB)——用 `build_poison_packs.py` 在 validated head 上重新生成(注意:live verifier 带时间戳,digest 不可字节复现,语义等价);agent 会话记录;中间脚本副本。

复现入口:
```bash
git clone <repo> && git checkout 9ea23491d1849f21bad9f60c1c1ca8df55bb5936
python -m unittest discover -s tests          # 172 tests
python evidence/poisoning/build_poison_packs.py  # 再生毒包 + validator 判定
python evidence/redteam/redteam_resolver.py      # 红队探针
```
