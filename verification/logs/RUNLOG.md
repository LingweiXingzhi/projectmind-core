# verification/logs — 原始回归运行记录(供独立核验)

由无人值守 overnight 2026-10-04 生成;md5 与文件一一对应。

| 文件 | 内容 | md5 |
|---|---|---|
| bd-integration-run3-postfix2.log | integration harness (verify_bd.py) | `9e0a05435a36c7891e485399ded2d94f` |
| stability3-harness-1.log | integration harness (verify_bd.py) | `fc61e13c94cc940e1681564d821ba4e8` |
| stability3-harness-2.log | integration harness (verify_bd.py) | `b90a992e50a4435e01d6b080b7fa18a0` |
| stability3-harness-3.log | integration harness (verify_bd.py) | `22841a575fb2ca9ca1fdc6204853baa1` |
| stability3-unittest-1.log | full unittest suite | `07750cda24fd0081fa9a376416c3a7f6` |
| stability3-unittest-2.log | full unittest suite | `f64b3d37ecaeb8d9ef638e6b9e7907b3` |
| stability3-unittest-3.log | full unittest suite | `1ad026f4a560a1ace3b26f5985acb4a3` |

关键读数:

- 每份 unittest 日志:`Ran 86 tests`,失败集恒为 2 项 Windows 环境限制错误
  (test_paths_are_exact_not_globs: 字面 `*.py` 文件名;test_symlink_and_gitlink_are_skipped: symlink 特权),md5 `3a1eda05aaeb2b4a2d1eb73cbd3da698`。
- 每份 harness 日志:`==== SUMMARY: 66/66 checks passed ====`。
- 同一失败集 md5 三轮一致 → 回归稳定。
