# 开发与验证指南（GitHub 开发分支）

适用范围：功能基线 `a14db8e` 及依赖修复 `7dc6f22`。本分支的 GitHub workflow 只有 Windows/Python 3.14 quality job；本机未提交的多平台 workflow、PDF worker 与哈希锁不属于这里。

## 环境与依赖

Windows vector-dev、local、collector 以及 Docker/Python 3.11 各有独立锁，见[依赖说明](../requirements/README.md)。先选 Python 3.14，再在仓库根目录执行：

```powershell
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
.\scripts\install_locked.ps1 -Profile vector-dev
```

脚本按锁安装后非 editable 安装项目；不覆盖 `.env`。质量工具未单独锁定，版本以[workflow](../.github/workflows/ci.yml)的 Install 步骤为准；当前使用：

```powershell
& $python -m pip install ruff==0.16.5 coverage==7.15.1 build==1.3.0 pip-audit==2.9.0 mypy==2.3.1
```

## 日常检查

```powershell
& $python -m pytest
& $python -m ruff check src scripts tests
& $python -m mypy src/ragforge --ignore-missing-imports --check-untyped-defs
& $python -m build --wheel
& $python -m pip_audit --strict -r requirements/windows-vector-dev-py314-piptools.txt
```

当前远端 workflow 的 coverage 命令包含测试代码；不能将其数值与本机后续 source/scripts-only 分支覆盖率比较。成功 CI 与未覆盖事项统一见[验收摘要](reports/final-acceptance.md)，旧记录不是新的验收结果。

默认离线 pytest 与真实服务分开记录。只有确认本机模型和服务后，才显式运行：

```powershell
& $python -m pytest tests/integration --run-ollama
```

start/browser 脚本把当前 `src/` 放入子进程 `PYTHONPATH`，以免误加载旧安装包；交付环境仍需重新安装当前 wheel。独立 CLI 与 API 的 InMemory 不共享；Qdrant Local 更新遵守维护窗口和备份要求。

## 运行验收

```powershell
.\scripts\verify_browser_e2e.ps1
.\scripts\verify_compose_recovery.ps1 -RunRecreate
& $python -m scripts.benchmark_runtime --repeats 12
```

这些命令可能启动临时进程、容器或模型调用，不由文本整理自动执行。浏览器使用隔离 profile；Compose 验收使用随机 project，不能对用户项目执行 `down -v`。不得把未运行的 Docker、浏览器或真实模型验收标为通过。
