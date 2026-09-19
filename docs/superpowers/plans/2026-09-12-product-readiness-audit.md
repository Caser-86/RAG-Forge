# 项目综合审查与成品化实施计划

> **For agentic workers:** 后续按 TASK 顺序使用 superpowers:executing-plans 或 superpowers:subagent-driven-development 执行；本文件只交付第一阶段审查与规划，不授权发布、删除用户数据或提交现有全部改动。

**Goal:** 将 RAG-Forge 推进为 Windows 原生、本地优先、数据可靠、可复现验收的单用户技术资料问答产品。

**Architecture:** 保留 FastAPI 单体、原生 Web UI、Ollama、Qdrant、SQLite。先修正文档完整性和更新安全，再完善请求状态、评测、部署与用户操作闭环，不引入微服务、Agent 执行器或新前端框架。

**Tech Stack:** Python、FastAPI、Pydantic、NumPy、Qdrant、SQLite、Ollama、BM25、可选 CrossEncoder、原生 JavaScript/CSS/HTML、pytest、PowerShell、Docker。

**Spec:** 用户 2026-09-12 粘贴的综合审查要求，以及根目录 `RAG-Forge_本地RAG项目改造执行计划.md`。本次要求限定为“第一阶段：只进行完整项目审查和成品化规划”。

**Global Constraints:** 保留现有工作树；不删除文件；不修改业务代码、数据库、语料或密钥；不升级依赖；不将 Mock、离线回声、候选题或历史采样当成真实质量验收；Windows 本地优先，Docker 可选。

**审查日期：** 2026-09-12。**项目根目录：** `D:\LLM Files\files\N LLm\rag-forge`。下文代码位置均以该根目录为基准，行号对应本次审查快照。

**证据口径：** A＝本轮执行并复现；B＝本轮直接阅读代码或配置；H＝已有历史报告，未在本轮重新运行；U＝尚未验证。百分比为相对于本文件 DoD 的工程估计，不是覆盖率、准确率或任务勾选率。

---

# 1. 项目概述

项目是一套面向本地技术文档的 RAG 问答工作台。公开资料采集、清洗、版本记录、向量化、混合检索、生成、引用和 Trace 已有真实实现。它不是 Agent 平台，没有自动执行模型工具调用的业务需求。

当前成熟度判断：**MVP，向 Beta 收尾；不满足 Production Ready。** 整体成品准备度估计 **60%～65%**。已有工程骨架比 Demo 完整，但本轮发现正文丢失、更新回滚误删、容器重建持久化缺口及评测配置失真。此前“153/155 项任务已勾选”不能继续作为项目完成度结论。

本轮实际验证：

| 检查 | 结果 | 边界 |
|---|---|---|
| 项目 `.venv` 全量默认测试 | **160 passed, 2 skipped in 4.82s** | 默认跳过的两项需要 Ollama；本轮未重跑真实模型集成 |
| pip check | No broken requirements found | 不代表不存在已公开漏洞 |
| 分块覆盖诊断 | 300 个不同字符，4 个字符完全未进入分块 | 内存合成输入；未修改语料 |
| 同版本更新异常诊断 | 已有 1 个 chunk，注入清理异常后变为 0 | 内存 store；未修改真实 Qdrant |
| 清空会话诊断 | 清空后发送按钮 disabled=true，模型 disabled=false | Node 执行真实 app.js，模拟 DOM/fetch；非真实浏览器 E2E |
| 索引 digest 变化 | ensure_compatible 接受了不同 digest | 纯函数检查 |
| API 后端模型选择 | chat 默认仍为 gemma3:4b，而 generator 默认来自 llm_model | 纯配置/选择函数检查，无外部调用 |
| Git 状态 | 分支 codex/local-rag-m0；34 个 tracked 文件；123 条展开 dirty entries | 未暂存、提交、回滚 |
| 密钥模式扫描 | 107 个指定项目文件，0 个高信号模式候选；.env 当前和历史路径记录均未跟踪 | 不是所有秘密格式、所有历史 blob 的完整扫描 |
| 静态导入图 | 所扫描的相对模块导入图未发现环 | 不证明动态导入和包 re-export 不可能有环 |

本轮没有完成：真实浏览器全流程、冷启动计时、并发压力、覆盖率采集、联网 CVE 审计、全新机器安装、容器销毁重建。不能沿用历史 PASS 将这些项目写成本轮通过。

# 2. 当前技术栈

| 层 | 真实实现 | 判断 |
|---|---|---|
| 后端 | Python，FastAPI 同步路由，Pydantic v2 | 适合当前规模 |
| 配置 | pydantic-settings、.env、环境变量、少量 CLI 覆盖 | 集中配置合理；运行配置与示例已分叉 |
| 前端 | HTML/CSS/原生 JavaScript，FastAPI StaticFiles | 无 Node 构建依赖；无需迁移 React |
| 检索 | NumPy、rank-bm25、RRF、sentence-transformers CrossEncoder | 三种模式真实存在；重排为可选能力 |
| 嵌入 | Ollama、sentence-transformers、OpenAI 兼容、deterministic | 最后一种只适合测试 |
| 生成 | Ollama、OpenAI 兼容、offline 回声 | offline 明确为演示，不能算生成完成 |
| 向量存储 | Qdrant local/server、in-memory | 默认实际 .env 仍为 in_memory |
| 元数据 | SQLite knowledge manifest、JSON index manifest | 两份状态与 Qdrant 需要一致性保护 |
| 采集解析 | httpx、BeautifulSoup、PyYAML、trafilatura、pypdf | 无 OCR；扫描 PDF 不等于可解析 PDF |
| 测试部署 | pytest、PowerShell、setuptools、Docker Compose | 无仓库内 CI 工作流；锁文件未接入 Dockerfile |

依赖声明：11 个基础依赖；local 2、vector 1、data 1、dev 2、collector 2，共 8 个 extra 条目。开发测试依赖位于 dev，没有发现将 pytest 放在基础运行依赖中的情况。

依赖用途核对：FastAPI/Uvicorn 服务；Pydantic/settings/dotenv 配置；NumPy 向量；httpx 模型和采集通信；rank-bm25 稀疏检索；openai 云端兼容；pypdf PDF；bs4 HTML；sentence-transformers/torch 本地模型；qdrant-client 向量库；datasets 历史数据脚本；PyYAML 来源配置；trafilatura 正文抽取。没有足够证据支持删除其中任一依赖。BeautifulSoup 和 trafilatura 的角色有区别，不按“都解析 HTML”认定重复。

Python 声明为 >=3.10，历史锁覆盖 Windows 3.14 与 Docker 3.11；3.10 支持未形成新机器验收。锁文件存在不代表构建已经按锁安装。**当前版本是否存在 CVE、是否过期未联网核实，不作“全部安全/全部最新”结论。**

# 3. 项目目录与模块分析

```text
rag-forge/
├─ src/ragforge/              应用实现，30 个 Python 文件
│  ├─ api/main.py             生命周期、鉴权依赖、HTTP 路由
│  ├─ api/security.py         有界的进程内限流
│  ├─ api/static/             index.html、app.js、app.css、favicon.svg
│  ├─ config.py / models.py   配置及数据结构
│  ├─ pipeline.py             摄入、更新、检索生成与 Trace 编排
│  ├─ collector.py            受控网站采集与 robots/sitemap
│  ├─ knowledge_manifest.py   SQLite 状态、增量更新和恢复
│  ├─ index_manifest.py       索引身份与原子文件替换
│  ├─ ingest/                 文件解析、正文清洗、标题分块
│  ├─ embeddings.py           四种嵌入后端
│  ├─ vectorstore.py          内存/Qdrant 存储适配
│  ├─ retriever/              Dense/BM25/RRF/Rerank
│  ├─ generator.py            三种生成后端
│  ├─ grounding.py            context 预算、引用解析、拒答规则
│  ├─ query_rewriter.py       可选改写与失败回退
│  ├─ ollama_client.py        非流式模型 HTTP 协议
│  ├─ trace_store.py          内存 TTL/容量限制
│  ├─ evaluation/             数据集与指标
│  └─ observability/          文本日志与耗时
├─ scripts/                  采集/更新/重建/评测/Windows 启停
├─ tests/                    39 个 Python 文件，含 conftest 和 integration
├─ benchmarks/               100 条候选、空 Golden、审核说明
├─ configs/                  来源配置与实验配置
├─ requirements/             四种已记录平台的锁文件与说明
├─ docs/                     历史设计、阶段验收、图片及当前计划
├─ data/                     用户/运行数据，不可按垃圾清理
│  ├─ raw/web/               401 个原始文件
│  ├─ processed/web/         332 篇 Markdown
│  ├─ qdrant/                本地持久向量库
│  ├─ reports/               逐题评测与采集运行报告
│  └─ run/                   进程状态与运行日志
├─ Dockerfile / compose      可选容器部署
├─ .env                      用户配置，已忽略
└─ build/、.pytest_cache/     生成物；第一阶段保留
```

