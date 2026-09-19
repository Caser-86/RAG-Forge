# RAG-Forge 本地 RAG 项目改造执行计划

> **用途**：这份文件可以直接放进 `RAG-Forge` 仓库根目录，然后交给 Codex 按阶段执行。  
> **原则**：一次只做一个阶段；每个阶段必须先测试、再验收、再进入下一阶段。  
> **项目仓库**：`Caser-86/RAG-Forge`

---

# 0. 先看这里：你需要怎么做

你只需要负责三件事：

1. 把 `RAG-Forge` 拉到本机。
2. 把这份文件放到仓库根目录。
3. 打开 Codex，让它严格按本文件从 **M0** 开始执行。

不要让 Codex 一次性执行 M0～M10。

每完成一个阶段，Codex 必须停下来，给你以下结果：

- 修改了哪些文件
- 为什么修改
- 执行了哪些测试
- 测试结果
- 有没有已知问题
- 是否满足本阶段验收标准
- 下一阶段准备做什么

如果当前阶段测试失败：

> **禁止继续下一阶段。先修复当前阶段。**

---

# 1. 给 Codex 的第一条提示词

把下面整段直接复制给 Codex：

```text
你现在接手当前 RAG-Forge 仓库。

请先完整阅读仓库中的《RAG-Forge 本地 RAG 项目改造执行计划（版）.md》。

执行规则：

1. 当前只执行 M0，不要提前实现 M1 或之后的内容。
2. 开始修改前先检查当前 git 状态、项目结构、Python 环境、现有测试。
3. 不要删除现有可用功能。
4. 不要大规模重构目录。
5. 优先最小修改，确保每次改动都可测试、可回滚。
6. Windows 11 原生环境优先，不依赖 WSL。
7. 不要把 Docker 作为本地开发的必要条件。
8. 不要依赖 OpenAI、DeepSeek、火山等云端 LLM API。
9. 本地 Ollama 是主要模型服务。
10. 不要伪造测试结果、性能数据或评测指标。
11. 所有测试都必须真实运行。
12. 如果发现计划与当前真实代码冲突，以“保持功能正确 + 最小复杂度”为优先，并明确告诉我原因。
13. 不要因为计划里写了某个技术就机械执行。如果实际不合适，先说明并采用更简单可靠的实现。
14. 每个阶段完成后停止，输出：
    - 修改文件
    - 实现内容
    - 测试命令
    - 测试结果
    - 验收结果
    - 已知问题
    - 下一阶段建议
15. 我是，不要只告诉我“自行配置”“自行测试”“按需修改”。如果需要我操作，请直接给出可复制的 PowerShell 命令。

现在只执行 M0。
```

---

# 2. 项目最终目标

把当前 RAG-Forge 升级成：

> **一套 Windows 原生、可完全本地运行、能自动获取公开技术资料、支持混合检索、引用溯源、模型切换、拒答、调试和量化评测的 RAG 工程项目。**

最终数据流：

```text
公开官方资料
    ↓
采集
    ↓
正文清洗
    ↓
去重 / 版本管理
    ↓
结构化 Chunk
    ↓
Ollama bge-m3 Embedding
    ↓
本地持久向量库
    ↓
────────────────────────
用户问题
    ↓
可选 Query Rewrite
    ↓
Dense Retrieval + BM25
    ↓
RRF
    ↓
可选 Rerank
    ↓
证据 Context
    ↓
gemma3:4b / gemma4:e4b
    ↓
回答 + Citation
    ↓
Trace + Evaluation
```

---

# 3. 明确不做什么

以下内容第一版 **不做**：

- 不重新从零创建另一个 RAG 项目
- 不把 InsightGraph / Athena 强行合并进来
- 不先上 LangChain 或 LlamaIndex 包掉整个 RAG
- 不先做复杂 React/Next.js 前端
- 不把 Docker 作为必须依赖
- 不做用户系统
- 不做多租户
- 不做云端部署
- 不做复杂 Agent 工作流
- 不做 Fine-tuning
- 不把“自动生成很多 QA”直接当成真实评测集
- 不为了指标好看修改答案或伪造 benchmark

原因：

当前目标是先把 **RAG 核心工程能力** 做扎实，而不是扩大项目范围。

