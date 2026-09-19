# RAG-Forge 项目总审计报告

日期：2026-09-12

## 1. 项目总体情况

项目是一个 Python/FastAPI 本地 RAG 服务，技术栈为：Pydantic Settings 配置、Qdrant local/server 或 in-memory 向量存储、Ollama `bge-m3` 嵌入与 Gemma 生成、BM25 + RRF 混合检索、可选 CrossEncoder reranker、原生静态 Web UI、pytest 验证。

主要目录职责如下：

- `src/ragforge/`：领域模型、配置、摄取/分块、嵌入、向量存储、检索、生成、grounding、Trace 和 API。
- `scripts/`：数据获取、摄入、增量更新、重建索引、环境检查、评测、Windows 启停。
- `tests/`：离线单元测试、API/security/UI 测试和显式标记的 Ollama 集成测试。
- `data/raw`、`data/processed`：输入与已处理公开技术文档；`data/reports`：运行报告；Qdrant/SQLite 等状态数据保留，不做垃圾清理。
- `docs/`、`benchmarks/`：计划、阶段验收、Demo、候选/Golden Set 规则。

入口与流程已核实：FastAPI 入口为 `ragforge.api.main:app`；CLI 入口包括 `scripts.smoke`、`scripts.ingest_docs`、`scripts.update_knowledge`、`scripts.run_benchmark`；Windows 推荐入口为 `scripts/start.ps1`。主链路为：文档解析 → 标题感知分块 → embedding → 向量/BM25 索引 → dense/hybrid/RRF/可选 rerank → context 编码 → 生成 → Citation/拒答 → Trace。

当前完成度：M0–M8 已有实现和测试证据；M9 的评测基础设施、逐题 checkpoint 和身份门禁已落地，但人工 Golden Set 和正式生成质量实验未完成；M10 Windows 启停、依赖锁、Docker API 链路、完整 Compose 双服务聊天、332 文档/5,042 chunk 的当前 schema 2 候选索引与 Demo 材料已有证据。旧的 5,240 chunk 集合属于历史 schema 1 快照，已保留但不再按当前代码复用。当前总体验收仍受 M9 人工门槛和许可证核验限制。

## 2. 已修复/已实现问题

| 范围 | 修改与收益 |
|---|---|
| Citation/grounding | Evidence 先按 context 预算截断再编号；引用映射到实际发送的 chunk；越界/零引用/提示注入式内容触发拒答或明确状态。 |
| 拒答 | 区分无证据、低置信工程阈值、内容支持不足、模型声明不足；不把 raw reranker/RRF 分数当概率。 |
| Trace | 增加 TTL/cap/thread-safe store；保存 query 分工、候选、context、raw output、阶段耗时、模型和索引身份；普通日志不打问题全文。 |
| API/UI | API key 按路由保护；页面根路径保持可访问；模型/模式/Top-K 可见；DOM 安全渲染、URL 协议校验、loading/error/retry/AbortController/history。 |
| Query Rewrite | 默认 OFF；固定 `qwen3:0.6b` 只改写检索 query；原问题用于回答；空/超长/think/结构化/新数字/丢关键实体等回退并记录原因。 |
| 评测 | 增加按 document_id 去重的 Hit/Recall/MRR、Citation validity、拒答 confusion matrix、candidate/golden 校验、逐题证据 hash/摘要和独立实验输出；审核工具对长文优先定位候选答案附近的受限证据窗口。 |
| Windows | 增加自有 PID/启动时间/可执行文件/uvicorn 命令行校验，端口冲突保护，隐藏启动，readiness 超时和忽略的运行状态。 |
| 干净环境兼容性 | 修复可选重排器状态判断顺序；模型缓存和 `sentence_transformers` 包同时缺失时返回可诊断的组合原因，避免干净安装与污染环境表现不一致。 |
| Smoke 演示 | 将原本无法确定触发拒答的占位问题改为明确不存在的 `E9999` 查询，离线 smoke 现在验证正常回答与拒答两条路径。 |
| 采集与重建可控性 | sitemap 发现阶段遵守 `max_pages`，避免为上限之外的 URL 做无谓 DNS/IP 校验；采集与增量更新新增可选 `--max-seconds` 总时限；不可信 sitemap 使用 `defusedxml` 解析；环境探测只允许 HTTP(S)；重建索引按 embedding batch 分批写入并返回 batch 统计。 |
| 数据提交与索引身份 | 文档版本更新采用候选版本/验证/清理顺序，失败时保留旧有效版本；重建拒绝复用已有集合；manifest 记录 backend、embedding digest 和分块算法版本，benchmark/checkpoint 的 `corpus_identity` 单独记录语料 hash。 |
| 发布与运行边界 | Compose API 状态使用独立持久卷；请求体、Host、摄入总量和非 loopback key 有明确边界；Docker 按 Python 3.11 锁安装并以非 root 用户运行；浏览器和 Compose recreate 有可复现脚本；Windows 本地启动优先加载当前 `src/`。 |
| 评测可恢复性 | 生成实验支持逐题原子 checkpoint，恢复前校验 dataset/corpus/index/model identity；Ollama 生成可记录 temperature、num_predict、seed 和 timeout。 |
| 重建性能 | `scripts/reindex.py` 按 embedding batch 调用 `VectorStore.add_many()`，避免对 Qdrant 逐点发起数千次 upsert；新增回归测试锁定批量写入行为。 |