规模按物理行统计，包含注释和空行：src 的 Python/JS/CSS/HTML 共 33 文件、5,402 行；scripts 的 Python/PowerShell 共 15 文件、1,949 行；tests 共 39 文件、2,917 行；合计约 10,268 行。SVG 未计入行数。可按职责划分约 10 个主要模块。

最大源码文件：collector.py 620 行，knowledge_manifest.py 460 行，vectorstore.py 406 行，api/main.py 395 行。较长函数为 pipeline.ask 102 行、IncrementalUpdater.update 94 行、schema migration 67 行。规模尚不需要全面拆包。

资源加载：FastAPI 固定 static 目录；setuptools `api/static/*` 自动打包；README 引用 docs/images/m7-debug.png；采集来源由 YAML 驱动；文档及评测脚本使用 rglob 扫描；模型通过配置字符串、缓存路径和延迟 import 加载。没有发现插件注册/反射执行框架。因此资源和配置“没有直接 import”完全不能作为删除依据。

# 4. 当前架构

```text
浏览器 ──HTTP──> FastAPI / engine_lock ──> RAGForge
                                           ├─ QueryRewriter → Ollama
                                           ├─ Retriever → Embedder → Ollama/local/API
                                           │            ├─ Qdrant / InMemory
                                           │            ├─ 内存 BM25
                                           │            └─ 可选 CrossEncoder
                                           ├─ Generator → Ollama/API/offline
                                           ├─ Grounding → Citation/拒答
                                           └─ TraceStore（进程内、短期）

维护脚本 → Collector → Cleaner → IncrementalUpdater → RAGForge → Qdrant
                                      └─ SQLite         └─ JSON index manifest
```

主要状态：Qdrant 持久化 chunk；SQLite 保存来源/版本/任务；JSON 指向 active collection；BM25 是当前进程的索引快照；前端 history 仅页内；Trace 在内存中，最多 100 条、TTL 默认 1 小时。

当前合理边界是**单用户、单 API 进程、维护窗口更新**。不能在没有外部状态同步和权限隔离的情况下直接加多个 worker 或宣传多租户。

# 5. 当前完成度

评分基于“功能实现、异常恢复、自动验证、可复现交付”四方面综合判断，存在约 5～10 个百分点估计误差。

| 维度 | 估计 | 代码依据与扣分项 |
|---|---:|---|
| 产品 | 65% | 查询闭环存在；首次接入、保存结果和维护状态不完整 |
| 前端 | 70% | 真接口/错误/空态/Trace；清空缺陷，缺浏览器回归 |
| 后端 | 75% | 路由/验证/适配真实；锁范围、错误映射、资源关闭需处理 |
| 核心业务 | 65% | RAG 全链路实现；分块正文丢失直接影响正确性 |
| 数据层 | 60% | 持久存储/版本/manifest；回滚与部署重建安全不合格 |
| AI 能力 | 55% | 本地模型调用真实；无正式 Golden 质量结论 |
| 测试 | 60% | 160 项通过；关键异常漏测，无覆盖率/CI/持续 E2E |
| 安全 | 60% | 路径、API key、限流、文本输出；边界/请求体/依赖审计缺口 |
| 性能 | 45% | 批量嵌入、有耗时；逐点写入、全表计数、生成持全局锁 |
| UI/UX | 65% | 基本操作可理解；术语、状态、恢复和保存不足 |
| 部署 | 50% | Windows 脚本/Compose 存在；manifest 未持久化、构建未用锁 |
| 文档 | 65% | 内容丰富；命令缺 extra、旧阶段名和新状态混杂 |

等权平均约 61%；仅用于说明成品缺口规模，**发布结论由阻塞项和验收清单决定，不由平均分决定**。M3/M5/M7/M10 的旧 PASS 应解释为历史测试范围通过，本轮已发现范围外缺陷，不能继续泛化。

# 6. 已完成功能

- 真实文档解析、标题路径、chunk ID、Dense/BM25/RRF、可选重排。
- Ollama 生成、嵌入、模型列表、allowlist、模型错误分类。
- 引用编号映射、越界拒答、证据不足规则、可访问 Trace。
- 公开资料采集、robots/域名/IP 检查、响应大小与重试限制、正文清洗。
- SQLite 增量任务记录、部分失败恢复、版本和 active 状态。
- Qdrant local/server 及 metadata roundtrip，索引身份拒绝部分不兼容设置。
- Chat/Debug/Settings 原生页面；受控文本渲染、临时 key、重试。
- PowerShell 启停、PID 所有权检查、端口/readiness 检查。

“已实现”不等于“无缺陷”。OfflineGenerator 和 DeterministicEmbedder 有明确测试/演示用途，必须保留并明确标识，不当作无用代码。

# 7. 未完成功能

以下表格是本计划初始审查时的差距快照，不再单独代表当前实现状态；执行后的权威状态以本文末尾任务表和 `docs/reports/project-audit.md` 为准。

| 状态 | 项目 |
|---|---|
| 已完成 | 数据更新原子性、跨存储恢复、索引身份、防误覆盖 |
| 已完成 | 生成失败/取消/重试及超长历史的界面恢复 |
| 部分完成 | 正式评测：有 runner，没有 reviewed Golden 与真实检索配置门禁 |
| 部分完成 | 本地交付：脚本齐，但默认 .env 未接入持久化候选索引 |
| 工具已完成，等待人工 | 审核操作工具、审核进度保存、证据预览和 split 冻结流程；100 条真实人工审核仍未完成 |
| 已完成 | 用户结果导出、知识库状态与本地来源定位的操作闭环 |
| 已完成 | 仓库内持续集成、可重复浏览器 E2E、容器 API recreate 恢复测试 |
| 非当前需求 | 用户注册、RBAC、多租户、Agent Tool 执行、支付、微服务 |
| 可选 | 流式输出、长期会话列表、OCR、自动定时采集 |

未发现应当被视为“整个页面都是 Mock”的情况。UI 调用真实 API；测试替身与 offline 后端不应混淆。

# 8. Bug与风险

本节 F-01～F-22 是初始审查发现的编号化快照。执行阶段已经修复其中的代码问题；当前仍生效的风险、证据和发布状态以 `docs/reports/project-audit.md` 的“暂未修改的问题”和最终验收报告为准。

## P0：阻塞发布

**F-01 标题分块丢正文（A）。** `src/ragforge/ingest/chunker.py:88` 附近给后续 raw body 加 overlap 后使用 `body[:room]`，截断的尾部没有完整转移到之后的 chunk。内存输入 300 个不同汉字，size=100、overlap=20 时，原文位置 174、175、272、273 完全消失。会使某些事实永远不可检索。现有重复词测试无法识别丢失。修复后必须升级分块算法身份并重建候选索引；不能覆盖旧索引冒充等价。

**F-02 更新失败可删除已有效的数据（A/B）。** `pipeline.py:101–131` 的 catch 无条件删除目标版本。同版本重试注入 `delete_document_except_version` 异常，count 从 1 变 0。另一风险路径是旧版本已删后 BM25/Retriever 构建失败，再删除新版本，可能两版都没有。后者为控制流推导，未对真实库注入。修复须区分写入、验证、提交、清理，不能仅扩大 try/catch。

## P1：严重问题

**F-03 重建可写入已有集合（B）。** `scripts/reindex.py:42–49` 接受任意 `--collection`，QdrantStore 在同名集合存在时直接复用，写入在 count/查询验证之前发生。失败不代表原集合未改。必须要求候选集合不存在、且不同于 active collection。

**F-04 容器重建丢索引 manifest（B）。** `docker-compose.yml` 只持久化 qdrant_data；API 没有挂载 index_manifest 所在目录。`pipeline._validate_persistent_identity` 遇到非空库而无 manifest 会抛 LegacyIndexError。已有容器内重启或首次启动测试不能覆盖删除重建 API 容器。本轮未执行破坏性重建。

**F-05 评测无法证明真实检索质量（A/B）。** 两份 experiments 配置的 embedder 都是 deterministic；Ollama 版只换生成。`run_benchmark.py:99–123` 固定 in_memory、use_rerank=False，忽略 index.backend 与启用重排的意图。`provisional` 仅由候选审核状态决定；即使 Golden 全 reviewed，测试嵌入仍可能被标作非 provisional。需要独立 quality_eligible 门禁。此前直接用现有命令即可“正式验收”的说明不完整。

**F-06 清空会话后发送按钮残留禁用（A）。** `app.js:262–285` clear 增加 requestSerial，旧请求 finally 因 serial 不符跳过恢复；clear 自身未恢复按钮。Node 运行真实脚本已复现。Enter 处理走 requestSubmit，是否形成浏览器级完全不可发送还需真实浏览器回归；已确认的是按钮状态错误。

