# M5 验收报告：标题感知分块、中文 BM25 与检索模式

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

日期：2026-09-12  
状态：通过 M5 门禁，可进入 M6；本报告不代表 M6 已开始。

## 1. 交付范围

本阶段把原来的纯字符窗口和混合检索单路径改为可解释的标题感知分块、中文友好的 BM25，以及三个明确的请求级检索模式：`dense`、`hybrid`、`hybrid_rerank`。

## 2. 已完成修改

| 文件 | 修改内容 |
|---|---|
| `src/ragforge/ingest/chunker.py` | 标题栈、跳级标题路径、代码围栏识别、标题/段落优先分块、同章节 overlap、稳定版本化 chunk ID |
| `src/ragforge/retriever/sparse.py` | 错误码整体 token、CJK 单字+相邻 bigram、固定 tokenizer version、空语料和零/负 IDF 安全处理 |
| `src/ragforge/retriever/search.py` | dense/hybrid/hybrid_rerank 分支、Dense20/BM2520/RRF、候选上限 40、阶段分数和 score kind |
| `src/ragforge/retriever/rerank.py` | CrossEncoder 可用性状态、缓存检查、懒加载、明确的 RerankerUnavailable |
| `src/ragforge/config.py` | `retrieval_mode`、`dense_top_k`、`rerank_candidate_k`、heading chunk 默认值 2200/200 等配置 |
| `src/ragforge/pipeline.py` | 请求级模式/top_k 透传、重排器状态、稳定 chunk ID 使用、None 分数安全日志 |
| `src/ragforge/api/main.py` | Chat/Query 请求增加模式和 top_k；models/health 报告重排器状态；不可用重排返回 503 |
| `src/ragforge/models.py` | 未执行的阶段分数使用 `null`，避免把真实 0 与未执行混淆 |
| `src/ragforge/index_manifest.py` | 将 `tokenizer_version` 纳入索引身份，防止旧 tokenizer 误复用 |
| `scripts/reindex.py`、`scripts/run_eval.py`、`.env.example`、`README.md` | 使用新分块策略/检索模式并更新示例配置 |
| `tests/test_heading_chunker.py` | 标题层级、代码围栏、长段落、章节 overlap、稳定 ID 测试 |
| `tests/test_sparse_tokenizer.py` | 错误码、CJK token、空语料、零分命中、top_k=0 测试 |
| `tests/test_retrieval_modes.py` | 三种模式的调用隔离、top_k、score kind、不可用重排测试 |
| `tests/test_reranker_availability.py`、`tests/test_api_models.py` | 缓存状态、API 503、models/health 状态测试 |
| `tests/fixtures/retrieval_cases.jsonl` | 25 条检索问题，覆盖语义、关键词、错误码、跨语言、无关五类，每类 5 条 |

## 3. 验收证据

### 3.1 离线自动化

以下检查均成功：

```powershell
.venv\Scripts\python.exe -m pytest -q -rA
.venv\Scripts\python.exe -m compileall -q src scripts tests
git diff --check
```

全套测试全部通过；2 个显式 `--run-ollama` 集成测试按设计跳过。新增 M5 测试覆盖标题分块、中文 token、三模式隔离、重排器可用性、API 503 和新索引身份。

### 3.2 真实重排器

本机当前 `.env` 指向的 `bge-reranker-base` 本地路径存在，`sentence_transformers` 可用。实际执行一次 CrossEncoder 排序：

- `status_before.available=true`
- 输入 2 个候选，返回 1 个候选
- 返回分数为有限值
- 之后又通过完整 RAGForge + InMemory 链路运行了 `dense`、`hybrid`、`hybrid_rerank`
- `hybrid_rerank` 返回了 `score_kind.rerank=cross_encoder`

未写入当前 Qdrant 知识库，也没有下载新模型。

### 3.3 API 行为

- `POST /api/chat` 接收 `retrieval_mode` 和 `top_k`，并将其传到引擎。
- 非法模式返回 422。
- 请求 `hybrid_rerank` 但模型不可用时返回 503，不静默降级为 hybrid。
- `GET /api/models` 和 `/api/health` 返回 `reranker_available`、`reranker_enabled`、`reranker_reason`。
- dense 结果的 sparse/fused/rerank 分数为 `null`；hybrid 的 rerank 为 `null`；只有实际执行的阶段写入分数。

## 4. 兼容和数据保护

- `.env` 未被改写，用户现有模型、密钥和本地配置均保留。
- M5 将 chunk 策略从旧字符窗口改为 `heading_chars`，并新增 tokenizer identity；旧 M4 索引不能被无提示复用，需要使用 `scripts.reindex.py` 在新配置下生成候选集合。这是防止模型/分块/tokenizer 混用的保护，不是删除旧索引。
- 现有 M4 Qdrant 集合和本地清单没有删除或覆盖。
- 没有执行文件删除，没有修改数据库、migration、许可证或用户数据。

## 5. 暂未修改的问题

### P0/P1

当前没有在 M5 验收范围内确认的 P0/P1 问题。

### P2

1. 25 条 fixture 已建立分类和 gold 标签，但尚未形成 M9 目标的完整真实质量基准；需要在隔离实验索引上统计 Hit@K、Recall@K、MRR 和延迟。
2. `hybrid_rerank` 当前模型不可用时明确失败，不提供自动降级；这是为了避免把未执行重排伪装成成功，后续如需降级应在响应中显式记录 effective mode 和原因。
3. `Reranker` 缓存探测支持本地路径和常见 Hugging Face cache，但没有在本阶段实现模型下载策略；保持不自动联网下载。

### P3

1. 旧 API 的 evidence 输出保留兼容字段，同时新增阶段分数；更完整的结构化 Citation 和 Trace 将在 M6 处理。
2. `.env` 仍是用户本地配置，示例默认值已更新，但不会自动迁移现有 `.env`。

## 6. 下一阶段条件

M5 门禁已满足。下一步可进入 M6：拒答阈值语义、结构化 Citation、Trace 脱敏与证据支撑校验；需要继续保持新旧索引身份隔离，不直接覆盖 M4 数据。