---

# 4. 本机已有模型

当前已确认 Ollama 中至少有：

```text
bge-m3
gemma3:4b
gemma4:e4b
qwen3:0.6b
```

模型分工：

| 模型 | 用途 |
|---|---|
| `bge-m3` | Embedding |
| `gemma3:4b` | 默认回答模型 |
| `gemma4:e4b` | 高质量回答模型 |
| `qwen3:0.6b` | 后期 Query Rewrite / Router |

第一版：

```text
Embedding = bge-m3
Generation = gemma3:4b
Rewrite = OFF
Rerank = 可关闭
```

---

# 5. 一个重要设计：哪些模型可以随便切

## 可以在前端直接切

生成模型：

```text
gemma3:4b
gemma4:e4b
```

切换生成模型：

- 不重新抓文档
- 不重新 Chunk
- 不重新 Embedding
- 不重新建向量索引
- 不重启 FastAPI

## 不能在聊天界面随便切

Embedding 模型。

原因：

向量库里的向量是由特定 Embedding 模型生成的。

如果把：

```text
bge-m3
```

换成另一个 Embedding 模型，就应该：

```text
重新 Embedding
→ 重建向量索引
```

因此 Embedding Model 只能放在“知识库高级设置”中，并明确提示“修改后需要 Reindex”。

---

# 6. 现有项目处理策略

## 直接保留

- FastAPI
- RAGForge Pipeline 主骨架
- Dense Retrieval
- BM25
- RRF
- Reranker 抽象
- Evaluation 基础
- Logging / Trace 思路
- pytest

## 修改

- `config.py`
- `models.py`
- `embeddings.py`
- `generator.py`
- `pipeline.py`
- `vectorstore.py`
- `ingest/chunker.py`
- `retriever/search.py`
- `retriever/sparse.py`
- `api/main.py`

## 新增

- Ollama Client
- 本地模型发现
- 公共资料 Collector
- Knowledge Manifest
- 增量更新
- Citation 结构
- Debug Trace
- 简单 Web UI
- 新 benchmark

## 暂时不删除

任何现有可工作功能。

只有在新实现稳定、测试覆盖以后，才允许删除旧兼容代码。

---

# 7. 最终优先采用的简单架构

为了降低 Windows 配置成本，第一版不要要求单独安装 Qdrant Server。

优先：

```text
Qdrant Local Persistent Mode
```

即 Python 进程直接使用本地磁盘目录：

```text
data/qdrant/
```

模式：

```text
in_memory       → 单元测试
qdrant_local    → Windows 本地默认
qdrant_server   → 以后需要 Docker/服务端再使用
```

这样第一版启动只需要：

```text
Python
Ollama
```

这比要求 Docker Desktop + Qdrant Container 更实用。

---

# 8. 前端策略

第一版不要 React / Next.js。

使用：

```text
FastAPI
+
原生 HTML
+
少量 CSS
+
少量 JavaScript
```

由 FastAPI 直接提供：

```text
http://127.0.0.1:8000/
```

原因：

- 不需要 Node.js
- 不需要 npm/pnpm
- 不需要额外前端构建
- 更容易在面试现场启动
- 已足够展示模型切换和 Retrieval Debug

以后如果项目真的需要产品化，再迁移 React。

---

# 9. 开发阶段总览

```text
M0  基线与环境检查
 ↓
M1  Ollama + 动态生成模型
 ↓
M2  Ollama bge-m3 Embedding
 ↓
M3  本地持久 Qdrant + 文档 Metadata
 ↓
M4  公开资料采集 + 清洗 + 增量更新
 ↓
M5  结构化 Chunk + Retrieval 改进
 ↓
M6  Citation + 拒答 + Trace
 ↓
M7  简单前端 + 模型切换 + Debug
 ↓
M8  Query Rewrite
 ↓
M9  Benchmark + 消融实验
 ↓
M10 最终验收 + README + 面试演示
```

---

# M0：基线与环境检查

## 目标

在任何大改之前，确认原项目当前状态。

## 本阶段禁止

- 不改模型架构
- 不抓公开资料
- 不改 Retrieval
- 不改 Chunk
- 不做 UI

## 新增文件

```text
scripts/check_environment.py
```

