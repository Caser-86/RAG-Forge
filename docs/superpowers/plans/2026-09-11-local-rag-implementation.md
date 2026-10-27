# RAG-Forge 全本地改造详细执行计划

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](../../reports/final-acceptance.md)。

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 一次只执行一个 M 阶段，完成验收后停止，等待用户决定是否进入下一阶段。

**Goal:** 在现有 RAG-Forge 上构建 Windows 原生、Ollama 驱动、知识库持久化、可增量采集、可追溯和可评测的本地 RAG 系统。

**Architecture:** 保留 FastAPI → RAGForge → Retrieval / Generation 的分层。OllamaClient 只管理模型通信；VectorStore 管理向量和元数据；SQLite Manifest 管理采集与索引状态；FastAPI 提供原生 HTML UI。默认一个 Python 服务进程独占本地 Qdrant，生成模型按请求选择。

**Tech Stack:** Python（现有声明 >=3.10；Windows 开发优先验证 3.11）、FastAPI、Pydantic、NumPy、rank-bm25、qdrant-client local、Ollama、SQLite、HTML/CSS/Vanilla JS、pytest。采集阶段按需加入 trafilatura / PyYAML；HTTP 通信使用显式声明的 httpx。

**Spec:** 根目录 `RAG-Forge_本地RAG项目改造执行计划.md`。原文件是需求来源，本文件是执行分解。以下设计为待实现契约，不代表代码已经具备这些能力。

## 1. 全局约束与阶段边界

- Windows 11 原生优先，不要求 WSL、Docker、Node.js 或云端 LLM API。
- 一次只执行 M0～M10 中一个阶段；测试失败或验收不足不得继续下一阶段。
- 保留现有可用功能；旧云端后端保留为显式选择的兼容选项，不自动调用。
- 不删除现有 `.env`、`.venv`、原始语料、Qdrant 数据、许可证或未提交开发文件。
- 当前只制定计划；不把阅读计划视为已经授权执行 M0 或提交当前所有修改。
- 所有阶段以最小可验证功能为单位；不批量升级全部依赖，不先引入 LangChain、复杂 Agent 或多租户。
- 所有测试和性能数据真实运行；未运行、跳过、环境缺失、模型不在线都单独记录。
- 模型名称是需求指定名称；本机是否安装、是否能运行、具体能力和耗时必须在执行时验证。
- 数据规模、Recall、MRR 是目标；不能通过复制 chunk、删除困难问题或改分母实现达标。
- 默认生成 `gemma3:4b`，可切换 `gemma4:e4b`；Embedding 默认 `bge-m3`；Rewrite 默认 OFF；Reranker 可缺席。
- 不把工程层拒答称为语义正确性的保证；不把引用编号合法称为引用内容真实支持答案。
- 每阶段报告修改、新增、测试、验收、已知问题、下一阶段条件，并在此停止。

## 2. 当前基线与需求差异（2026-09-11 静态核对）

| 领域 | 当前代码事实 | 处理阶段 |
|---|---|---|
| 工作树 | 有前两轮审核修改和未跟踪开发文件 | M0 记录基线，禁止整库盲目 add |
| Python | pyproject 声明 >=3.10，README 写 3.11 | M0 核对实际解释器并记录支持范围 |
| 模型生成 | 有 LLM API / OfflineGenerator，按 llm_api_key 是否非空选择 | M1 改显式 backend，本地路径不受遗留 key 影响 |
| Embedding | local / api / deterministic；无 Ollama | M2 加 ollama，保留 local 别名 |
| 存储 | InMemory / Qdrant server，集合固定 rag_forge | M3 本地持久化、集合配置、索引身份、关闭接口 |
| 启动保护 | Qdrant 已做非破坏性存在检查和维度校验 | M3 保留并适配 Local；不重复重写 |
| 索引恢复 | 已有 list_chunks 恢复 BM25 | M3 加 active/version 一致性与 Windows 关闭验证 |
| Chunk | 实际是字符窗口 800/100 | M5 heading-aware；文档不再写精确语义切块 |
| BM25 | 正则把连续中文整体作为 token | M5 单字 + bigram，保留英文错误码 |
| Retrieval | 总是 Dense + BM25 + RRF，rerank 由配置决定 | M5 请求级明确三种模式 |
| Reranker | 初始化可能直接加载/下载模型；未就绪可能抛异常 | M5 懒加载、本地缓存检查、显式 unavailable |
| 拒答 | 用真值过滤分数，0 分会被当成没有评分 | M6 区分未评分与真实 0 分，不跨模式共用阈值 |
| Citation | list[str]，只提取编号，不校验越界 | M6 新 API 结构化引用，旧接口适配 |
| API | /health /ask /query /ingest，已有 key、限流、路径限制 | 保留；M1 新 /api/models /api/chat；M7 UI |
| 生命周期 | lifespan 初始化 engine，退出未显式释放 | M3 close/finally 释放本地文件锁和客户端 |
| 日志 | ask 会记录原始 query | M6 默认脱敏日志，详细内容只放受保护 Trace |
| 评测 | MLQA 脚本 k 不保证驱动真实返回数量，复用默认存储 | M9 修复指标口径、隔离实验索引和资源释放 |
| Smoke | 指定 deterministic 但仍读取 .env 的存储配置 | M0 固定 InMemory/Offline，真正离线 |

历史 23 条测试通过只属于前次会话证据。本次计划制定没有重新运行测试，也没有确认本机 Ollama 模型状态。

## 3. 执行方式、提交与证据

### 3.1 首次执行 M0 的保护动作

1. `git status --short --untracked-files=all`、`git diff --stat`、`git diff --name-status`，记录起始状态。
2. 阅读根目录及作用目录内 AGENTS.md；检查当前分支、已有本阶段文件、现有测试。
3. 使用 `codex/local-rag-m0` 等阶段分支；分支切换保留当前工作树，不 reset、不 stash 未经确认的用户成果。
4. 需要隔离 checkout 时必须先安全保留本轮已有修改和未跟踪文件；只从 HEAD 建 worktree 会丢掉审核成果，不可直接当基线使用。
5. 阶段提交只包含本阶段明确文件/修改块。原需求中的 `git add .` 改为逐文件暂存和 staged diff 审核，避免把用户未提交内容混入。
6. 提交按用户已授权范围执行；不能因为测试通过自行推送远程。每阶段报告区分未提交、已提交、尚未验收。

