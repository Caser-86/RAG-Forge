# M2 Ollama Embedding 报告

## 范围

- 分支：`codex/local-rag-m0`
- 本阶段将 embedding 从默认 sentence-transformers 本地路径扩展为 Ollama `bge-m3` 路径；保留 `local` 作为 sentence-transformers 兼容后端。
- 未删除源码、资源、数据或用户未提交文件；只清理了本阶段测试产生的明确缓存目录。

## 已实现

- `OllamaClient.embed(model, texts)` 使用本机 `POST /api/embed`，发送 `model` 和批量 `input`，解析 `embeddings`；连接、超时、模型不存在和协议错误沿用 M1 分类。
- 新增 `OllamaEmbedder`，支持可配置批量大小，保持输入顺序；空输入直接返回 `(0, dim)` 的 `float32` 数组且不发 HTTP。
- 首批实际响应核对维度；配置维度不一致时明确提示 `reindex is required`，不补零、不截断。
- 对整个批次执行数值、形状、有限值、零向量和 L2 归一化检查。
- `RAGForge.ingest_chunks` 在写入向量库前检查批量形状、有限值和零向量，阻止坏向量进入存储。
- 默认 embedding 配置更新为 `ollama` + `bge-m3` + batch size `16`；`local`、`api`、`deterministic` 仍保留。
- 新增离线单元测试、真实 Ollama embedding 测试和三文档最小召回测试。

## 协议与真实结果

实际请求 `http://127.0.0.1:11434/api/embed` 成功，响应字段为 `model` 和 `embeddings`。本机 `bge-m3` 返回 1024 维向量。

固定三条文本的真实结果：

| 比较 | cosine |
|---|---:|
| 两条 RAG 文本 | 0.812163 |
| RAG 文本 1 vs 香蕉文本 | 0.297585 |
| RAG 文本 2 vs 香蕉文本 | 0.308458 |

结果符合“相近语义明显高于无关语义”的验收预期。数值只记录本机本次运行结果，未写入测试阈值。

三文档最小召回测试通过，RAG 相关文档出现在查询结果前两位；不是单文档自命中。

## 验证证据

- M2 目标单元测试：27 passed。
- 真实 Ollama embedding + 三文档召回：2 个 M1/M2 集成测试合计 `2 passed`。
- 全量离线测试：`60 passed, 2 skipped`；跳过的是默认不运行本地 Ollama 的两个集成入口。
- `ruff check`：通过。
- `compileall`：通过。
- `pip check`：通过。
- `scripts.smoke`：退出码 0，仍显式使用 offline + deterministic，不受新默认 embedding 影响。
- `git diff --check`：通过；仅有现有工作树的换行转换提示。

## 本阶段未处理

- Qdrant 本地持久化、metadata roundtrip、索引身份和生命周期属于 M3。
- 本阶段不把 Ollama embedding 结果写入持久索引，因此没有执行 reindex 或删除用户数据。
- 数据采集、清洗、增量更新和 UI 属于后续阶段。