## 3. 已删除文件

没有删除任何项目文件、用户数据、数据库、migration、资源、配置或未提交源码。对疑似临时目录的删除尝试被执行安全策略拒绝，因此没有发生不可逆删除。

## 4. 保留的疑似无用/运行时文件

| 文件/目录 | 看起来无用的原因 | 保留原因 |
|---|---|---|
| `.playwright-cli/` | 浏览器验收产生的页面快照和 console 日志 | 已确认是验收产物，但本轮删除被安全策略拒绝；已加入 `.gitignore`，不进入版本库。 |
| `.pytest_cache/` | pytest 缓存 | 纯缓存，但删除被安全策略拒绝；已被 `.gitignore` 覆盖。 |
| `build/` | wheel/构建过程产物 | 非源码且已忽略；删除被安全策略拒绝，保留不影响运行。 |
| `data/run/` | 启停脚本的日志目录 | 由脚本有意保留用于诊断；PID 文件已在 stop 后清除，目录属于运行时状态。 |
| `docs/images/m7-debug.png` | 文件名像调试截图 | 它是 M7 验收证据，已在阶段报告中引用，不能删除。 |
| `data/reports/*.json` | 生成式报告文件 | 是 M6/M8/M9 增量验收证据，已忽略但有审计价值，保留。 |

## 5. 暂未修改的问题

### P0 严重

未发现已验证的 P0 问题。

### P1 高

- M9 还没有人工审核后的 100 条 Golden Set；当前 100 条全是 `candidate`，不能发布指标或代签审核。
- M9 真实 Gemma 双模型已完成 20 条候选样本采样，但不是人工审核 Golden Set；正式质量对比、完整样本和可发布结论仍未完成，当前结果明确标为 provisional。
- 受控断网的最小 API 主链路已通过；Windows/Python 3.14 的干净 `.[vector,dev]` 安装及 pip-tools 锁解析也已通过，`local` 与 `collector` 锁也已分别在独立环境安装并通过 `pip check`/关键模块导入；Docker/Python 3.11 CPU 锁已生成并在全新容器中按锁安装验证通过。完整 Compose 聊天已有独立验收；另以当前 schema 2 候选索引完成 332 文档/5,042 chunk 的本机 Qdrant hybrid 聊天验证，但人工 Golden Set 仍未完成，不能宣布项目整体完成。
- Docker 基础 server backend 与 Windows Docker Desktop + 宿主 Ollama override 已完成配置解析验证；当前 Dockerfile 已实际构建，完整 Qdrant+API Compose 使用临时宿主端口 16333/18002 完成 ingest → chat → Citation/Trace；宿主 Qdrant/Ollama 保持可用。当前 schema 2 候选索引保存在独立集合 `rag_forge_full_v2_20260912`，旧的 `rag_forge_full_20260912` schema 1 快照未删除、未复用，也未覆盖用户当前 `.env`。

### P2 中

- 候选题的生成方式是确定性 section summary，问题自然度、答案完整性和跨文档关系仍需人工审核；候选集已因语料从 116 扩充到 332 文档而重新生成，旧 provisional 输出不再代表当前 corpus。
- 当前 provisional deterministic embedding 结果不代表 bge-m3 质量；hybrid_rerank 候选实验因评测配置未启用 reranker 而没有有效指标，不能用 0 分解释为模型质量；本机 reranker 组件已单次实际运行，但正式 rerank benchmark 仍待 Golden Set/固定配置。
- 冷启动与预热后的真实性能已在当前 schema 2 候选 profile 拆分采集：hybrid 检索冷查询 4,667.907ms，30 次 warm p50=102.260ms、p95=118.043ms；Gemma 生成 3 次 p50=17,476.817ms、p95=17,587.678ms。结果见 `data/reports/performance-real-qdrant-v2-20260912.json`，仍是当前硬件/候选语料诊断，不替代 Golden Set 正式性能门槛。
- `benchmarks/golden.jsonl` 仍为空，尚不能执行 release profile 的全量正式 benchmark；不得用候选题、deterministic/offline 结果或旧报告代替人工审核。
- `pyproject.toml` 声明 MIT，但根目录尚无可核验的 `LICENSE` 文本；发布前必须由权利人补充或修正元数据。
- 已新增只读 `scripts/release_gate.py` 和单元测试；它会检查必需发布文件、许可证、完整 benchmark schema、100 条 reviewed Golden 及 20/80 冻结 split，并正确解析相对于 `--repo-root` 的自定义路径。针对当前候选集中 10 条 `unanswerable` 题合法无来源的情况，门禁要求字段格式正确但允许空 `source_refs`；可回答题仍必须有来源。当前实测为 `BLOCKED`，阻塞编号为 `license_missing`、`golden_empty`、`split_missing`，不会自动代填真实人审或许可证。
- 该脚本定位为发布输入完整性门禁，不替代 Docker/Compose、浏览器 E2E、安全边界、依赖漏洞审计和工作树范围复核；输入门禁通过也不能单独推出可发布结论。