**F-07 长生成占用全局锁（B）。** `api/main.py:281` 的 engine_lock 包住整个 ask；health、query、Trace 也取同一锁。一次慢生成阻塞状态检查和其他请求。不能简单移除锁：generator.last_context_bundle/last_raw_output、rewriter.last_result、retriever.last_timings 是共享状态，需要先改成请求结果，再缩锁和加有界并发。

**F-08 默认运行尚未使用持久索引（A）。** 本轮有效 Settings 为 in_memory + local + Ollama，800/100；新进程不会自动获得此前另建 Qdrant 集合。用户容易把“服务启动成功”误认为知识库已加载。现有候选集合还必须先经 F-01 修复后的新算法重建，不能直接设为最终默认。

## P2：中等问题

- **F-09 模型身份不完整（A/B）**：`index_manifest.py:39` 不比较 embedding_digest；也缺显式 embedder_backend 和分块算法实现版本。不同 digest 被接受。相同字符串名/维度不保证同一模型内容。
- **F-10 API 生成后端路由不一致（A）**：api 模式 `/api/chat` 默认选 Gemma allowlist，而 LLMGenerator 默认使用 llm_model；云服务未必支持 Gemma。属于保留兼容入口的真实问题，不影响纯 Ollama 路径。
- **F-11 API 客户端关闭不完整（B）**：ApiEmbedder、LLMGenerator 没有 close；构造阶段在 try/finally 之前失败也可能泄漏已有资源。
- **F-12 状态检查全量扫描（B）**：QdrantStore.count 用 len(list_chunks())，分页取回全部 payload；health 调 len(store)，成本随语料增长。
- **F-13 文档重复摄入不等于替换（B）**：ingest_files→ingest_chunks 没有文档版本提交协议；同路径文档缩短后，旧的多余 chunk 可能保留。需补短文覆盖长文及 PDF 页数减少回归。
- **F-14 前端历史长度与接口不一致（B）**：HistoryMessage.content 最大 4000，模型输出未限制为 4000；前端原样 push 回 history，下一轮可能 422。requestJson 对数组 detail 直接转 Error，反馈难读。
- **F-15 context 证据边界（B）**：首 chunk 可被截断，但 bundle.evidences 保留完整原 chunk；insufficient_support_reason 检查完整原文，可能使用模型没看到的尾部内容。grounded=true 仅表示引用门禁通过，语义支撑始终 unverified。
- **F-16 构建依赖漂移（B）**：Dockerfile 未 COPY/安装锁文件，仍使用开放范围并独立安装 torch；锁文件验证不能约束实际镜像构建。
- **F-17 用户恢复闭环缺失（B）**：页内 history 刷新即失，Trace 短期保存；没有结果导出、源文档检视和新用户初始化闭环。
- **F-18 安全/采集边界（B/U）**：请求体总大小、Host 防护、同源安全头未见；采集 DNS 校验与实际连接为两次解析，流式读取未逐块检查总 deadline。见安全章节的适用前提。

## P3：优化项

- F-19 README 引导采集却没先安装 collector extra；M7 的“Query Rewrite 当前固定关闭”文案过时；旧 M1～M5 路线名与新 M0～M10 混用。
- F-20 日志是格式化文本，不是文档宣称的结构化 JSON；耗时日志未自动带 trace_id。
- F-21 `_to_evidence` 再算一次 RRF；Qdrant 解码 payload 重复；更新常重复创建 BM25/Retriever。
- F-22 Lint、类型检查、coverage、bandit、pip-audit 未安装；无版本化 CI。无独立 LICENSE 文件，尽管包声明 MIT；需确认版权来源后补齐授权文本。

# 9. 代码质量问题

优点：配置集中、主要模型有类型、协议错误分层、secret 比较使用 compare_digest、Trace 有容量和 TTL、检索分数语义有区分、optional 模型失败有显式状态。

问题集中于副作用和共享状态：数据提交与 BM25 重建耦合；部分恢复代码把失败当作可安全删除的凭据；API 路由重复映射返回值；生成结果的诊断数据依赖实例 last_*。这些比文件长几十行更值得先处理。

搜索 src/scripts/tests 的 TODO/FIXME/HACK 等未发现明确遗留业务待办标记；这不能证明没有未完成行为。抽象方法省略号是合法协议，不是占位业务。CLI print 是输出协议的一部分，不应按调试输出批量删除。安全回退捕获通用异常需记录异常类型和 trace，不能隐藏错误原因。

# 10. 架构问题

推荐继续采用现有单体，收紧三个边界：

1. **写入事务边界**：候选版本不可见 → 验证 → 激活 → 更新清单 → 延后回收；禁止在旧版不可恢复后无条件回滚新版。短期继续使用维护窗口，不引入分布式事务框架。
2. **请求状态边界**：retrieve/generate/rewrite 返回自己的诊断数据，Trace 从这些结果构造；避免共享 last_*。在此之前维持串行推理，不靠裸删锁提速。
3. **发布身份边界**：运行配置、模型 revision、chunk 算法、corpus snapshot、active collection 与 benchmark profile 有明确对应关系。

值得现在调整：上述三个边界，属于根因修复。暂不值得：拆微服务、统一事件总线、CQRS、通用插件系统、React 重写、多数据库抽象。主要风险是 public API/旧 manifest 兼容；采用新增字段、明确 schema 版本和候选索引切换，不静默复用。

# 11. 安全问题

按本地单用户产品界定威胁模型：本机用户信任；检索文档和模型输出不可信；采集来源配置由操作者维护；默认仅 loopback 暴露。不将“没有登录系统”直接列为漏洞，也不把共享 key 服务称为多租户。

| ID / 等级 | 位置及证据 | 影响与前提 | 修复/缓解及误报边界 |
|---|---|---|---|
| SEC-01 / P2 | main.py:68–80；空 api_key 放行，start.ps1 可传 HostAddress | 若改为非 loopback 且仍无 key，接口和 Trace 对可达者开放 | 非 loopback 启动 fail closed；默认 loopback 保留免登录；本轮未证明服务已对外暴露 |
| SEC-02 / P2 | main.py 请求模型只限制字段，未见 body middleware | 大 JSON 在字段验证之前消耗资源；/ingest 可一次处理 128×10MiB 文件 | 请求体 128KiB 上限、摄入批总量上限、并发 admission；数值为待实现发布策略 |
| SEC-03 / P2 | collector.py:556 校验 DNS；:496 仍按 URL 建连 | allowlist 域名解析可变或被控制时存在 DNS 重绑定窗口 | 固定/验证实际连接目标并保留 TLS 主机校验；本地可信官方源降低风险；未做攻击实测 |
| SEC-04 / P2 | collector.py:509 的 iter_bytes 无 deadline 检查 | 持续慢速小块响应可能超出总时限 | 每块检查 monotonic deadline；受控 transport 测试；不以普通 read timeout 替代总时限 |
| SEC-05 / P2 | grounding.py:149 起，support_status=unverified | 引用编号合法的捏造答案仍可能被显示为 grounded | 保留语义未验证标记；人工评测、恶意文档回归；不承诺 prompt 文本消灭注入 |
| SEC-06 / P3 | main.py 的 FastAPI 默认 docs；未见 CSP/Host middleware | 共享部署加大信息暴露和浏览器攻击面 | 本地 docs 可保留；共享 profile 限制 docs；同源 CSP/nosniff/防嵌入；边缘防护未验证 |

已见防护：SQLite 参数化 SQL；yaml.safe_load；摄入 resolve 后限定根目录、扩展名与单文件大小；前端 textContent、HTTP(S) 引用链接、key 仅页内；采集 HTTP(S)/凭据/私网/IP/重定向限制；模型 allowlist；没有执行模型输出的 eval/shell/Tool Call；未见 pickle 反序列化入口。

不适用或未证实：基于 cookie 的 CSRF（本项目使用 header key）、账号 IDOR（无用户资源所有权模型）、Agent Tool 滥用（无 Tool 执行器）。有共享部署需求时应重新审查，不能继承本地单用户结论。

密钥扫描范围内无高信号命中，未输出任何 key 值；不能证明历史提交、机器日志、所有外部仓库均无泄露。依赖漏洞状态尚未做实时数据库核验。

# 12. 性能问题

优先级从高到低：生成期间 health 被锁住；Qdrant count 全量 payload；逐 chunk HTTP upsert；每文档重建 BM25 和遍历 exists；Ollama 无输出 token 上限和本地请求整体预算；每次 chat 都请求模型列表。

采集和 reindex 已有批量 embedding，这是已有收益；store.upsert 仍单点，请勿把“批量嵌入”写成“批量数据库写入”。在 332 文档规模不建议先引入 Redis 或分布式向量检索。

本轮没有实测 p95、内存峰值和真实模型吞吐，不提供虚构数字。后续建议发布预算：health p95≤500ms、纯检索暖机 p95≤2s、默认模型完整回答 p95≤120s、超预算有明确超时反馈；全部在指定硬件及固定索引上验证。如果 CPU 达不到生成预算，选更合适的默认模型或缩短上下文，不能只调宽标准隐藏问题。

# 13. UI/UX问题