### 3.2 统一开发循环

> 本节是各阶段复用的执行模板，不作为独立未完成里程碑；每个阶段的实际完成状态以其下方专属清单和验收报告为准。

- [ ] 为真正行为变更写最小回归测试，运行并确认失败原因属于缺少目标行为。
- [ ] 实现该任务的最小完整功能，避免测试只验证自定义 helper 存在而未覆盖实际路由。
- [ ] 跑针对性测试，再跑全套离线回归。
- [ ] 执行阶段真实验收命令；保存退出码、计数和必要结果，不保存密钥。
- [ ] 审查 diff、兼容行为、错误路径、资源关闭、文档一致性。
- [ ] 更新阶段报告；通过才提出进入下一阶段，当前执行停止。

PowerShell 通用命令（在仓库根目录，执行前验证 `.venv` 存在）：

```powershell
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python --version
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'dependency check failed' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'diff check failed' }
```

M0 固定离线 suite；真实服务测试通过 `--run-ollama` 显式启用，未启用显示 SKIP，不记为真实验收通过。涉及新 CLI 的命令仅在所属阶段完成后使用。

证据文件：`docs/reports/M0-baseline.md` 至 `docs/reports/M10-acceptance.md`；机器输出放忽略的 `data/reports/`。测试 fixture 和人工审阅的 benchmark 放 tracked `tests/fixtures/`、`benchmarks/`。不要将真实用户数据提交进 Git。

## 4. 目标接口与数据契约

### 4.1 模型服务与生成（M1/M2）

`src/ragforge/ollama_client.py`：

```python
class OllamaClient:
    def health(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def generate(self, model: str, messages: list[dict[str, str]], *, stream: bool = False) -> str: ...
    def embed(self, model: str, texts: list[str]) -> list[list[float]]: ...
    def close(self) -> None: ...
```

M1 只实现 health/list/generate/close；M2 实现 embed。第一版非流式；`stream=True` 明确拒绝，不假装返回完整字符串是流式实现。HTTP 路径和字段在执行时对照本机服务及官方文档验证，不仅凭记忆实现。

异常：`OllamaUnavailable`（网络）、`OllamaTimeout`（超时）、`OllamaModelNotFound`（不存在）、`OllamaProtocolError`（不合法响应），定义在同文件。API 对应 503、504、422、502；拒答是正常 200 回答，不与网络错误混淆。

生成签名统一为 `generate(query, evidences, trace_id, model=None) -> Answer`。请求模型只作为局部参数传递；禁止修改共享 `settings` 或 `self.model`。

### 4.2 API 兼容策略

- 保留 `/ask`、`/query`、`/ingest`、`/health` 的原有核心字段。
- 新 UI 统一使用 `/api/models`、`/api/chat`、`/api/traces/{trace_id}`、`/api/health`。
- `Answer` 保留旧 `citations: list[str]`，M6 新增 `citation_details: list[Citation]`；`/api/chat` 将详情序列化为 `citations`，旧 `/ask` 仍输出字符串数组。
- 新接口从 M1 起返回 model/requested_model；M5 加模式；M6 加 Trace 和 Citation；M8 前请求 `rewrite=true` 返回 422 明确不支持。
- `GET /api/models` 的 generation/embedding/utility 是实际已安装且允许使用的模型交集；`missing_models`、`reranker_available` 作为附加字段。
- 请求模型必须同时在 allowlist 和已安装集合中；不允许客户端传任意模型触发下载。
- `/` 和静态资源可提供空壳页面；业务 API 和 Trace 继续使用 key 校验。网页不内嵌服务端 key，用户输入仅保存在页面内存。

目标聊天请求：

```json
{
  "query": "Dense 与 BM25 为什么结合？",
  "generation_model": "gemma3:4b",
  "retrieval_mode": "hybrid",
  "top_k": 5,
  "rewrite": false,
  "history": []
}
```

`history` 为最多最近 6 条 `{role: user|assistant, content: string}`，每条 <=4000 字符；不允许 system/tool 角色；M8 才参与改写。`top_k` 1～20，query 去除首尾空白后非空、<=4000 字符。

### 4.3 向量库、索引身份（M3）

保留 `add/search/list_chunks/__len__`；增加 `upsert(chunk, vector)`、`delete_document(doc_id)`、`count()`、`exists(chunk_id)`、`close()`。`add` 委托 upsert，`__len__` 委托 count。Local/Server 使用相同 payload 编解码，InMemory 满足同一契约。

新增字段全部有向后兼容默认值：

- Document：source_url、source_type、category、language、content_hash、version、retrieved_at、active；保留 id/title/text/meta。
- Chunk：source_url、heading_path（list[str]）、chunk_index；version/active/index_identity 放结构化 payload 或 meta 中并统一编解码。
- Citation：index、document_id、chunk_id、title、url（无远程来源可为 null）、snippet。

`data/index_manifest.json` 保存 backend、embedding model、可取得的模型 digest、dimension、normalization、chunk strategy/config、schema_version、active_collection。字段改变时要求 reindex，不自动覆盖旧库；同维度不同模型也不可复用。

### 4.4 配置分阶段引入

| 引入阶段 | 字段 / 环境变量 | 新本地配置值 |
|---|---|---|
| M0 | 环境检查 `--ollama-url` / RAG_OLLAMA_BASE_URL | http://127.0.0.1:11434 |
| M1 | generation_backend | ollama（另保留 api/offline） |
| M1 | default_generation_model | gemma3:4b |
| M1 | allowed_generation_models | JSON 数组 ["gemma3:4b","gemma4:e4b"] |
| M1 | ollama_connect_timeout / ollama_generate_timeout | 5 秒 / 180 秒，允许配置 |
| M1 | use_rerank | 新本地配置 false，旧显式配置保持 |
| M2 | embedder_backend / embedder_model | ollama / bge-m3 |
| M2 | embedder_batch_size | 16，CPU/内存不足时降低 |
| M3 | vector_store / qdrant_path | qdrant_local / data/qdrant |
| M3 | qdrant_collection | rag_forge_local_v1 |
| M5 | retrieval_mode / dense_top_k / sparse_top_k / top_k | hybrid / 20 / 20 / 5 |
| M5 | chunk_strategy / chunk_size / chunk_overlap | heading_chars / 2200 / 200 |
| M6 | trace_max_entries / trace_ttl_seconds | 100 / 3600 |
| M6 | context_max_chars | 12000（字符上限，不声称精确 token） |
| M8 | rewrite_enabled / rewrite_model / rewrite_timeout | false / qwen3:0.6b / 30 秒 |

