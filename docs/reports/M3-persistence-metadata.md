# M3 本地持久库、Metadata 与生命周期报告

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

## 范围

- 分支：`codex/local-rag-m0`
- 本阶段实现 Qdrant Local 持久化、统一 payload、metadata 兼容、索引身份 manifest、候选重建和资源释放。
- 未删除源码、资源、数据或用户未提交文件；真实验收使用的专用临时目录已在验证后删除。

## 已实现

- `vector_store` 支持 `qdrant_local`、`qdrant_server`、`in_memory`；旧 `qdrant` 保留为 server 别名。
- `qdrant_local` 使用 `QdrantClient(path=...)`，不把本地目录误当作 HTTP 服务；本机已安装 qdrant-client 1.19.0。
- Store 契约增加 `upsert`、`count`、`exists`、`delete_document`、`close`；旧 `add` 委托到 `upsert`。
- 本地 Qdrant 双客户端占用同一路径时转换为明确的 `VectorStoreOpenError`，提示先关闭另一客户端。
- 统一 `_chunk_to_payload` / `_chunk_from_payload`；保留 `source_url`、`heading_path`、`chunk_index` 和 `meta`，旧 payload 缺字段时使用兼容默认值。
- Document/Chunk 增加来源、版本、活动状态等字段；Chunker 将文档 metadata 传播到结构化字段和 meta。
- RAGForge 支持按文档删除并重建 BM25，避免删除后残留旧文本；`close()` 按 generator、embedder、store 顺序释放资源且可重复调用。
- 新增 `data/index_manifest.json` 原子写入与身份校验，阻断模型、维度、归一化、分块配置不匹配和无 manifest 的 legacy 库复用。
- 新增 `scripts.reindex`：写入独立候选 collection，完成数量/查询验证后才原子切换 manifest 的 `active_collection`；失败不删除旧 collection。
- `.gitignore` 增加 Qdrant、index manifest、SQLite/WAL/SHM 忽略规则；Docker 配置显式使用容器内 local embedding 和 api generation，避免默认 Ollama 地址失效。

## 自动化验证

- M3 专项测试：`13 passed`。
- 全量离线回归：`72 passed, 2 skipped`；跳过两个默认关闭的真实 Ollama 集成测试。
- 覆盖 Local 持久化重开、双客户端锁、文档删除隔离、payload roundtrip、旧 payload、空 payload、中文 metadata、manifest 原子写入、身份不匹配、损坏 manifest、legacy 阻断、候选 reindex 和 RAGForge 关闭。
- `ruff check`：通过。
- `compileall`：通过。
- `pip check`：通过。
- `git diff --check`：通过；仅有现有工作树的换行转换提示。

## 真实 API 持久化验收

使用临时 Qdrant Local 目录、Ollama `bge-m3` 和现有 `data/raw/docs/bge-rag.md`：

1. 第一次启动 API，导入后 `indexed_chunks=1`，`/api/health=1`，`/query` 命中 `bge-rag [段 1]`。
2. 停止 API，不删除 Qdrant 目录或 manifest。
3. 使用同一配置和同一路径重启 API。
4. 重启后 `/api/health` 仍为 `indexed_chunks=1`，`/query` 仍返回相同来源和内容摘要。

该验收实际通过；API 使用的临时数据随后已删除，当前 8766 端口无监听进程。

## 注意事项

- 未启动 Docker Qdrant Server，因此 `qdrant_server` 的网络连通性未做本机 live 验收；其适配路径和旧 `qdrant` 映射已保留，Local 路径为本阶段真实验收对象。
- `scripts.reindex` 测试使用 deterministic embedding 和临时 Qdrant，避免改写项目现有索引；真实生产重建前仍应停止 API，并确认当前 manifest 与目标配置。
- 旧的无 manifest 非空库不会被猜测复用，需显式执行 reindex 或人工确认后建立身份。