## 检查内容

程序必须检查：

- Python 版本
- 项目包能否 import
- Ollama 是否在线
- Ollama URL
- Ollama 本机模型列表
- 是否存在：
  - bge-m3
  - gemma3:4b
  - gemma4:e4b
  - qwen3:0.6b
- data 目录是否可写

## PowerShell 基线命令

Codex 必须实际运行：

```powershell
python --version
ollama list
python -m pip install -e ".[local,vector,dev]"
pytest -q
python -m scripts.smoke
```

如果现有项目命令与仓库真实情况不符，Codex需要修正命令并解释。

## 需要新增测试

```text
tests/test_environment.py
```

测试重点：

- 环境检查结果的数据结构稳定
- Ollama 不在线时返回明确状态，而不是程序直接崩溃
- 缺模型时能列出 missing_models

## 验收标准

必须满足：

```text
pytest 全部通过
```

并生成类似：

```text
Python: OK
Ollama: OK

Models:
bge-m3       OK
gemma3:4b    OK
gemma4:e4b   OK
qwen3:0.6b   OK
```

## M0 完成后

停止。

不要继续 M1。

---

# M1：Ollama 与动态生成模型

## 目标

回答阶段真正使用 Ollama，并能每次请求选择不同生成模型。

## 修改文件

```text
src/ragforge/config.py
src/ragforge/generator.py
src/ragforge/pipeline.py
src/ragforge/api/main.py
```

## 新增文件

```text
src/ragforge/ollama_client.py
tests/test_ollama_client.py
tests/test_model_switching.py
```

## OllamaClient 职责

只负责 Ollama HTTP 通讯：

```python
class OllamaClient:
    def health(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def generate(self, model: str, messages: list[dict], *, stream: bool = False): ...
    def embed(self, model: str, texts: list[str]) -> list[list[float]]: ...
```

不要把 RAG 业务写进 `OllamaClient`。

## Config 新增

建议：

```text
ollama_base_url = http://127.0.0.1:11434
default_generation_model = gemma3:4b
allowed_generation_models = gemma3:4b,gemma4:e4b
```

## Generator 修改

生成函数必须允许请求级模型：

```python
generate(
    query,
    evidences,
    trace_id,
    model=None,
)
```

如果 `model is None`：

```text
使用 gemma3:4b
```

如果指定：

```text
gemma4:e4b
```

本次请求使用 E4B。

不能修改全局单例导致并发请求互相串模型。

## API 新增

```text
GET /api/models
```

返回：

```json
{
  "generation": [
    "gemma3:4b",
    "gemma4:e4b"
  ],
  "embedding": [
    "bge-m3"
  ],
  "utility": [
    "qwen3:0.6b"
  ]
}
```

第一版允许：

```text
POST /api/chat
```

请求：

```json
{
  "query": "什么是 RAG？",
  "generation_model": "gemma3:4b"
}
```

## 测试要求

至少测试：

```text
默认模型
显式 gemma3
显式 gemma4
不存在模型
不允许 bge-m3 当生成模型
Ollama 掉线
```

## 验收

