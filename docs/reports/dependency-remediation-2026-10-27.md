# 依赖告警整改（2026-10-27）

范围：远端 `codex/local-rag-m0` 的旧代码基线；未合并本机大量未提交的业务整改，未修改 main、用户数据或服务配置。

## 根因与修改

原 [CI 40445704133](https://github.com/Caser-86/RAG-Forge/actions/runs/40445704133) 因 certifi 2026.7.22、pypdf 6.18.1、urllib3 2.7.0 的 18 条已知公告退出 1。后续全 profile 复查还发现 local/Docker 的 filelock 3.32.6 存在 3 条已知公告。

四份 runtime 锁仅更新原本存在的相关包：certifi → 2026.10.19，pypdf → 6.21.2，urllib3 → 2.8.0，filelock → 4.2.1。pyproject 的 pypdf 下限从 4.0 提升至 6.21.2。其他版本、依赖来源注释和原有锁格式保持不变；未关闭审计、忽略公告或删除依赖。

## 已验证证据

- 四份运行锁逐份执行 `pip-audit --no-deps --disable-pip --strict`：PyPI provider 均退出 0，无已知漏洞。
- Docker 的 CPU Torch `2.14.0+cpu` 不在 PyPI；只将它单独映射到上游 `torch==2.14.0`，用 OSV 查询退出 0。其余 71 个包仍逐个查询，没有排除 Torch 风险检查。
- 对远端源码的隔离副本执行离线 pytest：243 passed、2 skipped（未启用 live Ollama）。Ruff 与 mypy 通过。
- 验证环境是本机 Windows/Python 3.14，使用已升级包的现有环境，不等同于四 profile 的全新完整安装。当前提交 GitHub CI 会独立执行 Windows 锁安装、lint、类型检查、测试、wheel 和依赖审计；是否通过须查该提交的实际运行。

## 边界

“无已知漏洞”只指查询当时锁内包版本与公告库匹配结果，不证明所有漏洞可利用性、工件来源、独立签名或未来安全。未宣称 Docker 全新镜像、浏览器、用户持久库或正式发布验收通过。许可证、人工 Golden、split 与部署验收等既有阻塞保持不变。