页面有实际 Chat/Debug/Settings、loading、empty state、错误与重试、手机宽度媒体查询、减少动画媒体查询。整体不需要视觉重做。

影响使用的具体问题：清空按钮状态；0 chunks 仍显示 READY；缺少可操作的初始化说明；不可用 rerank 仍可选；改写固定关闭文案错误；错误原因英文码直接展示；API key 失败缺清晰定位；历史刷新消失；本地来源缺正文预览；Trace 请求失败与回答错误混在一起；输入框 outline:0 的焦点可见性需要实际检查。

还需真实浏览器验证：中文输入法 Enter、键盘焦点、Tab 语义、200% 缩放、320/375/768/1440 宽度、色彩对比、长标题和长答案。当前仅代码审查和模拟 DOM，不宣称可访问性合格。固定深色主题可作为 v1 产品选择，主题切换不是发布必需。

# 14. 测试问题

已有测试覆盖向量、元数据、配置、Ollama HTTP、检索模式、引用、拒答、rewrite、采集、incremental、API key、路径、Trace、Windows 脚本。TestClient 并不等于浏览器测试；test_web_ui 的文本存在断言不能验证清空期间的异步状态。

必须新增的高价值回归：分块每个原文字符/段落覆盖；更新各阶段故障和同版本重试；已有集合重建拒绝；容器 recreate；生成阻塞时 health；超长历史下一轮；真实索引 profile；未审核/过期 corpus/测试嵌入禁止正式成绩。

代码覆盖率 **未知**，不能用 160 个测试推算百分比。计划引入 branch coverage，先记录基线，再设 touched 核心模块≥85% 的目标并优先覆盖异常分支；不以无意义断言冲覆盖率。

# 15. 文档问题

README 包含安装、API、模型与评测，但存在：采集前未安装 collector；Copy-Item .env.example .env 未提醒保护已有配置；默认 Docker 为云 API 且依赖个人缓存路径；“权威评测用 RAGAS”措辞夸大，模型裁判仍须校准；历史 20 条采样没有在所有入口一致强调旧 corpus；阶段报告 PASS 未反映新发现。

缺少集中开发指南、支持矩阵、逐字段配置表、备份恢复演练、正式发布步骤、用户常见错误和 Golden 人工审核工具说明。下一轮按任务补充，历史报告保留并标明被新证据补充，不能删历史设计来减少文件数。

# 16. 可删除/疑似无用文件

**本轮删除数：0。** 用户明确限定第一阶段不删除。