实际调用：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/models
```

然后分别用：

```text
gemma3:4b
gemma4:e4b
```

请求同一个问题。

必须满足：

- 两次都成功
- 返回中包含实际使用模型
- 不需要重启 API
- 不需要重新索引

完成后停止。

---

# M2：Ollama bge-m3 Embedding

## 目标

利用已经安装在 Ollama 的 `bge-m3`。

## 修改

```text
src/ragforge/embeddings.py
src/ragforge/config.py
```

## 新增测试

```text
tests/test_ollama_embeddings.py
```

## Embedder 后端

最终保留：

```text
ollama
sentence_transformers
deterministic
api（兼容旧功能，可留）
```

Windows 默认：

```text
embedder_backend=ollama
embedder_model=bge-m3
```

## 接口不改变

仍然保持：

```python
encode(texts: list[str]) -> np.ndarray
```

Retrieval 不应该知道 Embedding 来自 Ollama 还是 Hugging Face。

## 必须验证

相同文本：

```text
"retrieval augmented generation"
```

Embedding：

- 维度固定
- 数值不是全 0
- normalize 后范数合理

相近文本应该比完全无关文本 cosine 更接近。

这里测试只做 sanity check，不把某个具体 cosine 数字写死。

## 验收

重新跑：

```powershell
pytest -q
```

再做一个最小文档：

```text
RAG combines retrieval with language model generation.
```

摄入后搜索：

```text
What does RAG combine?
```

必须能找到该文档。

完成后停止。

---

# M3：持久向量库与 Metadata

## 目标

关闭程序再启动，知识库仍然存在。

## 必须修复的问题

正常启动时：

> 不能 recreate / 清空 Qdrant collection。

## Vector Store 模式

```text
in_memory
qdrant_local
qdrant_server
```

默认：

```text
qdrant_local
```

存储：

```text
data/qdrant/
```

## 修改

```text
src/ragforge/vectorstore.py
src/ragforge/config.py
src/ragforge/models.py
src/ragforge/pipeline.py
```

## 新增 Metadata

Document 至少有：

```text
id
title
text
source_url
source_type
category
language
content_hash
version
retrieved_at
active
meta
```

Chunk 至少有：

```text
id
doc_id
title
text
source
source_url
heading_path
chunk_index
meta
```

## VectorStore 增加能力

```python
add(...)
upsert(...)
delete_document(doc_id)
search(...)
count()
exists(chunk_id)
```

## 测试

新增：

```text
tests/test_qdrant_persistence.py
tests/test_metadata_roundtrip.py
```

测试：

1. 建库
2. 写入
3. 销毁 Python 对象
4. 重新创建 Store
5. 数据仍可搜索

## 验收

API 重启后：

```text
indexed_chunks
```

不能变成 0。

完成后停止。

---

# M4：公开材料获取、清洗、去重、增量更新

## 目标

用户不需要自己准备大量文件。

## 第一批来源

不要一开始抓十几个网站。

第一轮只做四个：

```text
Ollama 官方文档
Qdrant 官方文档
FastAPI 官方文档
LangChain / LangGraph 官方文档
```

第一轮目标：

```text
100～300 个有效页面
```

稳定以后才扩展：

```text
Hugging Face
Sentence Transformers
FAISS
MCP
公开论文
官方 GitHub 文档
```

## 新增目录

```text
configs/
data/raw/
data/processed/
data/reports/
```

## 新增代码

```text
src/ragforge/collector.py
src/ragforge/knowledge_manifest.py
src/ragforge/ingest/cleaner.py
scripts/fetch_sources.py
scripts/update_knowledge.py
configs/sources.yaml
```

如果单文件变得明显过大，再拆成 collector 子目录。

不要第一天为了“架构漂亮”创建十几个空文件。

## sources.yaml

每个来源保存：

```yaml
- id: ollama_docs
  type: sitemap
  base_url: https://docs.ollama.com/
  category: local_llm
  trust: 1.0
  enabled: true
```

实际 sitemap URL 由实现阶段验证。

如果站点没有 sitemap，允许使用限定域的页面发现策略。

## 采集规则

必须：

- User-Agent 明确
- 超时
- 重试
- 限速
- 遵守 robots.txt
- 单页面失败不影响其他页面
- 不无限递归
- 限定域名
- 设置最大页面数

## HTML 正文提取

优先使用成熟正文提取方案。

推荐：

```text
trafilatura
```

如果实际测试发现对官方技术文档效果不好，再 fallback BeautifulSoup：

优先：

```text
main
article
role=main
```

清除：

```text
nav
footer
aside
script
style
cookie banner
重复菜单
previous / next navigation
```

## 增量状态

使用 Python 自带 SQLite：

```text
data/knowledge_manifest.sqlite3
```

不要先引入 PostgreSQL。

Document Manifest 记录：

```text
url
content_hash
title
status
version
retrieved_at
indexed_at
```

## 更新规则

```text
新 URL
→ ADD

已有 URL + hash 不变
→ UNCHANGED

已有 URL + hash 改变
→ UPDATE
→ 删除旧 chunks
→ 新 chunks
→ 新 embeddings

