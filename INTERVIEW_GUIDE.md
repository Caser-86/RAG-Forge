# RAG-Forge 面试要点 + 演示脚本

> 用途：GitHub 项目区面试用的辅助材料。文中的历史数字和踩坑记录来自特定本机快照，不代表当前 Golden Set 或正式发布指标；当前默认生成路径是本机 Ollama，OpenAI-compatible 后端只是兼容选项。
> 一句话定位：**可评测的检索增强问答引擎 —— 语义分块 + 稠密/BM25 混合检索 + RRF 融合 + CrossEncoder 重排 + 证据驱动生成（不足即拒答）+ 量化评测。**

---

## 一、架构与技术栈

```
用户问题
   │
   ▼
嵌入层  BAAI/bge-m3（本地开源，1024 维稠密向量）
   │
   ▼
检索层  ┌ 稠密检索（Qdrant/InMemory，余弦相似度）
        ├ BM25 稀疏检索（rank_bm25）───────► RRF 融合
        └ 按需扩展
   │     ▼
   ▼  bge-reranker（CrossEncoder）精排，输出需区分 raw / normalized 的相关性分
   │
   ▼
 生成层  证据驱动 prompt → Ollama Gemma（API 后端可选）；已校准分数才参与拒答阈值
   │
   ▼
答案（含 [n] 引用，traced）
```

- **语言/框架**：Python >=3.10；当前验证路径为 Windows/Python 3.14 与 Docker/Python 3.11；FastAPI + Uvicorn
- **向量库**：Qdrant（Docker）/ InMemory（本地离线测试）
- **嵌入/重排**：`BAAI/bge-m3` + `BAAI/bge-reranker-base`（智源开源，全部本地离线）
- **生成**：本机 Ollama `gemma3:4b`/`gemma4:e4b`；OpenAI-compatible 生成后端保留为兼容路径
- **评测**：Hit@K / Recall@K / MRR；忠实度用确定性 token 覆盖代理
- **工程化**：结构化日志 + trace_id、Docker Compose（Qdrant + API）、pytest 离线测试

---

## 二、核心亮点（按面试权重排序，挑 2-3 个深讲）

### 1. 分层检索：多路召回 + RRF 融合 + CrossEncoder 精排
- **为什么分层**：稠密向量擅长语义近义但不精确匹配，BM25 擅长精确/专有名词但忽略语义。单一召回会 miss。
- **RRF 融合**：不依赖调节权重，用 `∑ 1/(60+rank)` 把两路排序合并，鲁棒、无超参调优。
- **精排**：CrossEncoder 对「问题+候选段落」成对打分，比 BiEncoder 召回更准，把最相关顶到第一位。
- **历史实测证据**（特定本机一次检索，不是当前发布指标）：
  - 候选 `RAG技术=0.998`、`智能代理=0.009`、`苹果水果=0.000` → 语义相关性被拉开一个量级。

### 2. 证据驱动生成 + 拒答（反幻觉）
- 生成 prompt 强制**严格基于检索证据**作答，并要求标注 `[n]` 引用。
- 只有显式声明为 normalized/probability 的重排分数才参与**拒答门槛**；当前 raw 分数显示为未校准，不能直接与 `0.15` 比较或当作概率。
- **探测切入点**：把相关性 score 从「二值命中」升级成「连续分数再设阈值」——这一步是把「看起来有 RAG」做成「真的有反幻觉约束」的分水岭。

### 3. 可观测性
- 每次问答带 `trace_id`，结构化日志记录 `query / hits / best_score`，可端到端追踪单次请求命中质量。
- 面试可答：线上出问题时，凭 trace_id 定位是「检索 miss 还是生成幻觉」。

### 4. 离线可复现 + 量化评测（区别于「能用就行」的 demo 级 RAG）
- 全部模型本地开源，零 API 也可跑检索链路；LLM 走 OpenAI 兼容，可插拔。
- **评测口径与真实数字**见下节——坚持「用真实跑出的数字说话，并如实标注代理指标的局限」。

---

## 三、真实评测数字（诚实口径）

> 数据 `MLQA.en.zh`（英文问题+中文长文段）100 条，按唯一 context 去重为 80 篇；评测命令
> `python -m scripts.run_eval data/raw/mlqa_en_zh.jsonl 10`

| 阶段 | 指标 | dense_only | hybrid(+BM25/RRF) |
|---|---|---|---|
| 检索层 | Hit@10 / Recall@10 | 0.94 | 0.94 |
| 检索层 | MRR | 0.86 | 0.86 |
| 生成层 | faithfulness（token 覆盖**代理**） | 0.11 | — |
| 生成层 | refusal_rate（启用重排后） | **0.45** | — |

**怎么解释（面试时有人问"指标怎么这么怪"就这么答）：**
- 浅摘答型 MLQA 单文档命中，两路召回差异不显著——**诚实表明混合检索在无专名跨语言问句上未带来增益**，是消融该有的真实结论，比硬吹"hybrid 更强"可信。
- `faithfulness=0.11` 是**确定性 token 覆盖代理**（答案 token 被证据覆盖的比例），对短摘答偏严、拒答按 0 计入均值，是近似值，**不代表真实忠实度**；权威用 RAGAS 语义指标。
- `refusal_rate=0.45` 是启用重排后的真实表现——相关性分 <0.15 就拒答，**反幻觉约束显著增强**（未重排时几乎不拒答）。这不是退步，是高可信度策略。

---

