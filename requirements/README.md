# 依赖锁文件

`windows-vector-dev-py314-piptools.txt` 是使用 `pip-tools 7.6.1` 在 Windows、Python 3.14 环境中从 `pyproject.toml` 解析 `vector` 与 `dev` extras 生成的锁文件；按该文件新建环境安装后已通过 `pip check` 和离线 pytest。它用于复现当前验证环境，不代表 Python 3.10/3.11 或其他平台的通用锁文件，也不包含项目自身的 editable 安装行。

另外，`windows-local-py314-piptools.txt` 与 `windows-collector-py314-piptools.txt` 已分别从 `pyproject.toml` 解析出 `local` 和 `collector` extras，并在独立 Python 3.14 临时环境中完成安装、`pip check` 与关键模块导入验证。`docker-py311-piptools.txt` 使用与 Dockerfile 一致的 CPU Torch 源生成，并在全新 Python 3.11 容器中完成按锁安装、`pip check` 和关键模块导入验证。

因此当前锁定状态已覆盖本项目当前交付路径：Windows/Python 3.14 的 vector+dev、local、collector，以及 Docker/Python 3.11 的 local+vector 均完成“解析、按锁安装、依赖检查和关键导入”。这不是 Python 3.10、其他操作系统或其他 CPU/GPU 组合的通用锁文件；不要把任一文件当作跨平台完整发布依赖。

仓库 CI 使用 `windows-latest` 运行 Windows/Python 3.14 的质量门禁，避免把 Windows 专用锁文件误用于 Linux runner；Docker/Python 3.11 依赖另由容器构建和独立验收覆盖。

安装 `docker-py311-piptools.txt` 时需要同时提供 Dockerfile 使用的两个索引：清华 PyPI 作为常规源，上海交大 CPU wheel 源作为 `--extra-index-url`；否则 `torch==2.14.0+cpu` 无法从默认 PyPI 解析。

Windows 可使用 `scripts/install_locked.ps1` 选择 `vector-dev`、`local` 或 `collector` profile；脚本不会覆盖 `.env`，安装后会运行 `pip check`。详细开发流程见 [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md)。
