# RAG-Forge 项目上下文（GitHub 开发基线）

文档核对：2026-10-27。本页对应 `codex/local-rag-m0` 已提交代码，源码基线为 `a14db8e`。本机后续未提交整改不属于本分支。

## 模块与入口

- `config.py` / `models.py`：RAG_ 配置与请求结果模型。
- `ingest/`、`embeddings.py`、`vectorstore.py`：文档解析/分块、Ollama/local/API/deterministic embedding、InMemory/Qdrant。
- `retriever/`：Dense、BM25、RRF 与可选 CrossEncoder。
- `pipeline.py`、`generator.py`、`grounding.py`：编排、生成和引用/拒答。
- `knowledge_manifest.py`、`index_manifest.py`、`collector.py`：来源、索引身份与采集增量。
- `api/`、`trace_store.py`：API、静态 UI、访问策略与 Trace。
- `evaluation/`、`scripts/`：指标、benchmark、人工审核、split/checkpoint 与发布输入检查。

规范问答为 `POST /api/chat`；另有 models、health、knowledge、sources、export、traces，兼容 `/ask`、`/query` 与 `/ingest`。此提交没有 `/api/ready` 和后续 PDF worker。

## 配置与数据

Python 元数据声明 >=3.10；默认类配置为 Qdrant Local、Ollama bge-m3、gemma3:4b。实际配置受环境变量和 cwd 的 `.env` 影响。不从历史本机路径推断当前服务或集合状态。

持久化、备份与索引迁移见[操作手册](docs/LOCAL-SETUP.md)、[迁移](docs/INDEX-MIGRATION.md)、[恢复](docs/BACKUP-RESTORE.md)。InMemory 跨进程不共享；Qdrant Local 不能让独立写入进程随意并发占用。

本分支处于 Beta。人工 Golden、冻结 split、权利人许可证及正式质量/部署验收尚未完成。历史测试和模型结果见[历史验收](docs/reports/final-acceptance-history-2026-09-19.md)；此前旧锁的 18 条告警已按[依赖整改记录](docs/reports/dependency-remediation-2026-10-27.md)处理，修复提交 `7dc6f22` 的 [GitHub CI](https://github.com/Caser-86/RAG-Forge/actions/runs/40459161031) 已通过。当前汇总见[验收摘要](docs/reports/final-acceptance.md)。