旧 URL 本轮确认消失
→ INACTIVE
```

## 更新报告

每次必须生成：

```text
data/reports/update-YYYYMMDD-HHMMSS.json
```

示例：

```json
{
  "added": 20,
  "updated": 8,
  "unchanged": 151,
  "failed": 3,
  "inactive": 0
}
```

## 验收

第一次抓取后，再立即运行第二次。

第二次必须主要是：

```text
UNCHANGED
```

不能重复给所有文档做 Embedding。

完成后停止。

---

# M5：Chunk 与 Retrieval 改进

## 目标

让检索质量变得可解释、可对比。

## Chunk：实用性调整

不要假装“600 tokens”是精确值。

Ollama Embedding 路径下，我们没有直接使用 bge tokenizer。

因此默认做：

```text
Heading-aware + character budget
```

初始参数：

```text
max_chars = 2200
overlap_chars = 200
```

这是工程初始值，不是最终最佳值。

以后如果 SentenceTransformer backend 已加载对应 tokenizer，再增加真正 token-based mode。

## Heading-aware 规则

优先按照：

```text
# H1
## H2
### H3
```

保留：

```text
heading_path
```

例如：

```json
[
  "Retrieval",
  "Hybrid Search",
  "RRF"
]
```

某章节过长时再按段落/字符预算继续拆。

## BM25 必须检查中文

当前项目中文连续文本不能只被当成一个超长 token。

建议 tokenizer：

- 英文 / 数字 / 错误码：保持完整 token
- CJK：至少支持单字或 bigram
- 不强制一开始引入复杂分词服务

如果引入 `jieba` 能明显提升测试结果，可以使用；否则避免增加依赖。

## Retrieval Mode

实现三个明确模式：

```text
dense
hybrid
hybrid_rerank
```

不能所有请求永远固定执行同一套流程。

## 推荐候选数量

初始：

```text
dense top 20
bm25 top 20
↓
RRF
↓
rerank top 5
```

注意：

这只是初始配置。

最终根据 benchmark 调整。

## Reranker 实用策略

Reranker 不作为第一版“系统能否启动”的硬依赖。

支持：

```text
Fast:
dense/hybrid
```

以及：

```text
Quality:
hybrid + rerank
```

如果 bge-reranker 模型尚未下载：

- 系统正常启动
- UI 明确显示 reranker unavailable
- 不允许静默假装已经 rerank

## Trace

每个结果保留：

```text
dense_score
sparse_score
fused_score
rerank_score
```

## 验收

准备 20～30 个小测试问题：

- 语义相似
- 精确关键词
- 错误码
- 英文文档中文提问
- 无关问题

验证三种模式都可单独运行。

完成后停止。

---

# M6：真实 Citation、拒答、Trace

## 目标

回答中的引用必须真的能回到原文。

## Citation 返回结构

不要只返回：

```text
["[1]", "[2]"]
```

改成：

```json
{
  "index": 1,
  "document_id": "...",
  "chunk_id": "...",
  "title": "...",
  "url": "...",
  "snippet": "..."
}
```

## 强制校验

如果模型输出：

```text
[7]
```

但是本次 Context 只有：

```text
[1]～[5]
```

则：

```text
citation_invalid = true
```

不能假装引用有效。

## 拒答

至少三种情况应该拒答：

1. 完全没有检索结果
2. 最高证据分低于经过测试的阈值
3. 证据与问题明显不支持答案

不要只用模型自己说“信息不足”。

在生成之前就应该有工程层判断。

## Trace

新增：

```text
GET /api/traces/{trace_id}
```

至少返回：

```text
query
model
retrieval_mode
rewrite
retrieved chunks
scores
final context
timings
refused
citations
```

## Timings

记录：

```text
embedding_ms
dense_ms
sparse_ms
fusion_ms
rerank_ms
generation_ms
total_ms
```

## 验收

准备：

```text
至少 20 条“知识库不存在答案”的问题
```

要求大部分能正确拒答。

不要在这个阶段直接规定虚假的 99%。

先记录真实数据。

完成后停止。

---

# M7：Web UI + 前端模型切换 + Debug

## 目标

不写命令也能演示整个 RAG。

## 技术

只使用：

```text
HTML
CSS
Vanilla JavaScript
FastAPI StaticFiles
```

## 页面布局

建议：

```text
┌──────────────────────────────────────┐
│ RAG-Forge Local Knowledge Lab        │
├───────────────────────┬──────────────┤
│ Chat                  │ Debug        │
│                       │              │
│ 问题                  │ Query        │
│ 回答                  │ Dense        │
│ Citation              │ BM25         │
│                       │ RRF          │
│                       │ Rerank       │
│                       │ Context      │
├───────────────────────┴──────────────┤
│ Model / Retrieval / Settings         │
└──────────────────────────────────────┘
```

## 前端控制

必须有：

### 回答模型

```text
gemma3:4b
gemma4:e4b
```

数据来自：

```text
GET /api/models
```

不要把模型列表写死在 JavaScript。

### Retrieval

```text
Dense
Hybrid
Hybrid + Rerank
```

### Top-K

默认：

```text
5
```

### Query Rewrite

先显示：

```text
OFF
```

M8 完成后才真正使用。

## 模型切换验收

页面选择：

```text
gemma3:4b
```

问一次。

切：

```text
gemma4:e4b
```

再问同一个问题。

要求：

- 不刷新整个知识库
- 不重新 Embedding
- 不重新启动服务器
- UI显示本次实际模型

## Debug 面板

至少展示：

```text
Trace ID
Original Query
Rewritten Query
Dense hits
BM25 hits
RRF
Rerank
Final Context
Citation
Timing
```

## 验收

直接运行：

```powershell
python -m uvicorn ragforge.api.main:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
```

即可操作。

完成后停止。

---

# M8：Query Rewrite

## 目标

解决依赖上下文、表达含糊的问题。

## 模型

```text
qwen3:0.6b
```

## 默认

```text
OFF
```

不要默认对所有 Query 都改写。

## API

```json
{
  "rewrite": true
}
```

## Trace 必须保存

```text
original_query
rewritten_query
```

## Rewrite Prompt 约束

要求：

- 不回答问题
- 不加入原问题不存在的事实
- 保留错误码、产品名、专有名词
- 输出单条可检索 Query
- 对英文技术资料可以加入关键英文术语

例如：

```text
原始：
那第二种方法有什么缺点？