| 文件/目录 | 分类 | 判断与证据 | 后续条件 |
|---|---|---|---|
| .pytest_cache/，5 文件 | 可以安全删除的缓存候选 | pytest 缓存，被忽略 | 下一阶段确认无测试在运行再处理 |
| build/，32 文件 | 建议删除的构建产物候选 | 构建输出目录，被忽略 | 对照源码/打包引用，确认无独有用户产物 |
| .playwright-cli/，24 文件 | 需要确认 | 可含验收截图和操作证据 | 确認报告引用与历史审计价值后决定 |
| output/，0 文件 | 可清理空目录候选 | 2026-09-13 复核仍为空且无项目引用；已加入 `.gitignore` | 不物理删除空目录，避免扩大删除范围 |
| data/reports/ | 必须保留 | 逐题评测、采集状态与验收证据 | 只有明确保留策略后才归档 |
| data/raw、processed、qdrant、manifest | 必须保留 | 用户知识库、索引、版本状态 | 不属于垃圾 |
| benchmarks/golden.jsonl | 必须保留 | 1 字节、0 条数据，但代表待完成门禁 | 空文件不等于无用 |
| scripts/run_eval.py、fetch_data.py | 必须保留 | README 仍引用历史 MLQA 工作流 | 删除需明确废止兼容并更新文档测试 |
| INTERVIEW_GUIDE.md、阶段报告、旧计划 | 需要确认/保留 | 历史设计和项目用途资料 | 由内容价值和替代方案决定 |
| docs/images/m7-debug.png | 必须保留 | README 明确引用，514671 bytes | 不按旧截图直接删除 |
| api/static/* | 必须保留 | StaticFiles 和 package-data 自动加载 | 静态资源全局生效 |

对所枚举的 src/scripts/tests/docs/benchmarks/configs/requirements 非空非 JSONL 文件做 SHA256 重复分组，没有输出完全重复组；未把 raw 语料、模型、虚拟环境和数据库纳入“可删重复文件”判断。当前未发现有足够证据确认废弃的业务模块。

# 17. 技术债

| 债务 | 收益优先级 | 处理边界 |
|---|---|---|
| 分块/版本/提交协议缺少不变量 | 最高 | TASK-002～005 |
| 请求 last_* 共享诊断状态 | 高 | TASK-008；无须重写整个 pipeline |
| 多套配置口径漂移 | 高 | TASK-010、012、019 |
| 评测工具能运行但不能验产品质量 | 高 | TASK-012～015 |
| 无可重复异常 E2E/CI | 高 | TASK-019～020 |
| 文档维护多源 | 中 | 保留历史，增加单一当前发布页 |
| 重复几行返回值/RRF计算 | 低 | 涉及文件因其他任务修改时再整理 |

# 18. 成品必须补齐的能力

**必须完成：** 数据不丢、失败不误删、已有集合不被重建覆盖、运行和索引身份匹配、Docker recreate 可恢复、问答取消/重试正常、持久化配置可验证、正式质量门禁、人工审核工具及真实审核、结果保存、最小安全边界、可复现安装和核心 E2E。

**强烈建议：** 连接释放与带 trace 的错误日志、采集 deadline/DNS 防御、Qdrant 原生计数/批量写、定量性能预算、持续质量工具。

**可选优化：** 流式输出、长期会话列表、主题切换、OCR、自动定时采集、更细模块拆分、缓存物理清理。缺少这些不阻止本地 v1 成品。

# 19. Definition of Done

只有以下所有必需门禁有可复查证据，才可称“本地 v1 完成”：

1. F-01/F-02 及所有 P1 已修复；每项有能复现原问题的回归测试。
2. 真实 corpus 的正文分块覆盖检查通过；算法身份升级；新集合验证后切换，旧集合保留为回滚目标。
3. 各个更新阶段失败均不导致原有效文档丢失；重复运行结果一致；缩短/删除页不残留旧 chunk。
4. Windows 按文档在干净环境完成安装、初始化、问答、停止、重启、再次查询；无需云 API key。
5. Docker 路径若对外声明支持，必须通过 API 容器销毁重建和数据恢复测试，而不仅是 restart。
6. Chat/清空/重试/断网/模型缺失/空库/无权限/非法输入/超长答案下一轮均有清晰结果；页面刷新后的会话策略明确，结果可导出。
7. 100 条人工 reviewed 题，审核人和时间真实，证据可追溯；split 在调参前冻结，无重复泄漏。
8. 正式检索使用真实 bge-m3；生成使用真实默认模型；重排若宣称支持则有真实对比；测试嵌入/offline 不能得到 quality_eligible=true。
9. 基准记录 corpus、模型 revision、索引配置、生成参数、硬件、逐题输出、失败与超时；阈值在最终 test 运行前冻结。
10. 建议质量门槛：Hit@5≥0.80、Recall@5≥0.75、不可回答题拒答召回≥0.90、可回答题误拒答≤0.20；最终回答引用编号有效率100%；人工正确且被证据支持比例≥0.80。该组数值是本计划提出的产品目标，尚未达到，不是历史实测结论；100题样本仍需报告分母和不确定性。
11. 全部默认测试、真实 Ollama 集成、核心浏览器 E2E 通过；跳过和适用平台明确；新机器 wheel 包含静态资源。
12. 发布配置仅 loopback 或非 loopback 强制认证；secret 检查/依赖审计完成；未解决漏洞逐项评估，不将 scan 未运行记 PASS。
13. 备份包含语料、SQLite、index manifest 与匹配 Qdrant 快照；在独立目录恢复后能查询。
14. README 命令完整，支持平台边界准确，LICENSE/第三方许可清晰，发布文件清单包含目前未跟踪的必需实现。

# 20. 成品化路线图

| 阶段 | 目标 | 任务 | 进入下一阶段的条件 |
|---|---|---|---|
| Phase 0 | 当前证据与边界 | 001 | 基线、范围和回归结果落盘 |
| Phase 1 | 修复数据正确性 | 002–005 | 分块无丢失，更新/重建失败安全 |
| Phase 2 | 完成运行与交互 | 006–011 | 持久化、模型、请求状态、用户流程可用 |
| Phase 3 | 形成可信质量证据 | 012–015 | 正式 profile、人工审核、真实评测通过 |
| Phase 4 | 安全与交付硬化 | 016–022 | 安全、CI、E2E、性能、文档与恢复达标 |
| Phase 5 | 收尾与验收 | 023–024 | 必需门禁逐项有证据，发布包可复现 |

不执行 13 个空泛阶段。安全和回归测试随每个任务做，Phase 4 负责统一门禁，不把安全拖到最后才考虑。

# 21. TASK任务列表

以下“涉及文件”是预期修改范围，不授权顺便格式化其他文件。新文件明确标“新增”。每任务独立验证，失败先解决再进入依赖任务。完成只填写本轮真实测试证据，不自动 commit 用户的既有修改。

## TASK-001：冻结审查基线

- 问题/目标：过去的里程碑勾选不能说明成品状态；保存当前代码规模、缺陷证据与保护范围。
- 涉及文件：本计划；只读检查 Git、配置、src/scripts/tests。
- 方案/步骤：检查分支与展开状态 → 执行现有测试/pip check → 隔离诊断 → 写入当前报告。
- 依赖：无。优先级 P1；复杂度 S；类别必须；状态：本轮完成。
- 风险：把历史 PASS 当新证据；已用 A/B/H/U 区分。
- 验证/验收：160 passed/2 skipped；三个缺陷可复现；无业务代码或数据修改。

## TASK-002：修复标题分块正文丢失

- 问题：F-01；目标是正文无遗漏、顺序可追踪、重叠有界。
- 涉及文件：`src/ragforge/ingest/chunker.py`、`tests/test_heading_chunker.py`。
- 方案：以原文游标推进窗口，先为标题和 overlap 预留容量；不能将截断 body 丢弃。记录正文起止偏移，跨标题不重叠。
- 步骤：增加唯一字符回归 → 测试失败 → 重写 pack/overlap 边界 → 覆盖超长标题、代码块、连续长段、overlap 接近 size → 跑 ingest/retrieval 回归。
- 核心回归内容：
  ```python
  text = ''.join(chr(0x4e00 + i) for i in range(300))
  chunks = Chunker(100, 20, 'heading_chars').chunk(Document(id='d', title='d', text=text))
  assert all(any(char in chunk.text for chunk in chunks) for char in text)
  ```
- 依赖：001。优先级 P0；复杂度 M；类别必须。
- 风险：结果内容变化；不得直接覆盖现有索引，交 TASK-005 标识新算法。
- 验证：`python -m pytest tests/test_heading_chunker.py tests/test_ingest.py tests/test_retrieval_modes.py`。
- 验收：唯一字符覆盖100%；无非空正文缺失；标题/代码顺序保持；所有现有相关测试通过。

## TASK-003：建立失败安全的文档版本提交

- 问题：F-02/F-13；目标是更新重试不误删旧有效版本，缩短文档无旧片段。
- 涉及文件：`pipeline.py`、`vectorstore.py`、`knowledge_manifest.py`、`tests/test_incremental_update.py`、`tests/test_pipeline.py`、`tests/test_store_lifecycle.py`。
- 方案：同版本/同内容幂等；新版本写入期间 inactive，验证后激活；提交后清理失败记录待清理任务而不是删除新版本；发布窗口串行维护。统一文件摄入与来源增量的替换语义。
- 步骤：分别注入 encode/upsert/验证/激活/SQLite记录/BM25重建/旧版清理失败 → 明确提交点 → 按提交前后采取不同恢复 → 同版本重试 → 长文缩短/PDF页数减少测试。
- 依赖：002。优先级 P0；复杂度 L；类别必须。
- 风险：跨存储无法天然事务；保留旧版本直到新版本及状态可恢复，清理不作为可用性前提。
- 验证：在 tmp_path 的 local Qdrant 和内存库运行故障注入；不使用当前数据目录。
- 验收：任意故障后至少一个已提交有效版本可检索；再次执行收敛；没有重复有效版本/残留过期页；同版本故障 count 不从1变0。

## TASK-004：禁止重建复用已有集合

- 问题：F-03；目标是在第一次写入之前拒绝危险目标。
- 涉及文件：`scripts/reindex.py`、`vectorstore.py`、`tests/test_reindex.py`。
- 方案：添加“必须新建”存储入口；检查当前 manifest 的 active 名称；命名冲突直接失败；不采用先查询再默认 upsert 的弱保护。
- 步骤：已有 active/非active 集合各写入测试数据 → 指定同名重建 → 断言任何 upsert 未发生 → 新集合正常流程 → 注入中途失败并检查 manifest 不变。
- 依赖：003。优先级 P1；复杂度 M；类别必须。
- 风险：同名恢复流程改为显式新名字；CLI 给出提示，禁止默认“覆盖恢复”。
- 验证：`python -m pytest tests/test_reindex.py tests/test_qdrant_persistence.py`。
- 验收：已有集合内容 hash/count不变；新候选验收成功才切换；失败候选保留且报告其名称。

## TASK-005：升级索引身份并建立候选切换清单

- 问题：F-09及分块修复后的身份变化；目标是不静默复用不兼容索引。
- 涉及文件：`index_manifest.py`、`pipeline.py`、`scripts/reindex.py`、`tests/test_index_identity.py`；新增 `docs/INDEX-MIGRATION.md`。
- 方案：schema 新版本包含 embedder_backend、实际模型 revision/digest、chunk_algorithm_version、现有chunk参数、tokenizer；采集/文件/benchmark doc ID 给出明确映射；语料 hash 作为独立快照证据记录在 benchmark/checkpoint 中。
- 步骤：增加 backend/digest/algorithm 不同必拒测试 → 获取并保存模型真实身份 → 明确旧 manifest 只允许旧版本回滚或要求重建 → 新候选验证 → 生成“旧→新”切换/回滚记录。
- 依赖：002、004。优先级 P1；复杂度 M；类别必须。
- 风险：旧索引被拒用；保留旧程序配置和集合，不自动删除。
- 验证：不同 digest 的纯函数用例应从接受变为拒绝；旧 manifest 路径有明确错误；候选重建回归通过。
- 验收：模型或分块语义改变必触发不兼容；文档 ID 映射可追溯；manifest 原子写入保留。

## TASK-006：持久化容器 API 状态并验收 recreate

- 问题：F-04；目标是重建 API 容器不丢索引身份。
- 涉及文件：`docker-compose.yml`、`docker-compose.ollama.yml`、`Dockerfile`；新增 `scripts/verify_compose_recovery.ps1`。
- 方案：为 API index manifest/必要 SQLite 指定独立可写持久目录；Qdrant volume 保留；原始文档只读；基础 profile 优先本地，云端兼容单列。
- 步骤：配置绝对容器状态路径 → 建立独立 compose project/临时宿主端口 → 摄入合成文档 → 强制重建仅该 API 容器 → 同一问题查询 → 记录集合/manifest一致性。
- 依赖：005。优先级 P1；复杂度 M；类别必须（保留Docker支持时）。
- 风险：误操作默认容器；脚本必须固定验收 project 名，禁止使用现有生产 volume。
- 验证：compose config + recreate 回归；不是仅 restart。
- 验收：容器删除重建后chunk数/模型身份/文档内容不变；不出现 LegacyIndexError；测试隔离项目可安全结束。

## TASK-007：统一保留的云端兼容模型路由

- 问题：F-10；目标是 /ask 和 /api/chat 在 api 后端遵守同一模型配置。
- 涉及文件：`api/main.py`、`config.py`、`generator.py`、`tests/test_api_models.py`、`tests/test_model_switching.py`。
- 方案：按 generation_backend 建立模型目录；api profile 的默认来自 llm_model，并保留显式 allowlist 校验；不实际调用付费API。
- 步骤：Mock OpenAI 请求捕获 model → 验证默认/允许切换/禁止未知模型 → 区分 Ollama 安装检查 → UI目录展示一致。
- 依赖：001。优先级 P2；复杂度 S；类别必须（保留兼容接口时）。
- 风险：旧配置字段兼容；保留已有名字并说明语义。
- 验证：相关 API/model tests，云端调用以 transport 替身验证请求参数。
- 验收：默认请求不意外发送 gemma3:4b 到配置的其他服务；Ollama行为不变。

## TASK-008：隔离请求状态并让健康检查及时返回

- 问题：F-07；目标是慢推理不阻塞健康/Trace，模型输出不串请求。
- 涉及文件：`pipeline.py`、`generator.py`、`query_rewriter.py`、`retriever/search.py`、`api/main.py`、`tests/test_traces.py`、`tests/test_api.py`。
- 方案：新增请求结果结构携带 context/raw/timings；消除 pipeline 对共享 last_* 的依赖；初版推理并发固定1，忙时有界等待或503；状态路由不占推理锁；写入仍互斥。
- 步骤：用 Event 阻塞假生成器 → 并发 health/Trace → 建立请求结果 → 调整锁范围 → 两个不同模型/问题验证 trace对应 → 测试关闭期间请求。
- 依赖：003、007。优先级 P1；复杂度 L；类别必须。
- 风险：裸移锁会串上下文；先改结果结构，再改锁，保留 API 返回字段。
- 验证：并发测试用 Event/Barrier，避免只靠 sleep；完整 pipeline/trace/model tests。
- 验收：生成未完成时 health≤500ms；忙碌请求得到规定状态；引用、模型、raw output 不串台。

## TASK-009：修复清空、重试、超长历史和输入法交互

- 问题：F-06/F-14；目标是任何请求终态后用户都能继续提问。
- 涉及文件：`api/static/app.js`、`index.html`、`app.css`；新增 `tests/browser/chat-state.spec.js`。
- 方案：单一 resetRequestState 恢复 controller/button；清空重置 trace/lastQuery；规范化 422 detail；历史发送前按合同裁剪并标记；中文输入 composition 不触发发送。
- 步骤：复现请求中清空 → 修复 finally/serial → 连续清空和重试 → 5000字符回答后的下一问 → 错误数组展示 → 中文输入法和Enter/Shift+Enter验证。
- 依赖：008。优先级 P1；复杂度 M；类别必须。
- 风险：客户端取消不保证服务端停止推理，UI要说明并与 admission 配合。
- 验证：真实浏览器断言 `await expect(page.locator('#sendButton')).toBeEnabled()`；旧回答不得回填新会话。
- 验收：清空后按钮恢复；下一问可提交；长答案不引发不可理解422；模型错误可重试。

## TASK-010：提供可验证的本地发布 profile

- 问题：F-08；目标是从实际配置知道“运行哪个知识库”。
- 涉及文件：`config.py`、`scripts/check_environment.py`、`scripts/start.ps1`、`.env.example`；新增 `docs/LOCAL-SETUP.md`。
- 方案：环境检查输出后端、active collection、manifest匹配、活跃chunk、模型安装状态；不输出密钥；非测试 profile 禁止无提示 in_memory；明确旧 .env 和新 profile差异。
- 步骤：输出脱敏配置 diff → 针对新算法创建候选集合 → 核验真实 embedding/chat → 生成具体切换/回滚内容 → 发布窗口应用明确目标配置 → 启停重启验证。
- 依赖：005、008。优先级 P1；复杂度 M；类别必须。
- 风险：已有用户配置被覆盖；不直接 Copy-Item 覆盖 .env；保留回滚副本与新旧配置说明。
- 验证：只读 doctor + 两次进程启动查询；空库单独返回 empty状态。
- 验收：新进程加载正确持久化集合；不把0 chunks显示为就绪知识库；无需云API key。

## TASK-011：补齐来源定位、初始化指引和结果导出

- 问题：F-17及首次使用断点；目标是用户能找到证据、保存结果并再次查看。
- 涉及文件：`api/main.py`、`api/static/*`、`tests/test_api.py`、`tests/browser/`；新增只读知识库状态响应模型。
- 方案：页面展示知识库名称/活跃文档/更新时间；空库给出维护入口说明；来源通过受限 document ID映射预览，不接收任意文件路径；导出本次问答+引用为 Markdown/JSON，排除 key 和默认 raw Trace。
- 步骤：定义只读状态/来源接口 → 测试未知ID与越权路径拒绝 → UI显示初始化步骤 → 本地下载结果 → 新页面离线打开导出检查引用。
- 依赖：009、010、016。优先级 P2；复杂度 M；类别必须。
- 风险：调试信息泄露；导出默认不含完整上下文，额外诊断明确选择。
- 验证：API schema测试及浏览器下载文件内容检查。
- 验收：用户能定位至少一个实际支持文档、保存结果；刷新丢失页内会话前有明确策略说明。长期会话数据库另列可选。

## TASK-012：建立严格的真实评测配置与准入门禁

- 问题：F-05；目标是正式成绩不会由测试后端或忽略配置产生。
- 涉及文件：`scripts/run_benchmark.py`、`evaluation/benchmark.py`、`configs/experiments*.yaml`、`tests/test_benchmark.py`；新增 `configs/experiments-release.yaml`。
- 方案：区分 diagnostic 与 release；真实 bge-m3 profile显式启用重排；配置字段要么应用要么报错；诊断允许 in_memory真实向量，但Qdrant端到端性能单独验。正式门禁检查非空reviewed、corpus快照、split、真实模型和实际参数。
- 步骤：添加 reviewed+deterministic 不可quality_eligible测试 → 读取/验证 index与rerank配置 → 保存模型revision和生效参数 → 验证过期corpus/伪时间/空答案 → release拒绝limit采样冒充全量。
- 依赖：005、008。优先级 P1；复杂度 M；类别必须。
- 风险：旧报告schema消费者；保留旧字段，新增 eligibility/reasons/profile字段。
- 验证：`python -m pytest tests/test_benchmark.py tests/test_metrics.py`；release dry validation不能访问付费服务。
- 验收：deterministic/offline永不具有真实质量资格；请求重排时确实调用重排或失败；无静默忽略配置。

## TASK-013：提供人工审核工具并冻结 Golden Set

- 问题：100题JSONL约901KB，手工修改复杂且易伪签；目标是低负担真实审核。
- 涉及文件：新增 `scripts/review_benchmark.py`、`tests/test_benchmark_review.py`；`benchmarks/README.md`；生成独立审核进度文件与最终golden/split。
- 方案：标准库本地审阅工具逐题显示问题、答案、source_refs；允许接受/改写/拒绝/暂缓；保存决策、真实审核人、UTC时间；只导出已接受题，绝不自动写 reviewed。
- 步骤：验证source_refs限定语料根 → 导出易读审阅材料 → 人工逐题决策 → 中断恢复 → 替换拒绝题直到100 → 按类别分层冻结20校准/80测试（建议方案），近重复题成组划分 → 记录split hash。
- 依赖：012。优先级 P1；复杂度 M；类别必须。
- 风险：自动化不能替代真实人的语义认可；此环节需要用户实际审核动作，不可冒签。
- 验证：工具测试用虚构审核记录；真实数据仅在用户逐题操作后导出。
- 验收：100题已审核；每题可见证据；未确认题不能进入Golden；split无重复且不可被后续调参默改。

## TASK-014：运行可恢复的真实模型基准

- 问题：旧116文档20题样本不能证明当前质量；长任务中断可能丢结果。
- 涉及文件：`scripts/run_benchmark.py`、`ollama_client.py`、`config.py`、`tests/test_benchmark.py`、`docs/reports/M9-benchmark.md`。
- 方案：逐题checkpoint，恢复时验证全部身份；显式生成temperature/seed（支持时）/num_predict/timeout并记录实际值；同一证据缓存对比模型；单个默认模型先完成全量，次模型对比独立报告。
- 步骤：测试中断/恢复 → 接入生成参数 → 在校准集定阈值 → 冻结参数 → 运行最终集检索三模式/分块/生成 → 人工评答案事实与引用 → 汇总失败分母和性能。
- 依赖：012、013、015、021。优先级 P1；复杂度 L；类别必须。
- 风险：CPU耗时；先估算单题耗时并写checkpoint，不悄悄减题数或忽略超时。
- 验证：重启runner不重复已完成身份一致题；证据fingerprint在双模型间一致。
- 验收：DoD质量门槛达到或如实记录未达并继续修正；不能把代理忠实度当人工准确率。

## TASK-015：让引用检查仅使用实际发送的证据

- 问题：F-15/SEC-05；目标是正文裁剪与支撑检查使用同一份内容。
- 涉及文件：`grounding.py`、`generator.py`、`models.py`、`tests/test_citations.py`、`tests/test_refusal.py`；新增恶意文档fixture。
- 方案：ContextBundle保存实际已发送片段及对应引用范围；数值约束检查只看这些片段；UI表述“引用编号已校验，事实支撑未审核”；原API字段兼容但文档说明含义。
- 步骤：尾部独有错误码被裁掉测试 → 多chunk预算测试 → 引用越界/缺失 → 恶意文档要求忽略规则/伪造引用/泄露提示回归 → 人工语义评分表。
- 依赖：002、008。优先级 P1；复杂度 M；类别必须。
- 风险：误拒答增加；在校准集分析原因，不能通过宽松规则隐藏。
- 验证：仅原文尾部有事实而模型上下文无该事实时不可通过支撑门禁；context长度不超预算。
- 验收：引用可定位实际发送内容；语义未验证标志准确；没有工具执行能力被无意引入。

## TASK-016：明确本地API安全边界

- 问题：SEC-01/02/06；目标是安全默认值和可解释的拒绝。
- 涉及文件：`api/security.py`、`api/main.py`、`config.py`、`scripts/start.ps1`、`tests/test_api_security.py`。
- 方案：本地profile loopback；非loopback强制key；在读取请求body时实施128KiB上限并检查分块传输；ingest批总量默认32MiB；同源CSP/防嵌入/nosniff；Trace鉴权不遗漏。
- 步骤：无Content-Length的大body测试 → 超总量文件请求 → 错key和Unicode key → 非loopback空key启动拒绝 → 受限Host及静态页面headers → 旧接口兼容。
- 依赖：001。优先级 P2；复杂度 M；类别必须。
- 风险：限制误伤合法请求；数值可配置，有明确413/401/429反馈，不加无需求账号系统。
- 验证：已有及新增安全测试；敏感信息仅断言未出现，不输出真实值。
- 验收：body/路径/总量/鉴权边界均可测试；本地免登录可用；不宣称多租户隔离。

## TASK-017：验证采集deadline与网络目的地

- 问题：SEC-03/04；目标是慢流不能绕过总预算，DNS检查与连接一致。
- 涉及文件：`collector.py`、`tests/test_collector.py`、`configs/sources.yaml`。
- 方案：每个响应块检查deadline；连接前后目的地址保持受控并保留TLS主机校验；限制代理环境对目的地校验的影响。若不能可靠实现DNS固定，明确可信来源边界和出网限制，保留未完成状态。
- 步骤：模拟连续小块时间推进 → 超预算终止 → 重定向到私网 → DNS前后变化 → robots/重试/压缩/响应大小回归。
- 依赖：016。优先级 P2；复杂度 M；类别强烈建议。
- 风险：TLS/SNI和代理兼容；不采用verify=False解决问题。
- 验证：自定义httpx transport与虚拟clock，不攻击真实站点。
- 验收：总预算可终止持续响应；私网目的地不可达；不完整枚举不触发误失活。

## TASK-018：关闭所有客户端并补充可定位错误日志

- 问题：F-11/F-20；目标是资源生命周期完整且日志可按trace定位。
- 涉及文件：`embeddings.py`、`generator.py`、`pipeline.py`、`observability/logging.py`、`tests/test_store_lifecycle.py`、`tests/test_traces.py`。
- 方案：ApiEmbedder/LLMGenerator close幂等；构造期间ExitStack清理；日志字段trace_id/stage/error_type，不默认记录query/context/key。
- 步骤：构造第N资源失败测试 → 全资源关闭一次 → 请求失败产生trace_id和类型 → 检查日志不包含合成secret → Windows编码输出回归。
- 依赖：008。优先级 P2；复杂度 M；类别必须（资源关闭）；日志格式扩展为强烈建议。
- 风险：关闭异常遮蔽原异常；优先保留原失败并单独记录清理失败。
- 验证：客户端替身close计数、初始化故障注入、caplog敏感字段检查。
- 验收：无遗留HTTP客户端；用户错误可关联日志；不输出完整敏感内容。

## TASK-019：将锁文件真正接入构建和持续检查

- 问题：F-16/F-22；目标是实际安装遵守验证版本，提交可自动回归。
- 涉及文件：`Dockerfile`、`pyproject.toml`、`requirements/`；新增 `.github/workflows/ci.yml` 与必要质量工具配置。
- 方案：Docker复制并安装py311锁，再安装项目no-deps；Windows按对应锁；引入固定版本ruff/coverage/依赖审计，类型检查从核心模块开始；以当前真实支持平台建矩阵，未支持平台不虚报。
- 步骤：独立环境验证锁 → 构建非editable wheel → 检查static资源 → CI离线tests/lint/选定types → 联网CVE查询记录时间和结果 → 检查容器非root运行与写目录权限。
- 依赖：006、016、018。优先级 P1；复杂度 M；类别必须。
- 风险：依赖审计访问外部数据库；只提交包名版本，不提交语料或.env；升级只针对实际发现问题。
- 验证：干净环境pip check、wheel安装、静态资源HTTP；CI故意失败的测试应阻断。
- 验收：构建不再绕过锁；工具结果真实记录；无未处理的高危可利用依赖问题；没有为了lint全库格式化。

## TASK-020：建立核心浏览器和恢复E2E

- 问题：现有UI测试多为文件内容断言；目标是用户路径持续可复现。
- 涉及文件：新增 `tests/browser/`、浏览器测试配置；`tests/integration/`；CI和测试指南。
- 方案：浏览器状态测试使用受控服务响应；独立真实Ollama/Qdrant组验证至少一条实际问答。两类报告明确分开。
- 步骤：空库→导入说明→模型发现→问答→引用→导出→清空→再问 → 401/429/503/504 → 源服务恢复 → 重启API → 容器recreate → 手机/键盘/缩放。
- 依赖：006、009、010、011、015、016。优先级 P1；复杂度 M；类别必须。
- 风险：测试误连当前语料；固定隔离root、collection和端口，写操作前断言目标。
- 验证：保存逐用例结果/失败截图；真实模型组单列且不得mock生成后标真实。
- 验收：所有核心路径通过；无控制台未处理错误；禁用/加载/空态均能恢复；支持宽度无横向溢出。

## TASK-021：量化性能并处理高收益瓶颈

- 问题：F-12及逐点写入；目标是固定硬件下达到DoD预算。
- 涉及文件：`vectorstore.py`、`pipeline.py`、`ollama_client.py`、`tests/test_vectorstore.py`；新增 `scripts/benchmark_runtime.py`。
- 方案：count用服务端active过滤计数；增加批量upsert；维护结束后集中重建BM25；默认生成输出有界；模型列表短TTL缓存可选。
- 步骤：记录332文档基线 → 改count并断言无scroll → 批量写且检查失败 → 测1/2/4并发请求 → 记录冷/暖p50/p95和内存 → 调整默认模型/上下文。
- 依赖：003、008、010、018。优先级 P2；复杂度 M；类别强烈建议，性能验收必须。
- 风险：批量重试重复写；使用幂等ID，检查部分失败。
- 验证：store功能回归+同机器前后性能报告，不用单次请求宣称p95。
- 验收：health不拉取全部payload；达到第12节预算或列为未通过；数据/检索结果不变。

## TASK-022：完成新机器文档、备份恢复和发布材料

- 问题：文档命令、支持声明与实际交付不一致。
- 涉及文件：`README.md`、`requirements/README.md`、`docs/DEMO.md`、`docs/reports/final-acceptance.md`；新增 `docs/DEVELOPMENT.md`、`docs/BACKUP-RESTORE.md`、`docs/RELEASE.md`；LICENSE需确认权利人。
- 方案：本地安装为唯一主路径，旧API/Docker为独立章节；加入collector extra、配置表、常见错误；备份配套manifest/SQLite/语料/Qdrant；明确历史报告适用范围。
- 步骤：从空目录按文档运行 → 记录缺失前提并补齐 → 生成隔离备份 → 在独立目录恢复 → 检查来源/引用 → 审核许可证与依赖许可 → 生成发布文件清单。
- 依赖：010、014、019、020、021。优先级 P1；复杂度 M；类别必须。
- 风险：版权信息不能凭空填写；当前123条改动不自动提交；发布清单必须包含未跟踪的新模块。
- 验证：另一干净环境只按文档运行成功；恢复后的索引身份/活跃文档/查询一致。
- 验收：无需隐含个人缓存路径；不覆盖既有.env；发布材料不存在旧PASS误导；许可证文本有实际授权依据。

## TASK-023：小批次清理已确认的生成物

- 问题：少量缓存/空目录可能影响整洁度；目标是清理而不丢审计或用户数据。
- 涉及文件：只允许本次重新核实的缓存/构建输出，候选见第16节。
- 方案：每批记录绝对路径、Git状态、动态/构建/测试/文档引用、恢复方式；证据不足保留。
- 步骤：重新枚举 → 排除修改/新建开发文件 → 对独有文件做内容核对 → 小批清理 → 运行对应构建或测试 → 验证引用。
- 依赖：019、022。优先级 P3；复杂度 S；类别可选。
- 风险：截图/报告是验收证据；不得将整个data或workspace作为目标。
- 验证/验收：每项删除可解释且可恢复；测试构建无退化；所有疑似业务文件保留。

## TASK-024：按DoD执行最终发布验收

- 问题：不能以“能跑/测试绿”替代发布标准。
- 涉及文件：`docs/reports/final-acceptance.md`、`docs/RELEASE.md`、最终逐题和E2E报告。
- 方案：对每个必需任务逐项检查artifact/命令/时间/身份；结果PASS/PARTIAL/FAIL/NOT_RUN；P0/P1或必需门禁不通过则不发布。
- 步骤：核对工作树范围 → 完整测试 → 真实模型/浏览器/重启/恢复 → 核对Golden和性能分母 → 校验wheel/锁/许可 → 生成最终报告及发布候选包。
- 依赖：002–016、018–022；017如留项须有适用边界与风险结论；023不阻塞。
- 优先级 P1；复杂度 M；类别必须。
- 风险：偷换验收阈值或漏记跳过；冻结阈值/身份，明确所有残留风险。
- 验证/验收：第24节全部必需项通过，无P0/P1；本地v1可交付。生成候选包不等于自动提交、合并或对外发布。

# 22. 任务依赖关系

主链：001 → 002 → 003 → 004 → 005 → 010 → 012 → 013 → 014 → 022 → 024。

运行支链：001 → 007 → 008 → 009；005 → 006；001 → 016；009+010+016 → 011。

质量支链：002+008 → 015；008 → 018；003+008+010+018 → 021；012+013+015+021 → 014。

交付支链：006+016+018 → 019；006+009+010+011+015+016 → 020；010+014+019+020+021 → 022。016 → 017；019+022 → 可选023。

人审等待期间可继续016～021，不需要停下所有工程工作。不得自动将人审改成AI签名。

# 23. 推荐执行顺序

**001（本轮完成）→ 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 016 → 010 → 011 → 015 → 012 → 013 → 018 → 017 → 021 → 019 → 020 → 014 → 022 → 可选023 → 024。**

同一时间不让多个任务修改 pipeline/manifest。人工审核可与不改Golden/corpus的工程任务并行；审核期间冻结语料快照。若必须更新语料，记录新快照并重新核对受影响题。

# 24. 最终验收Checklist

| 类别 | 必需检查 | 具体方法 | 通过标准 |
|---|---|---|---|
| 功能 | 真实问答/引用/拒答/模型切换 | 固定真实语料、默认模型和第二允许模型逐问 | 有证据题正确；无证据按门槛拒答；模型身份准确 |
| 功能 | 改写开关 | 有历史指代、模型缺失、错误码保留 | applied/fallback原因正确；原问题用于回答 |
| UI | 清空/重试/超长历史/输入法 | 浏览器自动化及中文输入法人工检查 | 可继续发送，无旧回答回填，无无意义422 |
| UI | 移动/键盘/空态/错误 | 320～1440宽度、200%缩放、Tab、断网 | 无不可达操作/横向溢出；焦点可见 |
| API | 鉴权和错误合同 | 401/413/422/429/503/504逐项触发 | 状态码、结构和提示一致；不返回secret |
| API | 长生成并发health | Event阻塞生成与真实慢请求 | health p95≤500ms；无trace串台 |
| 数据 | 全正文分块覆盖 | 唯一字符/长段/标题/代码样本 | 不遗漏正文；算法身份更新 |
| 数据 | 更新失败与幂等 | 各阶段故障注入、长文缩短、重复执行 | 已提交内容不丢；旧尾部不残留 |
| 数据 | 重建保护 | 指定已有集合以及中途失败 | 写入前拒绝；active manifest不误切 |
| 数据 | 重启/备份恢复 | 新进程、独立恢复目录、容器recreate | 索引身份和有效文档匹配、可查询 |
| 安全 | 根目录/请求体/Host/非loopback | 越界路径、无长度body、空key共享配置 | 请求被拒绝且服务持续可用 |
| 安全 | 文档注入/XSS/日志 | 恶意文本与合成secret样本 | 不执行脚本/工具；不泄露密钥；语义局限明确 |
| 安全 | 依赖/许可 | 带日期漏洞审计、LICENSE/第三方清单 | 无未处置高危可利用问题，授权依据完整 |
| 性能 | 检索与生成 | 固定硬件30次以上暖机样本，独立冷启动 | 达到预先冻结预算，超时计入分母 |
| 测试 | 回归和覆盖 | 默认pytest、integration、browser、branch coverage | 必需测试全过；跳过明确；核心异常受覆盖 |
| 评测 | Golden与split | 100题真实审核记录、hash、近重复检查 | 未审核0条；split不泄漏；来源有效 |
| 评测 | 真实模型资格 | release配置与逐题身份核对 | 无测试嵌入/offline冒充；有效引用100% |
| 部署 | Windows新环境 | 仅按README从空目录安装运行 | 不依赖私有路径、云key或Docker |
| 部署 | wheel/Compose | wheel静态资源请求、锁安装、recreate | 页面/API可用，版本和数据保留 |
| 文档 | 命令逐条执行 | 开发者按安装/恢复/评测指南操作 | 无缺extra、无过时默认值、无覆盖用户.env |
| 体验 | 保存和再次查看 | 导出答案/引用后重新打开 | 内容可读，来源可追溯，不包含key |

验收记录必须包含执行日期、commit或文件快照身份、有效配置、数据/模型身份、命令、退出码、报告位置。旧报告可以引用，但必须标历史证据，不能作为新版本自动通过。

# 25. 项目最终建议

最合理的路线是**保留当前技术栈，优先修数据正确性，再补运行与评测闭环**。当前阻碍不是功能数量少，也不是框架不够新，而是缺少关键不变量和发布路径验证。

以上是初始审查时的执行建议；实际执行已按任务表推进并完成 TASK-002～012、TASK-015～020。当前仍需真实人工 Golden 审核、正式 benchmark/性能证据和许可证依据，不能将 provisional 结果升级为发布结论。

执行更新（2026-09-12）：已修复分块完整性、版本提交/恢复、索引身份、容器持久化、模型路由、并发状态、UI 恢复、API 安全、采集时限、资源关闭、锁定构建、浏览器/Windows/Docker 验收及评测 checkpoint；已补充开发、备份恢复、发布和索引迁移文档；本轮追加 URL scheme 限制、不可信 sitemap XML 防护、生成器运行时不变量检查和 CI 安全 lint。未删除用户源码、数据、资源、配置、数据库或未提交文件，也未运行生产数据迁移、修改密钥或自动替换默认集合。

# 项目执行总表

| ID | 任务 | 优先级 | 复杂度 | 依赖 | 状态 | 验收标准 |
|---|---|---|---|---|---|---|
| TASK-001 | 基线与审查 | P1 | S | 无 | 已完成本轮审查 | 初始 213通过/2跳过；当前 224通过/2跳过，隔离复现与保护范围记录 |
| TASK-002 | 分块正文完整性 | P0 | M | 001 | 已完成 | 无遗漏正文，长段/标题/代码覆盖 |
| TASK-003 | 版本提交和失败恢复 | P0 | L | 002 | 已完成 | 故障不丢有效版本，缩短无残留 |
| TASK-004 | 新集合重建保护 | P1 | M | 003 | 已完成 | 已有集合写入前拒绝，manifest不误切 |
| TASK-005 | 索引身份升级 | P1 | M | 002,004 | 已完成 | backend/digest/算法不匹配拒绝复用 |
| TASK-006 | 容器状态持久化 | P1 | M | 005 | 已完成 | API recreate后查询与身份一致 |
| TASK-007 | 云端兼容模型路由 | P2 | S | 001 | 已完成 | 两入口默认模型语义一致 |
| TASK-008 | 请求状态与锁 | P1 | L | 003,007 | 已完成 | 慢生成不锁health，无trace串台 |
| TASK-009 | 清空/历史/重试交互 | P1 | M | 008 | 已完成 | 清空恢复发送，超长历史可续问 |
| TASK-010 | 本地发布profile | P1 | M | 005,008 | 已完成 | 独立 API profile 加载 schema 2 持久索引并通过查询 |
| TASK-011 | 来源定位和结果导出 | P2 | M | 009,010,016 | 已完成 | 查得到来源，保存结果可再查看 |
| TASK-012 | 正式评测门禁 | P1 | M | 005,008 | 已完成 | 测试后端不能取得真实质量资格 |
| TASK-013 | 人审工具和Golden | P1 | M | 012 | 工具完成·等待真实人审 | 100 reviewed，冻结split，无伪签 |
| TASK-014 | 可恢复真实基准 | P1 | L | 012,013,015,021 | checkpoint完成·正式运行待Golden | 当前身份全量成绩、失败分母、checkpoint |
| TASK-015 | 实发证据引用门禁 | P1 | M | 002,008 | 已完成 | 裁剪尾部不被误当支撑 |
| TASK-016 | API安全边界 | P2 | M | 001 | 已完成 | body/路径/鉴权/共享启动策略通过 |
| TASK-017 | 采集网络/时限 | P2 | M | 016 | 已完成 | deadline严格执行，目的地受限 |
| TASK-018 | 资源关闭和错误日志 | P2 | M | 008 | 已完成 | 无客户端泄漏，错误带trace且脱敏 |
| TASK-019 | 锁构建与CI | P1 | M | 006,016,018 | 已完成 | 干净安装、wheel、Windows 锁对应 CI、Ruff/mypy 与漏洞审计 |
| TASK-020 | 浏览器与恢复E2E | P1 | M | 006,009,010,011,015,016 | 已完成 | 核心路径全过、真实组独立 |
| TASK-021 | 性能预算与瓶颈 | P2 | M | 003,008,010,018 | 真实诊断完成·正式性能待Golden | 当前候选 profile 已有 30 次检索和 3 次真实生成数据；正式固定硬件预算/质量门槛仍待完成 |
| TASK-022 | 文档/备份/许可/发布 | P1 | M | 010,014,019,020,021 | 文档完成·许可证阻断 | 新环境按文档运行，恢复查询一致 |
| TASK-023 | 确认后清理生成物 | P3 | S | 019,022 | 未删除·已加忽略 | 不丢数据/证据，每批可恢复 |
| TASK-024 | 最终验收 | P1 | M | 全部必需任务 | 部分完成·可重复门禁已加·未发布 | `scripts/release_gate.py` 可重复报告阻塞；Golden/许可证仍未完成 |
