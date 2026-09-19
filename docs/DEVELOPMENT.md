# 开发与验证指南

## 支持边界

- Windows/Python 3.14：`requirements/windows-vector-dev-py314-piptools.txt` 是当前验证路径。
- Windows/Python 3.14 的 `local`、`collector` extras 分别有独立锁文件。
- Docker/Python 3.11：使用 `requirements/docker-py311-piptools.txt`，Dockerfile 会按锁安装。
- `pyproject.toml` 的 `>=3.10` 是代码声明，不等于每个 Python/操作系统组合都已验收。

## 创建环境

```powershell
python -m venv .venv
.\scripts\install_locked.ps1 -Profile vector-dev
```

若只开发本地 embedding 或采集器，使用 `-Profile local` 或 `-Profile collector`。脚本安装锁文件后以非 editable 方式安装项目，并运行 `pip check`；不要把根目录 `.env`、`data/` 或模型缓存加入发布包。

## 日常检查

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m pytest
ruff check src scripts tests
& $python -m build --wheel
pip-audit --strict -r requirements/windows-vector-dev-py314-piptools.txt
```

默认测试不会访问 Ollama、Qdrant 或云端 API。需要真实本机 Ollama 时，确认模型和服务后显式运行：

```powershell
& $python -m pytest tests/integration --run-ollama
```

真实服务测试与离线回归必须分开记录；离线 `deterministic/offline` 结果不能写成生成质量指标。

本地 `start.ps1` 和浏览器验收脚本会把当前工作树的 `src/` 放到子进程 `PYTHONPATH` 首位，避免 `src` 布局项目误加载旧的非 editable 安装包；交付环境仍应按锁文件重新安装 wheel。

## 关键验收脚本

```powershell
.\scripts\verify_browser_e2e.ps1
.\scripts\verify_compose_recovery.ps1 -RunRecreate
& $python -m scripts.benchmark_runtime --repeats 12
```

浏览器脚本使用临时目录、临时进程和 deterministic/offline profile；Compose 脚本使用随机 project/临时文档，不对当前用户集合执行 `down -v`。

## 修改原则

先写能复现问题的测试，再做最小修改；每个小批次修改后立即运行对应测试。涉及索引身份、分块、资源、权限或外部服务时，同时记录配置、命令、时间和是否使用真实模型。