结合会话：
前面第二种方法 = Hybrid Search

改写：
Hybrid Search 在 RAG 检索中的主要缺点是什么？
```

## 验收

建立至少 20 条需要上下文的问题。

比较：

```text
rewrite OFF
vs
rewrite ON
```

只有真实提高 retrieval 才推荐默认启用。

否则继续默认 OFF。

完成后停止。

---

# M9：Benchmark 与实验

## 目标

这个项目最终不能靠“感觉回答不错”。

## 第一版 Golden Set

先人工确认：

```text
100 条
```

稳定后扩大：

```text
200～300 条
```

## 类型

建议：

| 类别 | 第一版数量 |
|---|---:|
| 基础事实 | 20 |
| 定义解释 | 15 |
| 精确关键词 / 错误码 | 15 |
| 语义改写 | 15 |
| 中文问英文资料 | 15 |
| 跨文档 | 10 |
| 无答案 | 10 |

## 数据格式

```json
{
  "id": "q001",
  "question": "...",
  "expected_doc_ids": ["..."],
  "expected_answer": "...",
  "answerable": true,
  "category": "semantic"
}
```

## 自动生成 QA 的使用规则

允许 Gemma 根据知识库帮忙生成候选问题。

但是：

> **自动生成的问题不能未经检查就算 Golden Set。**

必须至少人工抽查和修正。

## Retrieval Metrics

主要指标：

```text
Hit@K
Recall@K
MRR
```

可选：

```text
NDCG
```

## Generation Metrics

第一版：

```text
answerable accuracy（人工小样本）
citation validity
citation coverage
refusal accuracy
```

可以加：

```text
embedding similarity
```

但必须标明：

> proxy metric

不要叫“真实正确率”。

## 实验一

```text
Dense
vs
Hybrid
vs
Hybrid + Rerank
```

## 实验二

固定同一批 Evidence：

```text
gemma3:4b
vs
gemma4:e4b
```

比较：

```text
回答质量
Citation
拒答
generation latency
total latency
```

## 实验三

Chunk：

```text
1200 chars
1800 chars
2200 chars
3000 chars
```

注意：

不同 Chunk 实验必须重建索引。

## 目标指标

这些是目标，不是伪造的硬要求：

```text
Recall@5     目标 >= 0.80
Recall@10    目标 >= 0.90
MRR          目标 >= 0.70
Citation validity = 100%
```

优化后争取：

```text
Recall@5 >= 0.85
Recall@10 >= 0.92
MRR >= 0.75
```

如果真实数据低于目标：

> 保留真实结果，分析原因，继续优化。

禁止改 README 假装通过。

完成后停止。

---

# M10：最终验收与面试成品

## 功能 Gate

必须：

- Windows 原生可运行
- 不需要 WSL
- 不需要云端 LLM API
- Ollama 模型可检测
- bge-m3 可 Embedding
- gemma3:4b 可回答
- gemma4:e4b 前端可热切换
- 切换生成模型不重新建库
- Knowledge Base 重启不丢失
- 自动采集公开资料
- 增量更新
- Dense
- BM25
- RRF
- 可选 Rerank
- Citation
- Refusal
- Trace
- Evaluation
- Web UI
- pytest 全通过

## 数据规模最终建议

不要为了规模盲目抓网页。

最低成品目标：

```text
有效页面 >= 300
Chunks >= 3000
```

理想：

```text
有效页面 >= 500
Chunks >= 5000
```

如果 300 个高质量页面已经覆盖充分：

> 不需要为了数字硬抓垃圾网页。

## Citation

硬要求：

```text
虚假 Citation = 0
```

## 断网验收

在知识库已建好的情况下，断开互联网：

必须还能：

```text
查询
Embedding
Dense Search
BM25
RRF
本地 Rerank（若模型已存在）
Gemma 回答
Citation
Trace
Evaluation
```

只有：

```text
重新抓网站
```

需要联网。

## 一键启动

新增：

```text
scripts/start.ps1
scripts/status.ps1
scripts/stop.ps1
```

`start.ps1` 至少：

- 检查 Ollama
- 检查必要模型
- 启动 FastAPI
- 给出访问地址

## README 最终必须包括

```text
项目介绍
为什么做
架构
数据流程
模型角色
知识来源
安装步骤
Windows 启动
截图
API
Retrieval 设计
Chunk 设计
Citation
拒答策略
Benchmark
真实实验数字
已知限制
后续路线
```

---

# 10. 最终 5 分钟面试演示脚本

最终项目必须支持以下流程。

## 第 1 分钟

启动：

```powershell
.\scripts\start.ps1
```

展示：

```text
Ollama OK
bge-m3 OK
gemma3:4b OK
gemma4:e4b OK
Knowledge Base: XXXX chunks
```

## 第 2 分钟

前端问：

```text
RAG 中 Dense Retrieval 和 BM25 为什么要一起使用？
```

展示：

```text
回答
Citation
```

## 第 3 分钟

展开 Debug：

```text
Dense
BM25
RRF
Rerank
Final Context
```

讲清：

```text
Retrieval 负责找到证据，
Generation 负责基于证据回答。
```

## 第 4 分钟

把：

```text
gemma3:4b
```

切成：

```text
gemma4:e4b
```

问相同问题。

展示：

```text
同一套知识库
同一套 Retrieval
不同 Generation Model
```

## 第 5 分钟

问一个知识库根本没有的问题。

展示：

```text
系统拒答
```

最后打开 Evaluation：

```text
Recall@5
Recall@10
MRR
Citation
Refusal
Latency
```

---

# 11. 遇到错误时你该怎么做

你不需要自己猜。

把：

```text
完整错误
+
Codex最后做了什么
```

发给 ChatGPT。

不要自己连续执行网上搜来的多个修复命令。

尤其不要随便：

```text
删 .venv
删 data
删 qdrant
删 lock 文件
重装 Python
升级所有依赖
```

这些操作有可能把原本可定位的问题变复杂。

---

# 12. Git 操作规则

每完成一个阶段：

```powershell
git status
git diff
pytest -q
```

确认通过后提交：

```powershell
git add .
git commit -m "feat: complete M1 ollama model integration"
```

提交信息阶段对应：

```text
M0 chore: establish local baseline
M1 feat: add ollama generation and model switching
M2 feat: add ollama bge embeddings
M3 feat: add persistent local vector storage
M4 feat: add public knowledge ingestion
M5 feat: improve chunking and retrieval modes
M6 feat: add grounded citations and tracing
M7 feat: add local web ui
M8 feat: add optional query rewrite
M9 test: add rag benchmark suite
M10 docs: finalize local rag project
```

如果某阶段失败：

> 不提交一个“半完成”的主分支状态。

---

# 13. Codex 每阶段必须使用的完成模板

要求 Codex每次结束都按照：

```text
## 阶段
M?