所有字段使用 RAG_ 前缀。旧 `local` 作为 `sentence_transformers` 别名，旧 `qdrant` 作为 `qdrant_server` 别名；不删除旧配置导致现有使用者启动失败。迁移命令采用进程环境变量覆盖旧 `.env`，不打印或重写其中密钥。

## 5. M0：基线与环境检查

**交付物：** check_environment CLI、离线回归隔离、基线报告。此阶段不接入新模型业务、不改检索算法或 UI。

**文件：** 新增 `scripts/check_environment.py`、`tests/test_environment.py`、`docs/reports/M0-baseline.md`；必要修改 `scripts/smoke.py`、`tests/conftest.py`、`pyproject.toml`、`.gitignore`。

### M0.1 解释器与工作树基线

- [x] 读取 Git 状态及 diff，记录本阶段前已有修改文件；核对当前脚本版本。
- [x] 运行 `Get-Command python,ollama -ErrorAction SilentlyContinue`、`python --version`、`.venv\Scripts\python.exe --version`，输出 sys.executable，记录实际使用哪个解释器。
- [x] 运行 `ollama list`；CLI 不存在但 HTTP 在线要分别记录，不能误判服务不可用。
- [x] 按根需求在选定虚拟环境运行 `python -m pip install -e ".[local,vector,dev]"`；报告安装前后版本变化和失败原因，不擅自全量升级。未来本地最小安装可以不含 local extra，但 M0 先复现原要求。
- [x] 核对直接 import 的 NumPy 是否直接声明；新增 HTTP 客户端需显式声明 httpx，而非依赖 openai 间接安装。变更仅补实际直接依赖。
- [x] 若虚拟环境缺失，用选定解释器创建；不得删除旧环境重建。Python 3.10/3.11 差异通过事实记录，不为规划随意重装 Python。

### M0.2 环境检查 CLI

输出稳定 JSON 契约：

```json
{
  "schema_version": 1,
  "python": {"ok": true, "version": "实际版本", "executable": "实际路径"},
  "package": {"ok": true, "error": null},
  "ollama": {"ok": true, "url": "http://127.0.0.1:11434", "models": [], "error": null},
  "required_models": ["bge-m3", "gemma3:4b", "gemma4:e4b", "qwen3:0.6b"],
  "missing_models": [],
  "data": {"ok": true, "path": "实际路径", "error": null},
  "ok": true
}
```

- [x] 将状态探测与终端格式化分开，提供 `check_environment(ollama_url, data_dir) -> dict`；调用中使用可注入 HTTP transport 进行离线测试。
- [x] 支持 `--json`、`--ollama-url`、`--data-dir`；默认检查四个指定模型。
- [x] `bge-m3` 与 `bge-m3:latest` 可等价匹配；`gemma3:4b` 必须精确 tag，不接受只有同 family 的其他尺寸。
- [x] 用有时限请求读取模型列表；连接拒绝、超时、非 JSON、无 models 字段返回明确状态。
- [x] 包检查只 import ragforge，不初始化模型或 RAGForge；数据可写性用自动关闭并删除自身的临时探针文件验证。
- [x] text 输出 OK/FAIL/MISSING，JSON 结构不随失败类型改变；整体通过 exit 0，必需项缺失 exit 1，CLI 参数错误 exit 2。

测试用例：全部正常、服务掉线、超时、非法响应、缺一个模型、缺全部模型、模型 tag 匹配、data 不可写、包导入失败、JSON CLI 退出码。HTTP 使用本地替身，不依赖本机实际 Ollama。

示例行为断言：

```python
assert report["ollama"]["ok"] is False
assert report["missing_models"] == report["required_models"]
assert report["ok"] is False
```

### M0.3 离线测试与真实验收分离

- [x] Smoke 显式指定 `_env_file=None`、in_memory、deterministic、无 LLM key、use_rerank=False；后续 M1 增加显式 offline generation。
- [x] tests/conftest 对每个测试隔离 RAG_* 环境和 get_settings cache；不能让实际 `.env` key 触发云端请求。
- [x] 先执行 baseline pytest/smoke，修复属于环境隔离和导入的问题；非 M0 架构问题报告并停止越界修改。
- [x] 再执行 `python -m scripts.check_environment --json`，保存实际报告。

```powershell
& $python -m pytest tests/test_environment.py -q
& $python -m pytest -q
& $python -m scripts.smoke
& $python -m scripts.check_environment --json
```

**Gate：** 离线全通过、smoke 真正离线、四个指定模型检测结果明确。缺任何必需模型时 M0 软件部分可完成，但环境验收 FAIL，不能写 YES。提供具体 `ollama pull 模型名` 命令，不自动大量下载或替换模型。报告后停止。

## 6. M1：Ollama 生成与请求级模型切换

**文件：** 新增 `src/ragforge/ollama_client.py`、`tests/test_ollama_client.py`、`tests/test_model_switching.py`、`tests/integration/test_ollama_generation.py`；修改 config/generator/models/pipeline/api/main、`.env.example`、smoke、pyproject、conftest。

### M1.1 Ollama 通信与显式生成后端

- [x] 通过实际 `/api/tags` 与官方协议验证响应字段和错误码；固定已验证的客户端依赖版本范围。
- [x] 用 MockTransport 测试列表、生成、模型不存在、连接失败、超时、缺 message/content、空回答、服务端错误。
- [x] 实现 OllamaClient 的健康、列表、非流式生成和 close；网络超时明确，生成不自动重试以避免重复长耗时任务。
- [x] 新增 OllamaGenerator；build_generator 根据 generation_backend 选择，不再由遗留 key 自动决定。
- [x] 已有 OfflineGenerator / LLMGenerator 接收可选 model 参数；旧云端调用必须显式 api backend；smoke 显式 offline。
- [x] 使用现有不可信资料 Prompt 边界；请求中的模型名不能变成系统指令。

### M1.2 路由与并发模型隔离

