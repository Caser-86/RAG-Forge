# RAG-Forge

Python/FastAPI 编写的 RAG 原型：文档分块、embedding、Dense/BM25 检索、RRF 融合、可选 CrossEncoder 与 OpenAI-compatible 生成。

## 分支与状态

文档核对：2026-10-27。本页对应 `main` 中的早期 API 代码，代码基线为 `abdd77a`，包版本为 `0.1.0`。旧提交标题中的“v1.0”不作为正式发布验收依据。

[本地 RAG 开发分支](https://github.com/Caser-86/RAG-Forge/tree/codex/local-rag-m0)另有 Ollama、Web UI、Trace 和 benchmark 等实现；这些功能没有合并到当前 `main`。本机未提交的后续整改也不随本次文档更新发布。2026-10-27 的依赖修复和成功 CI 仅适用于开发分支，见[该分支验收摘要](https://github.com/Caser-86/RAG-Forge/blob/codex/local-rag-m0/docs/reports/final-acceptance.md)，不能外推为 main 已通过审计或适合部署。

本次只核对文档与已提交源码，没有重新运行本分支的模型、Docker 或质量评测。旧 README 的 MLQA 数字已移至[历史记录](docs/reports/legacy-mlqa-evaluation.md)，不能用作当前质量或发布指标。

## 代码范围

| 路径 | 作用 |
|---|---|
| `src/ragforge/ingest/` | 文档解析和字符分块 |
| `embeddings.py`、`vectorstore.py` | local/API/deterministic embedding 与 InMemory/Qdrant |
| `retriever/` | Dense、BM25、RRF 与重排 |
| `pipeline.py`、`generator.py` | 问答编排与生成 |
| `api/main.py` | `/ask`、`/query`、`/ingest`、`/health` |
| `scripts/` | 数据获取、摄入、兼容评测和 smoke |

本分支没有 `/api/chat`、`/api/ready`、原生 Web UI、PDF 独立 worker 或开发分支的发布门禁脚本。配置字段必须以本分支 `config.py` 为准。

## 安装与离线 smoke（Windows PowerShell）

```powershell
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[dev]"
$env:RAG_VECTOR_STORE = "in_memory"
& $python -m scripts.smoke
```

Python 元数据声明 `>=3.10`，不表示所有版本/平台均已完整测试。smoke 显式选择 deterministic、关闭重排并清空生成 key；上面的存储环境变量用于避免已有配置把 smoke 指向 Qdrant。

若使用真实本地 embedding/重排，安装 `.[local,dev]` 并提前下载模型；Qdrant 还需 `vector` extra。默认类配置为 InMemory、local embedding、OpenAI-compatible 生成；`RAG_` 环境变量和 cwd 的 `.env` 会覆盖默认值。

需要创建配置时先保护已有文件：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

API key 和模型服务地址由使用者配置，不提交 `.env` 或模型缓存。

## API 使用

```powershell
& $python -m uvicorn ragforge.api.main:app --host 127.0.0.1 --port 8000
```

`GET /health` 查看进程响应，`POST /ingest` 接收文件路径，`POST /query` 检索，`POST /ask` 问答。InMemory 的 CLI 与 API 是两个独立进程，需向实际服务进程摄入后再检索。该早期入口没有开发分支的完整认证和路径隔离实现，仅适合受信本机实验。

`docker-compose.yml` 含宿主模型缓存挂载配置，需要先改成目标机器的实际路径；不是可直接跨机器复用的部署文件。默认宿主端口为 API 8001、Qdrant 6333，运行前检查配置、认证和网络暴露范围。

## 评测与许可

Hit/Recall/MRR 描述检索；token 覆盖形式的 faithfulness/citation_support 是代理指标，不能等同于事实正确率。raw reranker 分数不是已校准概率，拒答比例不能证明反幻觉能力。正式质量需固定数据、模型与代码身份并人工审核。

仓库不随附完整数据和模型；open-access、本地运行与第三方材料的分发许可是不同问题。`pyproject.toml` 含 MIT 声明，但本次核对未发现根 LICENSE，正式分发前需由权利人确认文本及范围。

技术讲解见[演示与限制](INTERVIEW_GUIDE.md)。