## 完成内容
...

## 修改文件
...

## 新增文件
...

## 实际执行的测试
...

## 测试结果
PASS / FAIL

## 实际验收
...

## 已知问题
...

## 是否可以进入下一阶段
YES / NO

## 需要用户执行的命令
如果没有就写“无”
如果有，必须给完整 PowerShell 命令
```

---

# 14. 有几条建议明确被否定

为了项目实用性，以下方案现在不采用。

## 方案：马上用复杂 React 前端

否定。

原因：

它对 RAG 核心能力没有直接提升，却增加 Node、构建工具和前后端调试成本。

第一版原生 Web UI 足够。

---

## 方案：Docker + Qdrant 作为唯一运行方式

否定。

原因：

你的目标是 Windows 本地使用和面试演示。

默认 Local Persistent Qdrant 更简单。

Docker 保留为可选部署方案。

---

## 方案：所有模型都放在一个下拉框随便切

否定。

原因：

Generation Model 可以热切换。

Embedding Model 改变后应该重新建索引。

两者不是同一类设置。

---

## 方案：一开始就开启 Query Rewrite

否定。

原因：

小模型 Rewrite 可能改坏原 Query。

先建立 Retrieval baseline，再比较开启前后指标。

---

## 方案：一开始就强制 Reranker

否定。

原因：

Reranker 是质量增强，不应该成为系统基础链路能否运行的阻塞项。

先跑通 Dense + BM25 + RRF。

随后启用 Reranker 做对比实验。

---

## 方案：直接抓几万网页

否定。

原因：

RAG 不是文档越多越好。

优先：

```text
少量
高质量
可追溯
可评测
```

---

# 15. 最终验收表

Codex 完成 M10 后填写：

| 项目 | 状态 | 实际结果 |
|---|---|---|
| Windows 原生 | ⬜ | |
| Ollama | ⬜ | |
| bge-m3 Embedding | ⬜ | |
| gemma3:4b | ⬜ | |
| gemma4:e4b | ⬜ | |
| 前端模型切换 | ⬜ | |
| 持久知识库 | ⬜ | |
| 自动抓取 | ⬜ | |
| 增量更新 | ⬜ | |
| Heading-aware Chunk | ⬜ | |
| Dense | ⬜ | |
| BM25 | ⬜ | |
| RRF | ⬜ | |
| Rerank | ⬜ | |
| Citation | ⬜ | |
| Citation 虚构=0 | ⬜ | |
| Refusal | ⬜ | |
| Trace | ⬜ | |
| Debug UI | ⬜ | |
| Benchmark | ⬜ | |
| pytest | ⬜ | |
| 断网查询 | ⬜ | |
| README | ⬜ | |
| 面试 Demo | ⬜ | |

---

# 16. 你现在应该做的第一步

不要开始抓资料。

不要先改前端。

不要先下载更多模型。

当前只做：

```text
M0
```

把本文件交给 Codex，并发送第 1 节里的第一条提示词。

等 M0 完成，把 Codex 的：

```text
完成报告
+
测试结果
+
如果有错误则附错误信息
```

拿回来，再决定是否进入 M1。

---

# 17. 项目最终一句话介绍

面试时最终可以这样介绍：

> RAG-Forge 是我做的一套全本地可评测 RAG 工程系统。它可以从公开技术资料自动构建可增量更新的知识库，使用 bge-m3 做本地 Embedding，通过 Dense、BM25、RRF 和可选 Reranker 完成检索，再由可动态切换的本地 Gemma 模型生成带真实引用的回答，同时保留完整 Retrieval Trace，并用 Golden Set 对 Recall、MRR、拒答和引用有效性做量化评测。

---

**执行原则只有一个：每个阶段真实跑通，再进入下一阶段。**