- [x] 为 `/api/models` 和 `/api/chat` 编写 TestClient 实际 HTTP 测试，验证 401、422、503、504，不能只调用 helper。
- [x] 定义 ChatRequest 的 query/generation_model，新增 Answer.model；返回请求模型与实际模型。
- [x] 未知/未安装模型在开始检索和生成前拒绝；bge-m3 不能进入生成 allowlist。
- [x] mock 客户端记录两次交错请求参数，证明不同模型不污染共享状态；本机计算可串行排队，不承诺并行加载模型。
- [x] 不在 API 模块 import 时加载重模型；新本地配置默认关闭 rerank，M5 再完整实现其可用性能力。
- [x] key 比较增加非 ASCII 请求测试；非法头不应让 hmac 字符串比较抛 500。

**验收：** 暂用 deterministic + InMemory 做检索，仅验证生成切换；固定同一条已导入证据，不把这一阶段的 retrieval 质量作为性能结论。

```powershell
$env:RAG_GENERATION_BACKEND='ollama'
$env:RAG_EMBEDDER_BACKEND='deterministic'
$env:RAG_VECTOR_STORE='in_memory'
$env:RAG_USE_RERANK='false'
& $python -m uvicorn ragforge.api.main:app --host 127.0.0.1 --port 8000
```

在第二个终端设置自己的进程环境 key（若启用），使用以下请求；先通过 `/ingest` 导入验收 fixture：

```powershell
$headers=@{}
if ($env:RAG_API_KEY) { $headers['X-API-Key']=$env:RAG_API_KEY }
Invoke-RestMethod 'http://127.0.0.1:8000/api/models' -Headers $headers
foreach ($model in @('gemma3:4b','gemma4:e4b')) {
  $body=@{query='What does RAG combine?'; generation_model=$model} | ConvertTo-Json
  Invoke-RestMethod 'http://127.0.0.1:8000/api/chat' -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
}
```

**Gate：** 两模型真实生成成功、返回真实模型、无需重启/重新摄入，旧接口回归通过；内存不足等实际错误必须报告，不用 mock 验收代替。停止。

## 7. M2：Ollama Embedding

**文件：** 修改 ollama_client/embeddings/config/pyproject；新增 `tests/test_ollama_embeddings.py`、`tests/integration/test_ollama_embeddings_live.py`、`tests/fixtures/local_rag_seed.txt`。

- [x] 核验本机 embed 协议、批量输入与输出顺序。
- [x] 单元测试空列表、批量输出数量错、维度不一致、NaN/Inf、全零向量、异常响应、模型不存在。
- [x] 实现 `OllamaEmbedder.encode(texts) -> np.ndarray[float32]`，顺序稳定、分批编码；空输入返回 `(0, dim)`，不发送 HTTP。
- [x] 首次探测并核对实际 dimension；有配置冲突直接给出 reindex 提示，不自动截断或补零。
- [x] 非零向量 L2 归一化；全零或非有限数值拒绝入库；管道在写库前验证整批形状。
- [x] local 保留为 sentence_transformers 别名；更新 Settings Literal 和对应测试。
- [x] 真实测试固定三文本：RAG combines retrieval with language model generation；Retrieval augmented generation combines search and a language model；Bananas grow in warm tropical climates。验证相近对比无关对更接近，记录结果但不写死 cosine。
- [x] 用 3 条而非只有 1 条文档执行最小召回，正确文档在 top results；单文档命中不能证明语义检索有效。

```powershell
& $python -m pytest tests/test_ollama_embeddings.py -q
& $python -m pytest tests/integration/test_ollama_embeddings_live.py --run-ollama -q
& $python -m pytest -q
```

**Gate：** bge-m3 实际返回维度一致、非零、归一化正确，正例召回通过，全套离线测试通过。停止。

## 8. M3：本地持久库、Metadata 与生命周期

**文件：** 修改 vectorstore/config/models/pipeline/api/main、scripts/ingest_docs、`.gitignore`；新增 `src/ragforge/index_manifest.py`、`scripts/reindex.py`、`tests/test_qdrant_persistence.py`、`tests/test_metadata_roundtrip.py`、`tests/test_index_identity.py`、`tests/test_store_lifecycle.py`。

### M3.1 Store 契约与 Windows 持久化

- [x] 在 tmp_path 建 Local Store，写数据，显式 close，再新建对象，搜索断言原 chunk 仍在；不能仅 del 对象寄希望于 GC。
- [x] 验证两个本地客户端同时打开同路径时给出清晰提示；默认 API 一个 worker。
- [x] 适配 qdrant_local / qdrant_server / in_memory 和 qdrant 别名；按本机安装库核验 Local 存在检查，不假设 Local 抛 HTTP 404。
- [x] 统一 payload 编解码；覆盖旧 payload 缺新字段、空 payload、中文标题、heading_path、版本、source_url roundtrip。
- [x] 实现 upsert/count/exists/delete_document/close；删除仅指定 doc_id，测试邻居文档不受影响、删除后重开不再返回。
- [x] RAGForge.close 释放 store、模型客户端；lifespan 使用 try/finally，CLI 同样关闭资源。
- [x] BM25 从有效 chunk 重建；delete/update 后同步刷新，不保留已删文本。

### M3.2 索引身份与重建

- [x] manifest 原子写入（同目录临时文件 + replace），保存模型/维度/配置身份。
- [x] 同维不同模型、维度改变、chunk 参数改变、损坏 manifest 分别测试；明确拒绝错误复用。
- [x] 未携带 manifest 的旧库默认只识别为 legacy，不猜模型身份；保留旧 server collection。
- [x] `scripts.reindex` 创建独立候选 collection，完成全部导入和查询检查后才切 active_collection；失败保留旧 active，不自动删除旧 collection。
- [x] 本地 reindex 在 API 停止时运行；如果锁被占用则退出并提示停服命令，不强行解锁文件。
- [x] 将 data/qdrant、index_manifest、SQLite/WAL/SHM、实验库加入适当 ignore 规则，不误忽略 tests fixture。

```powershell
& $python -m pytest tests/test_qdrant_persistence.py tests/test_metadata_roundtrip.py tests/test_index_identity.py tests/test_store_lifecycle.py -q
& $python -m pytest -q
```

**真实验收：** 本地 Ollama+bge-m3 写入验收 corpus → 停 API → 重启 → `/api/health` 的 indexed_chunks 和指定查询结果保持；没有 Docker/Qdrant Server 也成立。