### P3 低

- `.playwright-cli`、`.pytest_cache`、`build` 的物理删除仍需在允许安全删除时执行；当前已通过忽略规则避免污染 Git。
- 根目录 `output/playwright/` 重新枚举为空且无项目引用，已将 `output/` 加入 `.gitignore`；空目录未物理删除，避免触碰用户工作树。
- 本轮四个系统临时干净环境的递归删除同样被执行安全策略拒绝；其路径在项目外，未进入 Git，也未改变项目运行数据。
- 若直接调用未激活的系统 `python`（当前为 `C:\Users\MR\miniconda3\python.exe`），会因未安装项目包而使环境检查失败，并报告其自身的无关依赖冲突；项目 `.venv` 已通过环境检查、`pip check` 和测试，后续必须使用项目解释器运行命令。
- 本地 `.env` 中存在非空 `RAG_LLM_API_KEY`，属于运行配置而非仓库文件；已确认 `.env` 被 Git 忽略，并在源码、脚本、配置、文档、评测和运行报告等 148 个相关文件中检查到 0 个密钥字面量泄露。密钥值未读取到报告或回复中，若曾对外暴露仍应按常规轮换。
- 当前已在项目 `.venv` 使用固定版本 `ruff`、`coverage`、`build` 和 `pip-audit` 完成对应检查；尚未把这些质量工具声明为项目运行依赖，CI 通过固定安装保证版本一致。
- `.env.example` 的云端 key 已改成非 `sk-` 形式占位符，降低误报；真实 `.env` 仍只应保留在本地并继续被忽略。

## 6. 验证证据

