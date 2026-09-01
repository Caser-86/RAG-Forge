# RAG-Forge

可评测的检索增强问答引擎：语义分块 + 稠密/BM25 混合检索 + RRF 融合 + CrossEncoder 重排 + 证据驱动生成（不足即拒答）+ 量化评测。

- **技术栈**：Python 3.11 · FastAPI · Qdrant(或 InMemory) · sentence-transformers(bge) · rank_bm25 · CrossEncoder 重排 · pytest
- **数据/模型全部可选开源**：本地 `BAAI/bge-m3` 嵌入 + `bge-reranker` 重排，离线可用、零 API 费用。

## 目录结构

```text
rag-forge/
├── src/ragforge/
│   ├── config.py / models.py / embeddings.py / vectorstore.py / generator.py / pipeline.py
│   ├── ingest/        # 解析、语义分块
│   ├── retriever/     # 稠密、BM25、RRF 融合、重排
│   ├── evaluation/    # Hit@K/Recall@K/MRR + 忠实度代理指标
│   ├── api/           # FastAPI
│   └── observability/ # 结构化日志 + trace
├── scripts/           # fetch_data / ingest_docs / run_eval / smoke
├── tests/             # 单元测试（离线）
├── data/raw/docs/     # 知识库语料（放入 md/txt/pdf/html）
├── docker-compose.yml + Dockerfile
└── .env.example
```

## 快速开始

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -e ".[local,dev]"                           # 含本地 bge 嵌入
cp .env.example .env                                    # 按需填 LLM key（可选）

# 1) 拉取评测子集（MLQA 英-中）
python -m scripts.fetch_data --mlqa 100

# 2) 摄入语料（把科技文档放入 data/raw/docs/ 后）
python -m scripts.ingest_docs data/raw/docs

# 3) 离线 smoke（不依赖网络/模型，验证链路）
python -m scripts.smoke

# 4) 评测：检索层指标 + 检索策略消融
python -m scripts.run_eval data/raw/mlqa_en_zh.jsonl 10

# 5) 启动 API
uvicorn ragforge.api.main:app --reload

# 6) 或 Docker 一键起（Qdrant + API；模型挂载宿主机 modelscope 缓存，见 docker-compose.yml）
docker compose up --build
#    服务地址：API http://localhost:8001（宿主机 8000 常被 Docker 内部占用，已改映射 8001）
#    qdrant  http://localhost:6333
```

## 评测指标（如实记录）

- 检索层：`Hit@K` / `Recall@K` / `MRR`
- 生成层：`faithfulness` / `citation_support`（当前为**确定性 token 覆盖代理**，标注为参考值；权威评测请用 RAGAS）
- 消融：`纯稠密 vs 稠密+BM25(RRF) vs +重排`、分块大小 x 召回 x 延迟

> 原则：用真实跑出的数字说话，不虚报；离线回生成器仅用于检索演示，不计入生成层评测。

## 数据来源（开源/开放，个人用途）

- **评测集**：`xtreme/MLQA.en.zh`（HuggingFace）、BEIR、MS MARCO
- **语料**：arXiv(AI/ML，open-access)、开源项目文档（MIT/Apache）——放 `data/raw/docs/`
- **模型**：`BAAI/bge-m3`、`BAAI/bge-reranker-base`（北京智源，开源）

## 评测结果（真实跑出，本地 bge-m3 + bge-reranker 重排 + 火山方舟 glm-5.3-flash）

> 数据：`MLQA.en.zh`（英文问题 + 中文长文段）取 100 条；按唯一 context 去重为 80 篇文档，每问以其所属文档为检索目标。评测命令：
> `python -m scripts.run_eval data/raw/mlqa_en_zh.jsonl 10`

| 阶段 | 指标 | dense_only | hybrid(+BM25/RRF) |
|---|---|---|---|
| 检索层 | Hit@10 | 0.94 | 0.94 |
| 检索层 | Recall@10 | 0.94 | 0.94 |
| 检索层 | MRR | 0.86 | 0.86 |
| 生成层 | faithfulness（确定性 token 覆盖代理） | 0.11 | — |
| 生成层 | citation_support（代理） | 0.11 | — |
| 生成层 | refusal_rate | 0.45 | — |

说明：
- **检索层**：80 篇文档单文档命中，Hit/Recall@10=0.94、MRR=0.86。该口径下纯稠密 vs 混合差异不显著——bge-m3 稠密召回已覆盖正确文档，BM25 在无专用名词的跨语言问句上未带来额外增益。
- **生成层 0.11 为代理指标**（答案 token 被证据覆盖比例）：对短摘答型 MLQA 偏严、且拒答样本按 0 计入均值，是近似值，不代表真实忠实度；权威评测用 RAGAS 语义化指标。
- **refusal_rate 0.45 是启用重排后的真实表现**：bge-reranker 输出语义相关性分（0~1），低于阈值 0.15 即拒答。相较未重排时（仅按“是否有命中”粗判、几乎不拒答），反幻觉约束显著增强——证据不足时宁可不答、不硬编。

## 路线图（MVP）

- [x] M1 摄取闭环（解析+分块+embedding+入库）
- [x] M2 检索基线（稠密 + 指标）
- [x] M3 混合检索（BM25/RRF，含消融脚本）
- [x] M4 生成+拒答+引用（方舟 LLM 实测）
- [x] M5 工程化收尾：完成 bge-reranker 重排、扩大评测样本至 100 条、落地 Docker