**Gate：** 持久化、显式关闭、索引身份阻断、文档删除隔离通过。停止。

## 9. M4：公开资料采集、清洗与增量更新

**文件：** 新增 configs/sources.yaml、collector.py、knowledge_manifest.py、ingest/cleaner.py、scripts/fetch_sources.py、scripts/update_knowledge.py；新增 tests/test_collector.py、test_cleaner.py、test_knowledge_manifest.py、test_incremental_update.py、fixtures/collector/；修改 pipeline/vectorstore/pyproject/ignore。

### M4.1 来源配置与可控采集

- [x] 第一批核验 Ollama、Qdrant、FastAPI、LangChain/LangGraph 官方站点的 robots、sitemap/页面发现方式和使用条件；来源 URL 以核验为准。
- [x] sources.yaml 定义 id/type/base_url/allowed_domains/category/trust/enabled/max_pages；使用安全 YAML loader，禁止任意 Python 构造。
- [x] 明确 User-Agent：RAGForgeLocalCollector/0.1；每域单并发、初始间隔 1 秒，robots 更严格则遵从；超时 20 秒、最多 2 次重试、重定向最多 5 次、页面上限 200、响应上限 5 MiB。
- [x] 只允许 http/https；每次重定向校验域名与解析 IP，阻止 localhost、私网、链路本地、凭据 URL；不能只检查初始地址。
- [x] 429 遵从 Retry-After（有总等待上限），瞬时 5xx 退避；robots 获取异常保守跳过域并报告。
- [x] URL 去 fragment、规范化主机/默认端口，移除明确 tracking 参数；保留可能影响正文的 query；限定发现深度和总候选数。
- [x] 采集与增量更新支持可选总时限；到时停止后续请求、保留已成功页面并在报告中标记，不把部分枚举误报为完整。
- [x] 本地 HTTP fixtures 测 robots 禁止、重定向越域、超时、429、坏 sitemap、循环链接、超大页面、一个页面失败其他继续。

### M4.2 正文清洗与来源保留

- [x] trafilatura 首选，官方技术页效果通过 fixture 检查；必要时 fallback main/article/role=main 的 BeautifulSoup。
- [x] 保留 h1/h2/h3、代码块、列表和原始引用 URL；输出 Markdown/结构化文本供 M5 使用，不能清洗时把 heading 全丢掉。
- [x] 移除导航、cookie、页脚、上下一页菜单；检测登录页、空正文和明显模板页并报告 skipped。
- [x] 哈希基于规范化正文，记录 cleaner_version；记录 URL、获取时间、响应状态、许可/来源线索。
- [x] 跨 URL 同 hash 保留来源别名，只索引主文档；不要删除 provenance。

### M4.3 SQLite 状态与可恢复更新

Manifest 表最少：

```sql
CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  source_id TEXT NOT NULL,
  title TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  indexed_at TEXT,
  last_seen_run TEXT,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE update_jobs (
  job_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  target_version INTEGER NOT NULL,
  phase TEXT NOT NULL,
  error_code TEXT
);
```

实际 schema 增加 raw/processed 路径、run 摘要、来源别名表和 schema_version；SQL 全部参数化。DDL 迁移版本化，不删除旧数据库。

- [x] URL 派生稳定 doc_id；新正文 hash 改变才递增 version。
- [x] UNCHANGED：同时验证当前索引身份和上次 indexed 成功；只有正文相同但索引不存在时仍须索引，不能假报 unchanged 完成。
- [x] UPDATE：先完成新正文清洗/分块/embedding，再执行替换；新向量失败不得先删除旧 chunk。
- [x] 第一版单进程维护窗口更新：CLI 要求 API 停止，job 记录 pending/indexing/indexed/failed；重启遇到未完成 job 先恢复，避免读到半替换状态。
- [x] 新版本写入并验证数量后删除该文档旧版本，再标记 indexed；重试幂等，不能留下新旧重复结果。跨 SQLite/Qdrant 不声称原子事务，靠 job 状态和恢复流程保证最终一致。
- [x] INACTIVE：只有可证明完整来源枚举且确认消失/明确 404、410 才处理；分页上限、robots 拒绝、超时、5xx 不证明消失。
- [x] inactive 同步排除 Dense 和 BM25；正文/历史不自动物理删除。
- [x] 每次输出 run_id、added/updated/unchanged/failed/inactive/skipped、嵌入调用数、发现范围是否完整及错误摘要。

关键测试：连续两轮 unchanged 不调用 embedding；改一个文档只重算该文档；正文不变但模型身份变了不跳过；新文本变短无残留旧 chunk；中断后恢复；抓取失败不下线；跨源 hash 去重仍可追溯。

```powershell
& $python -m scripts.fetch_sources --config configs/sources.yaml --max-pages 10
& $python -m scripts.update_knowledge --config configs/sources.yaml --max-pages 10
& $python -m scripts.update_knowledge --config configs/sources.yaml --max-pages 10
```

**Gate：** 先 10 页功能验收，再放大至第一轮 100～300 有效页；第二轮主要 unchanged，embedding 计数证明未全量重算；离线 fixtures 与全套测试通过。停止。

## 10. M5：Heading Chunk、中文 BM25 与检索模式

**文件：** 修改 ingest/chunker、retriever/sparse/search/rerank、config/models/pipeline/api/main；新增 tests/test_heading_chunker.py、test_sparse_tokenizer.py、test_retrieval_modes.py、test_reranker_availability.py、fixtures/retrieval_cases.jsonl。

### M5.1 可解释分块

- [x] heading 栈维护父子层级，跳级标题也保存真实路径；代码围栏内 # 不当标题。
- [x] 默认字符预算 2200/200，先按 heading/段落，过长再字符切；空白过滤，chunk_index 稳定且排序明确。
- [x] overlap 只在同章节内延续，不把上一章节标题误附给下一章节。
- [x] 测试无标题、中文、嵌套、代码块、超长段落、标题无正文、边界刚好、最后一块；重组非重叠主体应覆盖原有效正文。
- [x] Chunk ID 包含 doc_id/version/chunk config 身份和位置，重复执行相同配置稳定；配置变更通过 M3 reindex 新库验证。

### M5.2 中英文稀疏检索