- 全量 pytest：226 项收集，224 项通过、2 项跳过，退出码 0。
- 历史 M10 干净临时环境全量 pytest：162 项收集，160 项通过、2 项跳过，退出码 0；当前工作树的最新 `.venv` 回归见下方 226 项记录。
- `compileall src tests scripts`：退出码 0。
- 项目 `.venv` 与独立干净锁环境 `pip check`：均通过；未激活的系统 Miniconda `python` 不属于项目交付环境，不能用其结果判断项目依赖。
- Ruff 生产源码扩展规则（B/UP/FA/PIE/RET/SIM/ARG）与 `mypy src/ragforge --ignore-missing-imports --check-untyped-defs` 均通过；mypy 检查已接入 CI。
- Ruff 安全规则 `ruff check --select S src scripts` 通过；环境探测改用 `httpx` 并限制 HTTP(S)，sitemap 使用 `defusedxml`，生成器不再依赖可被 `python -O` 移除的运行时 `assert`。
- README、docs、benchmarks 和 requirements 的本地 Markdown 链接复核：35 个检查项全部有效；M4 历史报告的 3 个绝对路径链接已修正为相对路径。
- `node --check src/ragforge/api/static/app.js`：退出码 0。
- 敏感配置扫描：`.env` 中 `RAG_LLM_API_KEY` 非空但未被 Git 跟踪；148 个相关项目文件中未发现其字面量，未输出密钥内容。
- 六个 PowerShell 脚本 Windows PowerShell 语法解析：通过。
- M8 真实 `qwen3:0.6b`：20 条，关键实体保留 20/20，成功改写 4 条，安全回退 9 条，平均 ON 约 1874.842 ms。
- M9 provisional 候选集：100 条，类别分布符合 20/15/15/15/15/10/10；retrieval/generation/chunking 三个输出均保存；另有真实 Ollama 双模型 20 条采样，两个模型均 20/20 `ok`，仍标 provisional。
- M9 候选只读结构预审（当前 332 文档 corpus）：来源存在 100/100、文档 ID 合法 100/100、answerable 约束错误 0、重复问题 0；答案逐字匹配来源 21/90，仅作辅助信号，不替代人工语义审核。
- 本地组件集成：Ollama embedding、两种 Gemma 生成和 bge-reranker 单次实际重排均通过；Windows/Python 3.14 的 local 锁环境成功导入 Torch 2.14.0 CPU 与 Sentence Transformers 6.0.1；collector 锁环境成功导入 PyYAML 6.0.3 与 Trafilatura 2.2.0；当前有效文档 332、schema 2 候选索引 chunk 5,042，已达到 M10 的 300/3000 目标。
- Docker/Python 3.11 锁环境按 CPU wheel 源完成安装，`pip check` 通过，并成功导入 Torch 2.14.0+cpu、Sentence Transformers 6.0.1、Qdrant client 与项目包；未把 CUDA 依赖误写入容器锁。
- 受控断网最小主链路：进程级拒绝代理下，真实摄入 1 个文档并完成 `gemma3:4b` `/api/chat`，返回 1 条有效 Citation 后安全停止服务；另按当前 Dockerfile 构建并启动完整 Qdrant+API Compose，使用临时宿主端口和宿主 Ollama 完成 ingest → chat → Citation/Trace，随后删除专用容器、网络和卷。
- 采集先经 4 来源各 1 页小规模验证，再以 `--max-pages 100/150` 和 `--max-seconds 180/300` 分批运行；最终得到 401 raw 文件、332 个有效 processed 文档。采集报告记录 300 秒批次成功 294 页、仅 2 个时限错误；没有删除既有资料。新增总时限后，后续运行不会再无限等待。
- 全量重建使用 Ollama `bge-m3`、当前 `heading-window-v2` 分块算法和 schema 2 manifest 写入 Qdrant 独立集合 `rag_forge_full_v2_20260912`，结果为 5,042 chunks、候选查询校验通过；随后使用该集合完成真实 hybrid → Gemma → Citation/Trace 查询，返回 grounded=true、2 条 Citation。旧 schema 1 集合未删除、未复用，默认用户配置未自动切换。
- 默认配置一致性：当前 `.env` 为 `in_memory + local`，当前候选 manifest 为 `data/index_manifest_full_v2_20260912.json`，集合为 `rag_forge_full_v2_20260912`；身份匹配需显式提供相同 provider digest，用户默认配置尚未执行发布切换，而不是隐式降级。
- 当前候选 profile 的独立 API 验证：health=5,042 chunks、knowledge=332 documents、hybrid=5 hits；真实 `gemma3:4b` 返回 grounded=true、2 条有效引用、citation_invalid=false。未把 digest 缺失配置强行放行，临时 API 已停止。
- Windows 实际生命周期：start/readiness、status、重复 start、端口冲突、stop、无实例 status 通过。
- Qdrant：`ready=200`；现有 collections `rag_forge_m4_acceptance_v1`、`rag_forge_m4_ollama_v1` 未改变。
- 2026-09-13 复核：发布门禁仍报告 `license_missing`、`golden_empty`、`split_missing`；候选集统计确认 10 条 `unanswerable` 题合法为空来源，门禁已覆盖该边界。
- 生成 checkpoint 冒烟：同一 candidate/diagnostic 命令第二次运行报告 `resumed_counts` 为两个模型各 2，且 checkpoint 身份含语料、索引、模型与生成参数；不作为质量结论。
- Qdrant Server 当前按 `D:\Program Files\Qdrant Server\config\config.yaml` 运行，`127.0.0.1:6333/readyz` 返回 200；启动参数中的空格路径已用引号验证，三个既有集合均可恢复，未执行存储重置。

## 7. 后续优先级

1. 人工审核 100 条候选，冻结 calibration/test split，生成 `benchmarks/golden.jsonl`。
2. 用独立 index identity 运行 dense/hybrid/hybrid_rerank retrieval；具备模型时完成真实 reranker 校准。
3. 预热 Ollama 后运行真实 Gemma 生成实验，按 evidence hash 证明切模型不重复检索。
4. 将已验证的 `rag_forge_full_v2_20260912` 及其 schema 2 manifest 按发布窗口显式接入目标运行配置（当前未自动改写用户 `.env`），其他 Python/OS 锁仅在项目明确扩大支持矩阵时新增。
5. 最后再考虑物理删除已忽略的验收缓存；不得删除保留表中的数据、证据和用户未提交源码。
6. 由权利人确认许可证文本和第三方模型/依赖许可，再决定是否可以打包发布。

## 当前交付判断

代码与工程化主链路可继续使用，测试与阶段证据齐全；项目尚未达到“所有计划 Gate 完成”的最终交付条件。最小必需人工动作是审核候选题并冻结 Golden Set，之后才能把 provisional 结果升级为正式 benchmark。
