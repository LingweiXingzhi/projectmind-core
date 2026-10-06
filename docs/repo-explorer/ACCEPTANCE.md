# D：独立仓库样例与验收

ROLE = D。任务依据：2026-10-05 的 `PROJECTMIND_REPO_EXPLORER_4_PERSON_PLAN.md` 共同约定与 D1–D3。仅新增测试工具和本文，不改产品实现，不自动推送或建 PR。

## D1 首个交付

在仓库根目录运行 `python3 tests/repo_explorer_acceptance/fixture.py`。Windows 可将 `python3` 换成实际 Python 命令。

生成器在系统临时目录独立创建两个 Git 仓库，不使用正式仓库的 worktree。输出真实完整 base/target/second SHA、仓库路径、受版本控制路径与实际 Git rename 检测得到的变化清单；清单保存在输出的 `manifest.json`。每次重建固定内容与提交身份/日期，仍实际调用 Git 取 SHA。

样例不含地图 JSON；有源码包、普通/异步/嵌套定义、中文、空文件、绝对与相对导入、别名、缺失与歧义导入，另有语法错误、非 Python 文本、二进制、非法编码、超 1 MiB 文件、Git symlink 与 gitlink。symlink/gitlink 用 Git index 写入真实类型，不依赖系统 symlink 权限，不跟随目标。第二提交新增/修改/删除/移动；之后增加未跟踪文件与未提交文本以核查固定版本读取。第二仓库故意同名，但内容与 SHA 不同。

只生成源码，不导入或执行它；`DO_NOT_EXECUTE.py` 是用于发现错误执行的哨兵。目录外 canary 不能通过 symlink 读取。清理仅使用 `python3 tests/repo_explorer_acceptance/fixture.py --cleanup <该次 manifest 的绝对路径>`；校验生成器标记、保存的完整 manifest 和生成根目录，拒绝任意路径清理。

自检：`python3 -m unittest discover -s tests/repo_explorer_acceptance -p test_tools.py -v`。工具自检 PASS 不等于产品验收 PASS。

## 当前验收状态

D1 工具自检已执行；D2 脚本继续准备。D3 的产品 HTTP 和全部 UI 步骤为 NOT_RUN：尚未收到 A 的确切集成 checkout、完整 HEAD 与启动命令。指定共同基线不是 A 的最终集成版本，不能用它替代验收目标。
