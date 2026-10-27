# RAG-Forge

本地 RAG 开发基线：Ollama embedding/生成、标题感知分块、Dense/BM25/RRF、可选 CrossEncoder、Citation、Trace、Web UI 与 benchmark 工具。

## 状态与版本

文档核对：2026-10-27。此分支的功能基线为 `a14db8e`，另有依赖修复 `7dc6f22`，包版本 `0.1.0`；属于本地 Beta，尚未完成正式发布验收。[main](https://github.com/Caser-86/RAG-Forge/tree/main) 保留早期 API 原型。

本机有基于此提交的未提交工程整改；本次仅更新 GitHub 文档，未将这些代码上传。因此本地工作树测试数量、PDF 隔离、readiness 与后续安全修复不能视为本分支能力。

当前分支有 `/api/chat`、`/api/models`、`/api/health`、`/api/traces/{trace_id}` 与静态 UI；没有后续本地整改中的 `/api/ready` 或 PDF 独立 worker。本次未手动运行该分支的模型、浏览器或容器，历史 PASS 只保留为带日期证据。

2026-10-27 依赖修复及对应 GitHub CI 已通过；验证范围统一见[验收摘要](docs/reports/final-acceptance.md)，版本与四锁查询见[依赖整改记录](docs/reports/dependency-remediation-2026-10-27.md)。这不表示目标部署、真实模型或正式质量验收通过。

[项目上下文](CONTEXT.md)描述本分支模块，[TODO](TODO.md)汇总后续事项，[验收摘要](docs/reports/final-acceptance.md)说明当前证据范围，[文档索引](docs/README.md)提供操作与历史导航。

## 安装与运行

默认类配置为 `qdrant_local`、Ollama embedding `bge-m3` 与生成 `gemma3:4b`，实际值由 `RAG_` 环境变量和 cwd 的 `.env` 覆盖。模型需先安装；不会因 README 列出名称就自动存在。

```powershell
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[vector,dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
& $python -m scripts.smoke
```

平台锁文件及其他 extras 见 [requirements/README.md](requirements/README.md)。本分支锁与本机后续修改可能不同，不能将本地新锁的版本、哈希或审计结果套用于此分支。

准备好模型、profile 和已许可文档后，再按[本地部署](docs/LOCAL-SETUP.md)完成摄入。Qdrant Local 更新时先停止占用该目录的 API；InMemory CLI 与 API 不共享索引。Windows 启停入口：

```powershell
.\scripts\start.ps1
.\scripts\status.ps1
.\scripts\stop.ps1
```

脚本须在本机执行策略允许的环境运行。手动启动可用 `& $python -m uvicorn ragforge.api.main:app --host 127.0.0.1 --port 8000`。Web UI 默认地址 `http://127.0.0.1:8000`；配置 API key 后请求需携带 `X-API-Key`。

Docker Compose 基础版使用 API-compatible 生成配置；宿主 Ollama 用 `docker-compose.ollama.yml`，容器内通过 `host.docker.internal` 连接。安装、备份与端口细节见操作手册。

## 评测和边界

`benchmarks/candidates.jsonl` 是历史候选，不能代替人工审核的 Golden。根 LICENSE、非空 Golden 与冻结 split 尚缺，发布输入仍未齐备。正式实验须先固定语料/索引身份、calibration/test 划分及阈值，失败和超时保留在分母。

旧 MLQA 数字已从入口移至[历史记录](docs/reports/legacy-mlqa-evaluation.md)。token 覆盖代理不等于事实正确率，raw reranker 分数未校准，Citation 和拒答不保证零幻觉。兼容评测、采集、重建等脚本在使用用户配置前应核对存储目标与备份，不套用本地后续隔离修复的行为说明。

模型、语料、环境文件、索引与私密报告不进入公开文档。模型下载和本地运行不代表所有材料可自由再分发；正式分发前由权利人确认代码和第三方许可。