- [x] 英文小写，保留 `ERR_CONNECTION_RESET`、`HTTP_404` 等错误码整体 token；CJK 至少单字 + 相邻 bigram。
- [x] 固定 tokenizer_version，加入索引配置身份。
- [x] 测试空语料、全标点、单文档、重复中文词、混合英文数字、top_k=0；不能空 token 语料触发 BM25 初始化除零。
- [x] 记录 BM25 实现的零/负 IDF 行为，避免用 scores>0 一刀切掩盖小语料命中问题；通过关键词测试决定过滤逻辑。

### M5.3 三种明确模式

```python
retrieve(query: str, *, mode: str = "hybrid", top_k: int = 5) -> list[Evidence]
```

- [x] dense：只 Dense，不调用 BM25、RRF、Rerank。
- [x] hybrid：Dense20 + BM2520 → 按 chunk ID RRF(k=60) → top_k。
- [x] hybrid_rerank：融合候选（默认最多40）→ Rerank → top_k；实际 returned top_k 不得被旧固定配置覆盖。
- [x] Reranker 本地已有模型时可用；缺包/缺缓存时基础 API 启动正常，models/health 显示原因。
- [x] 请求 hybrid_rerank 而不可用时返回明确 503；如果提供降级选项，必须返回 requested_mode/effective_mode/fallback_reason，不静默伪装重排。
- [x] 保存原始分数和 score kind；未执行阶段用 null 区别于 0。旧 API 序列化必要时转换成原格式。
- [x] 加入 25 条小测试问题，覆盖语义、关键词、错误码、跨语言、无关，每类5条；单元测试分支用替身，真实质量测试用实际模型。

**Gate：** 三模式可分别运行；缺 reranker 时 Dense/Hybrid 可用且状态真实；可用时完成真实 rerank 验收；所有结果保留阶段分数。停止。

## 11. M6：Citation、工程拒答、Trace

**文件：** 修改 models/generator/pipeline/retriever/search/observability/logging/api/main；新增 `src/ragforge/grounding.py`、`src/ragforge/trace_store.py`、tests/test_citations.py、test_refusal.py、test_traces.py、fixtures/unanswerable.jsonl、fixtures/answerable.jsonl。

### M6.1 Context 与引用真实性

- [x] final context 使用有序 Evidence 和编号映射，预算裁剪之后再编号；Citation 只能映射实际送入模型的 chunk。
- [x] Prompt 数据结构转义/编码检索正文，测试正文包含闭合分隔符、假 system 指令和恶意来源字符串；记录防护局限。
- [x] 编号解析测试正常、多次重复、[0]、[7] 越界、无引用、代码中的类似标记；详细引用去重并保持首次出现顺序。
- [x] 新 Citation 的 title/url/snippet 均取自存储证据，不接受模型自造 URL。
- [x] 越界引用设置 citation_invalid=true，保留原始输出在 Trace；默认不把该回答标为 grounded，可返回拒答理由 invalid_citation。
- [x] 引用编号有效不代表句子获支持；字段 citation_support_status 明确 unverified/verified，第一版默认 unverified，人工评测另记录。

### M6.2 拒答策略与校准

- [x] 无 Evidence 直接拒答且不调用生成模型。
- [x] 将 rerank_score=0、负 logits、未执行重排分别处理；只有实际归一化过的分数才声称 0～1。
- [x] Dense cosine 和 rerank score 各有单独校准规则，RRF 排名分不能直接当置信度。
- [x] 用至少20条无答案 + 至少20条有答案样本校准，再留独立评测样本；记录模式、阈值、误拒/漏拒，不在评测集反复调到好看。
- [x] 对明显缺少关键实体、错误码或问题限定条件的 Evidence 设置 insufficient_support；跨语言题不能简单要求中文 query 字面重叠英文正文。
- [x] 增加生成后约束：无有效引用或输出声称资料不足，明确 refused/refusal_reason；不靠 LLM 自称作为唯一拒答依据。
- [x] 阈值未经校准的模式显示 uncalibrated，不造概率。初始验收“大部分”定义为无答案样本正确拒答超过一半，同时报告有答案误拒率；达不到就 FAIL，不改题。

### M6.3 可追溯且有界的请求状态

Trace 包含 original_query/rewritten_query/model/requested_model/retrieval_mode/effective_mode/rewrite、各阶段候选与分数、最终 context、timings、refused/refusal_reason/citations/citation_invalid、索引身份。

- [x] 使用 monotonic 分别计 embedding/dense/sparse/fusion/rerank/generation/total；可附 queue_wait 和 rewrite；total 不是简单相加并行或嵌套计时。
- [x] TraceStore 线程安全、100条/1小时 TTL、单条长度有上限；过期返回404，不无限保存完整语料。
- [x] `/api/traces/{trace_id}` 使用相同 API 认证；日志默认仅 trace_id/count/timing，不输出 query、key 或全文。
- [x] 测试 Trace ID 唯一、字段齐全、实际 context 一致、未运行阶段标记、TTL、容量、404、401和错误请求 Trace。

**Gate：** Citation 全部可回到实际 chunk、越界被标记而非接受；真实20+无答案测试有报告；有答案误拒率同时公开；Trace 受保护且可调试。停止。

## 12. M7：原生 Web UI

**文件：** 新增 `src/ragforge/api/static/index.html`、`app.css`、`app.js`、tests/test_web_ui.py、docs/reports/M7-ui.md；修改 api/main 与 pyproject package-data。

- [x] 页面分 Chat/Debug/Settings，提供输入、提交、loading、错误、重试、清空会话。
- [x] 页面启动调用 `/api/models`、`/api/health`；模型列表来自服务器，缺失模型不可选。
- [x] 支持生成模型、三模式、Top-K；Rewrite OFF 且禁用，直到 M8 能力字段启用。
- [x] 配置 API key 时在 UI 输入，内存持有并用于请求 header；不写 URL、HTML、日志或 localStorage。
- [x] 渲染回答/片段用 textContent；URL 仅允许 http/https，拒绝 javascript/data；新窗口链接加 noopener。
- [x] `/api/chat` 返回后按 trace_id 请求 Debug，展示各阶段候选、分数、来源、最终 context 和 timing；所有 unavailable/fallback 都可见。
- [x] 切模型只影响下一请求；保存每条回答的实际模型，迟到响应不能覆盖新会话；用请求序号或 AbortController 防止重复显示。
- [x] 小屏变单列，控件有 label、键盘可提交、错误可读；未完成的“取消”不能假称取消了服务端推理。
- [x] wheel 中包含静态资源，安装后的根页面和静态路径也通过测试，不只 editable 模式能打开。
- [x] 实际浏览器验收两模型同问题、不重新索引、Debug、无答案、key错误、Ollama掉线、reranker缺失；截图经确认无密钥/私人内容后存 docs/images。

