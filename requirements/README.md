# 依赖锁与安装（GitHub 开发分支）

核对于 2026-10-27。本分支功能基线为 `a14db8e`，依赖修复为 `7dc6f22`。四份锁是精确版本锁，尚未包含本机后续的 SHA-256 加固、质量工具锁、Python 3.10 CI 锁或 PDF worker。不要套用本机未提交的安装说明。

| 本目录锁文件 | 适用环境 |
|---|---|
| `windows-vector-dev-py314-piptools.txt` | Windows/Python 3.14，vector + dev |
| `windows-local-py314-piptools.txt` | Windows/Python 3.14，local |
| `windows-collector-py314-piptools.txt` | Windows/Python 3.14，collector |
| `docker-py311-piptools.txt` | Linux/Python 3.11，local + vector，CPU Torch |

它们不是跨平台通用锁。Python 元数据声明 >=3.10，不等于每个版本均已验收。

## 安装

先用 Python 3.14 创建项目 `.venv`，在仓库根目录执行：

```powershell
.\scripts\install_locked.ps1 -Profile vector-dev
$python = ".\.venv\Scripts\python.exe"
& $python -m pip check
```

其他两个 Windows profile 用 `-Profile local` / `-Profile collector`。脚本不会覆盖 `.env`；按锁安装后以非 editable 方式安装项目。脚本受本机执行策略约束，不要求绕过策略。手动安装用：

```powershell
& $python -m pip install -r requirements/windows-vector-dev-py314-piptools.txt
& $python -m pip install --no-deps .
& $python -m pip check
```

本分支锁无哈希，不应增加 `--require-hashes` 后声称能安装。Dockerfile 当前使用清华 PyPI 与上海交大 CPU wheel 索引，`torch==2.14.0+cpu` 不能从默认 PyPI 单独解析；镜像源与工件来源边界仍需发布前核对。本轮仅整理文本，不修改索引配置或宣称已完整重建镜像。

## 更新与验证

Windows 锁由对应平台/Python 与 pip-tools 7.6.1 解析 `pyproject.toml` 和所选 extras。更新后审查差异、按锁安装、运行 `pip check`、对应测试与漏洞查询，不能把其他 profile 的安装记录当作本 profile 已通过。

最新版本更新、四锁查询与已完成的 GitHub CI 见[依赖整改](../docs/reports/dependency-remediation-2026-10-27.md)；整体证据与发布缺口见[验收摘要](../docs/reports/final-acceptance.md)。旧的全新环境安装记录属于历史，不能代替更新后逐 profile 验证。质量工具版本与当前 CI 命令以[本分支 workflow](../.github/workflows/ci.yml)为准。