## 四、面试常见深挖问题 + 参考回答口径

1. **为什么需要重排（reranker）？BiEncoder 不能直接排序吗**
   → 召回是 BiEncoder 近似，速度快但精度有限；重排用 CrossEncoder 对 query-passage 对精细打分，把 Top-N 里"语义近但非答案"的段落压下去，换 top1 精度。**召回求全、精排求准**。

2. **RRF 为什么不用线性融合/权重**
   → 线性融合要调双路权重且跨数据集不稳定；RRF 用排位（rank)而非分数（score），跨模型可比、无超参，是工业界常用的鲁棒方案。缺点：丢失分数幅度信息（可补分位归一）。

3. **拒答阈值怎么定，会不会误伤**
   → 阈值 0.15 来自重排分数分布观察；可在评测集中扫阈值，画出「拒答率 vs 正确率」取平衡点（下一篇可选：把 RAGAS 对拒答样例专门评估）。0.45 拒答率在安全敏感场景是偏保守的正确取向。

4. **faithfulness 你怎么测的，权威吗**
   → 明确：当前是 token 覆盖代理（近似、偏严），**标注为参考值**；权威做法接 RAGAS/LLM-as-judge，但那些本身依赖另一个 LLM、同样有偏。**能主动承认指标局限，比虚报数值更能加分。**

5. **为什么用 bge 不用 OpenAI embedding**
   → bge-m3 本地离线、零 API 费、多语言、支持词条三种粒度；对演示和隐私友好。LLM 层走 OpenAI 兼容，嵌入/生成可自由替换，体现工程抽象。

6. **InMemory 和 Qdrant 的区别，为什么要两套**
   → InMemory 用于**离线单元测试/评测**（确定性、无外部依赖）；Qdrant 用于**线上持久化+可扩展**。抽象成 `VectorStore` 接口，`build_store` 按配置切换——这也是为什么本地评测全过但 Docker 会暴露 qdrant 的 API 差异（见下）。

---

## 五、真实踩过的坑（面试最有价值的谈资）

1. **qdrant-client 1.7+ 从 `.search()` 改成 `.query_points()`**：本地 InMemory 后端掩盖了这个坑——**本地能过、切 qdrant 才炸**。教训：多后端时扎实写好集成测试，别只测默认实现。修复：`query_points(collection, query=vec, limit=k)`，读 `resp.points[].score`。
2. **Qdrant point ID 只收整数/UUID**：用 `路径::c0` 字符串当 ID 被拒。修复：`uuid5(固定namespace, chunk_id)` 派生稳定 ID，并存入 payload 以便检索还原。
3. **Docker build 连不上官方源**（PyTorch R2 / Docker Hub 均不稳定）：改用国内镜像（上海交大 pytorch-wheels、清华 PyPI、qdrant 重试）；模型**挂载宿主机而非打进镜像**，避免每镜像塞 3.4GB、避免反复下载。
4. **评测假阴性**：MLQA 同一文章含多个问题时相同段落被重复索引成不同 id，导致"内容命中却判不中"。修复：按唯一 context 建语料再对 gold。
5. **零除 / 配置前缀**：空语料 BM25 判空跳过；`.env` 使用 `RAG_` 前缀，配置会在启动时校验不支持的后端与非法分块参数。

---

## 六、现场演示脚本（Docker API :8001）

前置：`docker compose up -d`（Qdrant+API 已运行），文档已 ingest 为 1 chunk。

### 演示 1 —— 命中问答（检索→重排→生成→引用）
```powershell
$body = @{ query = "BGE-M3 是做什么用的？它的向量维度是多少？" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/api/chat -ContentType 'application/json' -Body $body
```
预期：返回 `answer`、`citations`/`citation_details` 和 `refused` 字段；是否回答取决于当前索引、模型和证据，不预设具体分数。

**讲解点**：答案内容全部来自证据、带引用、不编造。

### 演示 2 —— 拒答（证据不足则不硬编）
```powershell
$body = @{ query = "如何做一道红烧肉？" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/api/chat -ContentType 'application/json' -Body $body
```
预期：若当前语料没有可靠证据，应返回 `refused:true` 和 `refusal_reason`；拒答结果由证据、配置和模型响应共同决定。

**讲解点**：证据选择、引用校验和拒答规则共同约束幻觉；未校准的重排 raw 分数不作为概率。

### 演示 3 —— 检索视图（看多路融合 + 精排分）
```powershell
$body = @{ query = "BGE-M3 支持哪几种编码方式？" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8001/query -ContentType 'application/json' -Body $body
```
预期：命中 1 段，同时看到 `rerank_score`(精排) 与 `fused_score`(RRF 融合)。

**讲解点**：两个分数分别对应精排与融合，展示分层检索的可见性。

### 可加演 —— 观测 trace
```powershell
docker compose logs api --tail 20        # 看 trace_id 与 query/hits/best_score 日志
```

---

## 七、三句话自述（开场白模板）

> 我做了 RAG-Forge，一个**可评测**的检索增强问答引擎。核心是分层检索：**bge-m3 稠密 + BM25 稀疏双路召回，RRF 融合，再按需用 bge-reranker 精排**；生成阶段只把实际发送的证据交给模型，并用引用校验和工程拒答约束边界。整条链路可以用 deterministic/offline 配置做离线回归，也支持本机 Ollama、Docker、结构化日志和 trace。它解决的是“RAG 能跑但说不清质量、证据链不透明”的工程问题。