**Gate：** `python -m uvicorn ragforge.api.main:app --host 127.0.0.1 --port 8000` 后直接浏览器可完成操作；无 Node 构建；浏览器控制台无未处理异常。停止。

## 13. M8：可选 Query Rewrite

**文件：** 新增 `src/ragforge/query_rewriter.py`、tests/test_query_rewriter.py、fixtures/rewrite_cases.jsonl；修改 config/pipeline/api/main/models/static/app.js。

- [x] 接口 `rewrite(query: str, history: list[dict[str,str]]) -> str`；qwen3:0.6b，只生成单条查询，不生成答案。
- [x] history 由客户端随请求传入且有上限；不保存跨用户全局对话，不引入用户系统。
- [x] 原 query 保留用于回答，rewritten_query 仅用于检索；Trace 保存两者、耗时、状态及失败原因。
- [x] rewrite=false 时不调用 utility 模型；缺模型、超时、空输出、过长输出回退原 query，并显式标记 fallback。
- [x] 约束保留实体、错误码、版本、产品名；禁止添加新事实；检查模型是否包含 think/多段解释，不能盲目把全部输出当 query。
- [x] 20条上下文依赖题，每题固定 history + expected_doc_ids，比较 OFF/ON、错误码保留和延迟；本次为 rewrite-only 真实对比，独立检索质量实验留待 M9。
- [x] 生成模型切换不改变 rewrite_model；改写绝不触发 reindex。

**Gate：** 默认 OFF、ON 可运行、Trace 完整、失败可回退、真实对比结果保存；无改善仍可交付可选功能，但不得建议默认开启。停止。

## 14. M9：Golden Set 与可复现实验

**文件：** 新增 benchmarks/golden.jsonl、benchmarks/README.md、configs/experiments.yaml、scripts/run_benchmark.py、src/ragforge/evaluation/benchmark.py、tests/test_benchmark.py、tests/test_metrics.py；修改 scripts/run_eval.py、evaluation/metrics.py。

### M9.1 数据与人工审核

- [x] 先构建100条候选：基础20/定义15/关键词15/改写15/跨语言15/跨文档10/无答案10。
- [x] 每条有 id/question/expected_doc_ids/expected_answer/answerable/category；增加 review_status、reviewer、reviewed_at 和 corpus/index身份。
- [x] 模型生成只能进入 candidate；已审核子集才能命名 golden。人工未完成时报告数量和待审核范围，不能代签审核。
- [ ] 冻结校准集与最终测试集分割；M6/M8 已用于调参题不混为新的独立测试结果。
- [x] 校验 doc_id 存在、有答案题有证据、无答案题空 expected_doc_ids、ID唯一、无重复问题泄漏。

### M9.2 指标与实验隔离

- [x] Retrieval Hit@K/Recall@K/MRR 按 document_id 去重；主指标分母仅 answerable 题，无答案单列；排序截断位置一致。
- [x] top_k 真正传到 Retrieval；若请求10只返回4必须可观察，不能仍宣称评估了足够10条候选。
- [x] Citation validity 记录合法引用数/全部引用数，并另报有引用回答覆盖率；零引用不记100%合法，无运行不记100%。
- [x] Refusal confusion matrix 输出 answerable/unanswerable 两侧误差；人工正确性指标仅人工审阅子集，标注 n。
- [x] 代理指标明确 proxy；不把 embedding similarity 或 token overlap 叫真实正确率。
- [x] 保存每题预测、证据、模型身份、索引配置、耗时、失败/跳过；网络/模型失败不能从分母悄悄删除。
- [x] 每次实验独立 Qdrant 路径/collection，显式 close；不得向日常库写入 MLQA 评测语料。

### M9.3 三组实验

| 实验 | 控制变量 | 变化量 | 结果 |
|---|---|---|---|
| A 检索 | 相同 corpus/chunk/embedding/questions | dense/hybrid/hybrid_rerank | Hit/Recall/MRR、检索延迟、不可用状态 |
| B 生成 | 预先冻结完全相同 Evidence、Prompt、问题 | gemma3:4b/gemma4:e4b | Citation、拒答、人工小样本、生成延迟 |
| C Chunk | 相同正文、问题、模型 | 1200/1800/2200/3000 chars | chunk量、Recall/MRR、建库成本 |

- [x] B 每条 evidence cache 记录 hash，切模型不重新检索；固定 temperature 与其他支持参数，记录非确定性。
- [x] C 每组重建独立库，overlap 默认200并记录；不能同库混不同 chunk 配置。
- [x] 冷启动耗时与预热后 p50/p95 分开；记录 CPU/GPU/RAM、模型版本、样本量、重复次数，GPU 未查询时明确记录，硬件不足用真实耗时说明。
- [x] 输出 JSON + Markdown 摘要；目标 Recall@5>=0.80、Recall@10>=0.90、MRR>=0.70 仅作对照，未达标照实保留。

```powershell
& $python -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments.yaml --experiment retrieval
& $python -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments.yaml --experiment generation
& $python -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments.yaml --experiment chunking
```

**Gate：** 100条实际人工确认 Golden Set、三组真实实验可复现、指标单元测试通过。缺人工审阅时阶段未完全验收，不编造审阅者。停止。

## 15. M10：Windows 启停、断网验收、文档与交付

**文件：** 新增 scripts/start.ps1、status.ps1、stop.ps1、docs/DEMO.md、docs/reports/M10-acceptance.md；修改 README、INTERVIEW_GUIDE、`.env.example`、Dockerfile/Compose（只兼容性更新）、pyproject 和锁文件。

### M10.1 原生启动与进程所有权

