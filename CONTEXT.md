# RAG-Forge 项目上下文

> 本文件是当前项目的快速上下文入口。它描述已核对的现状，不替代阶段验收报告，也不把 provisional 结果写成正式质量结论。
> 最近核对：2026-09-19（Asia/Shanghai）。

## 项目定位

RAG-Forge 是一个可评测的本地 RAG 问答引擎：文档解析与标题感知分块 → embedding → Qdrant/InMemory 检索 → Dense/BM25/RRF，可选 CrossEncoder 重排 → 证据约束生成、引用和工程拒答 → FastAPI/Web UI/Trace。

当前状态是“本地 Beta、可继续开发，不是正式发布”。M0–M8 有实现和测试证据，M9 的候选题与实验框架已完成，但人工 Golden Set、正式 benchmark、最终许可证门禁仍未完成。

## 技术栈与运行边界

- Python：项目声明 `>=3.10`；当前已验证交付路径为 Windows/Python 3.14 和 Docker/Python 3.11。
- API/UI：FastAPI、Uvicorn，以及 `src/ragforge/api/static/` 中的原生静态页面。
- 生成/Embedding：默认设计为本机 Ollama；旧的 OpenAI-compatible 生成后端通过 `generation_backend=api` 保留。
- 向量库：`in_memory` 用于离线测试/演示，`qdrant_local` 用于本地持久化，`qdrant_server`/`qdrant` 用于 Qdrant Server 或 Compose。
- 检索：Dense、BM25、RRF、可选 `bge-reranker`；reranker 的 raw 分数不能当作概率，未校准时拒答阈值不产生正式质量结论。
- 数据身份：索引 manifest、知识库 SQLite、语料 hash、provider digest、chunk 参数和 benchmark identity 共同决定可复现性。

## 主要模块

```text
src/ragforge/config.py              配置与边界校验
src/ragforge/ingest/                解析、清洗、标题感知分块
src/ragforge/embeddings.py          Ollama/local/API/deterministic embedding
src/ragforge/vectorstore.py         InMemory、Qdrant Local/Server 抽象
src/ragforge/retriever/             Dense、BM25、RRF、reranker
src/ragforge/pipeline.py            摄入、检索、上下文、生成编排
src/ragforge/grounding.py           引用解析、证据边界、拒答检查
src/ragforge/generator.py           Ollama/API/offline 生成与模型路由
src/ragforge/api/                   API 路由、鉴权、限流、静态 UI
src/ragforge/evaluation/            指标、benchmark、split/checkpoint 身份
src/ragforge/collector.py           URL 来源采集、清洗与增量更新
scripts/                            摄入、重建、评测、验收和 Windows 启停
tests/                              离线回归、集成测试和浏览器配置测试
```

规范 API 入口是 `POST /api/chat`、`GET /api/models`、`GET /api/health`、`GET /api/traces/{trace_id}`；`/ask` 和 `/query` 是保留的兼容入口，其中 `/query` 主要用于检索调试。

## 当前验证基线

在项目虚拟环境中最近一次核对结果：

```text
pytest                         243 passed, 2 skipped
ruff check scripts src tests   All checks passed
pip check                      No broken requirements found
release_gate --json            BLOCKED
```

发布门禁当前明确阻塞：`license_missing`、`golden_empty`、`split_missing`。这三个条件分别需要权利人确认、真实人工审核和冻结题集流程；不能由自动化脚本代填。

当前评测输入状态：`benchmarks/candidates.jsonl` 有 100 条 candidate，`benchmarks/golden.jsonl` 为空，`benchmarks/golden-split.json` 尚不存在。因此所有候选实验都只能标为 provisional。

当前工作树存在大量未提交和未跟踪的开发文件。任何后续清理都必须先核对 `git status`，不能把“未被直接引用”作为删除依据。

## 常用流程

```powershell
$python = ".\\.venv\\Scripts\\python.exe"
& $python -m scripts.check_environment --json
& $python -m pytest
& $python -m ruff check scripts src tests
& $python -m pip check
```

- Windows 本地启动：`scripts/start.ps1`、`scripts/status.ps1`、`scripts/stop.ps1`。
- Qdrant Local/Server、索引迁移和恢复：见 [`docs/LOCAL-SETUP.md`](docs/LOCAL-SETUP.md)、[`docs/INDEX-MIGRATION.md`](docs/INDEX-MIGRATION.md)、[`docs/BACKUP-RESTORE.md`](docs/BACKUP-RESTORE.md)。
- 评测与 Golden：见 [`benchmarks/README.md`](benchmarks/README.md) 和 [`docs/reports/M9-benchmark.md`](docs/reports/M9-benchmark.md)。
- 发布门禁：`& $python -m scripts.release_gate --json`；退出码为 1 时不能发布。

## 文档权威关系

1. `README.md`：用户入口、安装、启动和能力边界。
2. `CONTEXT.md`：当前架构和核对基线。
3. `TODO.md`：只记录尚未完成的工作和验收出口。
4. `docs/README.md`：按用途分类的完整文档索引。
5. `docs/LOCAL-SETUP.md`、`docs/DEVELOPMENT.md`、`docs/BACKUP-RESTORE.md`、`docs/RELEASE.md`：操作手册。
6. `docs/reports/`：带日期的历史证据；以报告日期和顶部增量说明判断适用范围。
7. `docs/superpowers/plans/` 与根目录原始计划：设计/执行历史，不自动代表当前完成状态。

## 安全与数据保护约定

- `.env`、用户语料、索引、模型缓存和 `data/reports/` 不进入公开文档或发布包。
- 不打印或复制 API key、LLM key、Qdrant key 和私有路径中的敏感值。
- 生产或共享网络部署必须配置 API key、反向代理认证、TLS 和共享限流；默认 loopback 只适合本机环境。
- 删除文件前必须做全局引用、动态加载、构建、测试和 Git 状态复核；本轮文档同步不删除任何业务、数据或历史验收文件。
