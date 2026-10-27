# M10 阶段报告：Windows 启停、文档与交付材料

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

日期：2026-09-12

## 已完成

- 新增 `scripts/start.ps1`、`scripts/status.ps1`、`scripts/stop.ps1`。
- 脚本从 `$PSScriptRoot` 定位仓库，支持带空格的工作区路径，使用 `.venv\Scripts\python.exe`，默认 `127.0.0.1:8000` 与单 worker。
- 启动前检查 Ollama 与嵌入/默认生成模型；可选模型缺失只告警；API key 不写入状态和日志。
- 启动检查端口占用；已有本项目实例直接报告地址，不重复启动；端口属于其他进程时退出，不杀进程。
- PID 状态含 PID、项目路径、可执行文件、启动时间、进程启动时间、端口和日志路径，保存在 Git 忽略的 `data/run/`。
- status 只读确认自有 PID、启动时间、项目命令行和 `/api/health`；若状态无法确认，不执行停止。
- stop 在停止前再次校验 PID、启动时间、项目路径和 uvicorn 命令行，不停止 Ollama，不触碰 Qdrant 数据。
- 新增五分钟脚本：[DEMO.md](../DEMO.md)；README 补充原生 Windows 启动和 M9 实验入口。

## 已验证

| 检查 | 结果 |
|---|---|
| Windows PowerShell 5.1 语法解析 | PASS，三个脚本均通过 UTF-8 解析 |
| 工作区路径含空格 | PASS，全部路径以 `$PSScriptRoot`/绝对路径拼接 |
| 进程身份防误杀静态检查 | PASS，测试要求 PID + start time + project path + command line |
| runtime 状态不入 Git | PASS，`.gitignore` 包含 `data/run/` |
| start/status/stop 实际生命周期 | PASS，真实启动/ready、重复 start、status、stop、无实例 stop 均通过 |
| 端口冲突保护 | PASS，临时占用 8000 后 start 明确退出且未停止占用进程 |
| 缺少必需模型保护 | PASS，隔离环境变量注入缺失嵌入模型时明确退出 |
| 错误/伪造 PID 文件保护 | PASS，`status` 返回 `STALE_OR_NOT_OWNED`，`stop` 退出且未停止任何进程 |
| 干净虚拟环境安装 | PASS，临时干净环境成功安装 `.[vector,dev]`，`pip check` 与关键模块导入通过；实际解释器为 Python 3.14.6 |
| 干净环境离线回归 | 历史证据：修复可选重排状态诊断后，162 项中 160 项通过、2 项 Ollama 集成测试按设计跳过；当前工作树最新回归见 `final-acceptance.md` |
| 依赖锁 | PASS（当前交付路径），`pip-tools 7.6.1` 已生成并验证 Windows/Python 3.14 的 vector+dev、local、collector 锁，以及 Docker/Python 3.11 的 local+vector CPU 锁；各环境按锁安装，`pip check` 和关键模块导入均通过。其他 Python/OS/CPU-GPU 组合未声称支持 |
| Docker Compose/容器实际链路 | PASS，基础 Qdrant server 配置与 Ollama override 通过 `docker compose config --quiet`；使用 `RAGFORGE_QDRANT_HOST_PORT=16333`、`RAGFORGE_API_HOST_PORT=18002` 启动完整 Qdrant+API Compose，完成 ingest → hybrid chat → Citation/Trace；验收后容器、网络和卷均已清理，宿主 Qdrant/Ollama 保持可用 |
| 本地 Ollama 组件 | PASS，embedding 集成、`gemma3:4b`/`gemma4:e4b` 生成集成和本地 bge-reranker 单次实际重排均通过 |
| 当前资料量 | PASS，当前有效文档 332/目标 300，schema 2 候选索引 chunk 5,042/目标 3,000；使用官方来源增量采集和当前 800/100 分块配置，未通过缩块刷数量 |
| 互联网不可用主链路 | PASS（受控最小链路），进程级拒绝代理 + `NO_PROXY` 本机服务；真实 embedding 摄入 1 个文档后完成 `/api/chat`、Citation 与 Gemma 生成；完整 332 文档候选索引也完成真实 hybrid → Gemma → Citation/Trace 查询 |

## 限制

当前脚本已具备安全边界；真实启动使用了当前工作区带空格路径，完成了 start → ready → status → stop、重复 start、端口冲突、缺模型、无实例 stop 和错误 PID 文件保护。采集和增量更新新增可选总时限；当前 schema 2 重建索引已完成 5,042 chunk 候选集合验证，后续重建已改为按 embedding batch 调用存储层批量写入并有回归测试保护。干净 `.[vector,dev]`、`local`、`collector` 安装以及 Docker/Python 3.11 CPU 锁安装均已通过对应依赖检查；完整 Compose 双服务链路已有独立验收，当前候选集合另完成本机 Qdrant chat 验证。M9 的人工 Golden Set 仍未完成，因此本项目暂不宣布全部路线图完成。

补充环境边界：未激活的系统 `python` 当前指向 `C:\Users\MR\miniconda3\python.exe`，其中没有安装项目包且存在无关包冲突；项目交付命令必须使用 `.\.venv\Scripts\python.exe`。项目 `.venv` 已通过 `check_environment`、`pip check` 和全量回归，独立锁环境也已通过，不能用系统环境的 `pip freeze` 代替项目依赖锁。

本轮干净环境位于系统临时目录 `C:\Users\MR\AppData\Local\Temp\ragforge-clean-20260912`、`C:\Users\MR\AppData\Local\Temp\ragforge-lock-install-20260912`、`C:\Users\MR\AppData\Local\Temp\ragforge-local-lock-20260912` 和 `C:\Users\MR\AppData\Local\Temp\ragforge-collector-lock-20260912`，不在项目目录、不在 Git 状态中；验收后递归清理被当前执行安全策略拒绝，未影响项目文件和运行服务。

## 验证命令

```powershell
pytest -q tests/test_windows_scripts.py
powershell.exe -NoProfile -NonInteractive -Command "`$errors=`$null; `$tokens=`$null; foreach(`$p in @('scripts/start.ps1','scripts/status.ps1','scripts/stop.ps1')){[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path `$p),[ref]`$tokens,[ref]`$errors)>`$null}; if(`$errors.Count){exit 1}"
```