- [x] start 从 `$PSScriptRoot` 定位仓库，支持带空格路径；使用项目 `.venv`，默认127.0.0.1:8000、一个 worker。
- [x] 检查 Ollama 在线、bge-m3/default generation 存在、库身份一致；缺可选模型明确说明，不阻断基础启动；最终双模型 Gate 仍要求两者可用。
- [x] 已运行同一实例时报告地址，不重复启动；端口被其他程序占用时退出，不杀其他进程。
- [x] Start-Process 使用 Hidden；记录 PID、启动时间、可执行文件和项目路径到忽略的 data/run 文件；日志不带 key。
- [x] readiness 轮询有超时，区分进程已起与服务就绪；给出 URL、模型状态和 indexed_chunks。
- [x] status 只读检查自有实例；stop 校验 PID+启动时间+路径避免 PID 复用误杀，优先正常关闭释放 Qdrant，不停止用户 Ollama。
- [x] 测试重复 start/stop、无实例 stop、端口冲突、目录带空格、错误 PID 文件和缺模型；真实完整 chat 场景已覆盖。

### M10.2 可复现安装

- [x] 在干净临时虚拟环境验证最小 `.[vector,dev]` 本地模式，local extra 仅用于可选 reranker/ST；M4 collector 依赖单独明确。
- [x] 基于成功解析结果生成锁文件；优先使用 pip-tools，分别锁 Windows core/optional rerank 与容器依赖，不用当前污染环境的 pip freeze 充当跨平台锁。
- [x] 锁工具版本已记录为 `pip-tools 7.6.1`；干净环境按 Windows/Python 3.14 锁安装后跑离线回归通过；无法验证的 Python/OS 组合不声称支持。
- [x] README PowerShell 使用 `.\.venv\Scripts\python.exe`、Copy-Item 等正确语法，说明覆盖旧 env 的本地 backend 配置。
- [x] 可选 Docker 显式 server backend；容器访问宿主机 Ollama 的地址单独说明，不把127.0.0.1错误当宿主地址。

### M10.3 最终验收与材料

- [x] 页面去重后的有效资料目标>=300、chunk>=3000；当前 schema 2 候选索引为 332 个有效文档、5,042 个 chunks，已达到目标，未通过缩块刷数。此前 5,240 个 chunks 属于历史 schema 1 快照。
- [x] 使用进程级拒绝代理（`HTTP_PROXY/HTTPS_PROXY/ALL_PROXY=127.0.0.1:9`，`NO_PROXY=127.0.0.1,localhost`）完成互联网不可用最小链路；未断开整机网络；容器端到端链路已有独立证据，当前 schema 2 候选索引链路另已完成本机 Qdrant/API 验证。
- [x] 离线/本机验证 query embedding、Dense/BM25/RRF、已有本地 Rerank、两种生成、Citation/Trace/Evaluation；采集仍明确需要联网。
- [x] README 按需求包含架构、数据流、模型分工、来源、Windows命令、截图、API、Chunk/检索/拒答设计、真实benchmark、限制、路线图。
- [x] 旧 README 数字标记历史评测的原始配置，不挪作新 Ollama 项目成绩；无法复现数字不宣称最新结果。
- [x] DEMO 按5分钟脚本：启动、混合检索问答、Debug、切模型、拒答、真实指标入口；冷启动超过现场时间要事先预热并说明。
- [ ] 根需求最终验收表逐项填 PASS/FAIL/SKIP/结果证据路径，只有全部必需项完成才宣布项目完成。

```powershell
.\scripts\start.ps1
.\scripts\status.ps1
.\scripts\stop.ps1
```

**Gate：** Windows 原生、断网主链路、持久化、两模型切换、采集增量、三检索模式可观察、引用合法、拒答真实评测、UI、全测试和文档均有证据。停止并交付，不自动部署云端。

## 16. 关键风险、处理策略与回滚

| 风险 | 执行策略 | 回滚/恢复 |
|---|---|---|
| 既有未提交修改混入 | 每阶段记录基线和精确diff | 仅撤销本阶段hunk，不能 git reset --hard |
| 旧 .env 触发云端请求 | 显式 generation backend、测试env隔离 | 恢复进程变量，不覆盖密钥文件 |
| 两个Gemma无法同时驻留内存 | 允许串行请求、记录切换/加载耗时 | 保留默认小模型，双模型验收如实失败 |
| 本地Qdrant文件被多进程占用 | 单worker，CLI维护窗口，显式close | 停止自有进程后正常重开，不删除锁/数据库 |
| 同维模型污染原索引 | manifest身份校验、新collection重建 | active_collection切回已验证旧集合 |
| 更新崩溃留下半版本 | job日志、维护窗口、重试幂等 | 恢复完成前不提供不一致索引 |
| 网页消失判定错误 | 区分完整枚举和限额/失败 | 保持旧active，人工核实来源 |
| Reranker真实输出不是概率 | 保存score kind，分模式校准 | 保留hybrid，显式报告不可用 |
| Prompt注入或越界引用 | 来源不可信、引用映射、后校验 | 拒绝invalid回答，保留Trace用于诊断 |
| Benchmark越调越偏 | 分离校准/测试，固定corpus | 回到冻结实验配置，不替换困难问题 |
| 依赖解析不可复现 | 分平台锁、干净环境验证 | 保留上一版锁，不全量盲目升级 |

## 17. 完成报告模板与需求覆盖

```text
## 阶段
M?
## 完成内容
实际行为和关键设计取舍
## 修改文件
路径、原因、兼容性影响
## 新增文件
路径、职责
## 实际执行的测试
完整命令、解释器、退出码
## 测试结果
PASS / FAIL / SKIP；数量和未执行原因
## 实际验收
模型、库路径、数据量、真实调用结果、证据文件
## 已知问题
风险、缺口和下一步
## 是否可以进入下一阶段
YES / NO，并说明对应Gate
## 需要用户执行的命令
无，或完整PowerShell命令
```

覆盖映射：环境M0；Ollama模型发现/切换M1；bge-m3 M2；持久化/metadata/reindex M3；采集/robots/清洗/SQLite/增量M4；heading/CJK/三模式/可选重排M5；Citation/Refusal/Trace/Timing M6；Web UI/Debug M7；Rewrite/history M8；Golden Set/三消融/指标M9；Windows启停/锁定/断网/README/面试Demo M10。

原需求未展开但本计划补齐的执行前提：请求级历史、模型身份校验、Local close、跨存储恢复、来源消失证明、旧接口兼容、实际HTTP认证测试、静态资源打包、客户端错误状态、评测索引隔离和人工审核门槛。

执行起点为 M0。已完成项按实际证据勾选；未勾选项仍代表待人工审核、真实模型实验或发布前验证，不以代码存在替代 Gate 验收。
