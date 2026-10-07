# 可复查的交换夹具

fixtureOnly=true；AI 响应是构造的测试数据，人工审核是显式测试替身。
不表示真实模型 API 调用或 ProjectMind 负责人的批准。
exchange-fixture.json 是运行 smoke.py 的实际结果，含正常/规划版本、
三种真实错误与 C 快照。没有审批/发布令牌、本机目录或真实项目数据。

两个 bundle 含本次小型真实测试 Git 仓库的完整历史，可离线复查。
在新的目录运行：

```sh
git clone code-fixture.bundle fixture-code
git -C fixture-code remote set-url origin https://example.invalid/projectmind-b-fixture.git
git clone architecture-fixture.bundle fixture-architecture
```

该 URL 仅是测试身份定位器，服务不会请求它。原代码 fixture 与接收者必须
使用完全相同定位器；用 bundle 默认的本机 origin 会产生不同 codeRepoId。
按 normalExchange 的 mapId/mapRevision/provenance.mapSourceRevision 调用：

```python
from pathlib import Path
from extensions.architecture_workspace.git_publication import GitPublisher
package = GitPublisher.read_version(Path("fixture-architecture"), map_id, map_revision, map_source_revision)
```

返回 version 应与 normalExchange.version 一致；provenance 中真实来源 SHA 一致。
planningExchange 仍为无代码 confirmed_design。版本文件没有自身 Git commit SHA，
不会创建循环摘要。不要将这些测试 fixture 导入真实正式 Model 分支。
