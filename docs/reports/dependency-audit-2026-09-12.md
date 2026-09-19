# 依赖审计记录

日期：2026-09-12（Asia/Shanghai）

## 结果

- 工具：`pip-audit 2.9.0`
- 目标：`requirements/windows-vector-dev-py314-piptools.txt`
- 命令：`pip-audit --strict -r requirements/windows-vector-dev-py314-piptools.txt`
- 结果：`No known vulnerabilities found`
- `defusedxml==0.7.1` 已作为核心依赖同步到 Windows local/vector/collector 与 Docker 锁文件；Windows 三份锁使用 `pip install --dry-run --ignore-installed -r ...` 解析成功。同日执行 `pip-audit --strict -r requirements/windows-collector-py314-piptools.txt`，结果同样为 `No known vulnerabilities found`。

审计针对已锁定的第三方依赖清单执行，不把本地项目包 `rag-forge` 当作 PyPI 发布包查询；本地项目包本身仍需随发布 wheel 进行代码审查。该结果是本次运行时点的供应链快照，不替代后续发布前复查。
