# M4 验收报告：公开资料采集、清洗与增量更新

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

日期：2026-09-11  
状态：通过 M4 门禁，可进入下一阶段；本报告不代表 M5 已开始。

## 1. 交付范围

本阶段完成了官方技术文档的受控采集、正文清洗、来源保留、SQLite 清单、版本化索引、可恢复更新任务，以及 Qdrant Server 的真实链路验证。

首批来源为：

| 来源 | 发现方式 | 域名 | 采集条件 |
|---|---|---|---|
| Ollama | sitemap | `docs.ollama.com` | 官方文档，trust 1.0 |
| Qdrant | sitemap | `qdrant.tech` | 官方文档，trust 1.0 |
| FastAPI | sitemap | `fastapi.tiangolo.com` | 官方文档，trust 1.0 |
| LangChain | sitemap | `docs.langchain.com` | 官方文档，trust 0.95 |

采集配置位于 [configs/sources.yaml](../../configs/sources.yaml)。安全 YAML 解析不执行任意 Python 构造；来源域名、协议、重定向目标和 DNS 解析地址均重新校验。

## 2. 已完成修改

| 文件 | 修改内容 |
|---|---|
| `src/ragforge/collector.py` | sitemap/链接发现、robots 遵从、限速、重试、响应大小限制、重定向域名与 SSRF 防护、gzip 和尾斜杠处理 |
| `src/ragforge/ingest/cleaner.py` | trafilatura 优先、BeautifulSoup fallback、保留标题/代码/列表、去除页面 chrome、登录页/空页/模板页跳过、正文哈希 |
| `src/ragforge/knowledge_manifest.py` | SQLite schema、稳定 doc_id、版本/状态/job/run、来源别名、恢复和增量判定 |
| `src/ragforge/pipeline.py` | 新版本先写入并验证，再删除旧版本；失败时只清理候选版本；active 状态同步 |
| `src/ragforge/vectorstore.py` | 版本删除、active 过滤、Qdrant Server/InMemory 一致契约 |
| `scripts/fetch_sources.py` | 采集、落盘 raw/processed、输出采集报告 |
| `scripts/update_knowledge.py` | 采集清洗后增量更新；CLI 显式覆盖 `.env`；索引阶段默认关闭 CrossEncoder 重排 |
| `src/ragforge/index_manifest.py` | Windows 瞬时文件锁下的原子 manifest 替换有限退避重试 |
| `pyproject.toml`、`.gitignore` | 声明采集可选依赖并忽略处理产物/清单运行数据 |
| `tests/test_collector.py`、`test_cleaner.py`、`test_knowledge_manifest.py`、`test_incremental_update.py`、`test_update_script.py`、`test_index_identity.py` | 增加离线安全、清洗、版本、恢复、身份和 Windows 原子写入回归测试 |

## 3. 真实验收证据

### 3.1 来源与采集

已实际请求四个站点的 robots 与 sitemap：robots 均返回 HTTP 200；sitemap 发现规模为 Ollama 67、Qdrant 786、FastAPI 151、LangChain 1581 个 URL。LangChain 的 `llms.txt` 也可访问，但本阶段仍采用 sitemap 作为统一发现入口。

10 页/源的采集报告为 `data/reports/fetch-20260911-125831.json`（本地历史产物，不随仓库分发）：

- 40 个页面成功响应；39 个清洗成功；1 个页面按登录页规则跳过；0 个抓取失败。
- `enumeration_complete=false` 是预期结果，因为本轮使用了页面上限，不能据此执行 INACTIVE 下线。

### 3.2 增量更新

所有真实更新均使用 Qdrant Server `http://127.0.0.1:6333`、集合 `rag_forge_m4_ollama_v1`、Ollama `bge-m3`；脚本输出确认 `use_rerank=false`，没有把 `.env` 中的旧重排实验配置带入索引任务。

| 轮次 | 结果 | 嵌入调用 |
|---|---|---:|
| 10 页/源首轮 | added 14，updated 1，unchanged 24，failed 0 | 15 |
| 相同 10 页/源第二轮 | added 0，updated 0，unchanged 39，failed 0 | 0 |
| 30 页/源扩大轮次 | added 76，unchanged 39，failed 1 | 76 |
| 扩大轮次补偿 | added 0，updated 1，unchanged 115，failed 0 | 1 |

扩大轮次最终形成 116 个 indexed 文档，覆盖 100～300 有效页目标。中途曾出现一次 Windows `WinError 5` 原子替换失败；文档旧索引未被删除，修复重试后单独补偿成功。

最终只读状态：

- SQLite：116 个 `indexed` 文档；无 `pending`、`indexing` 或 `failed` 文档；无未完成 job。
- Qdrant：`readyz=200`，集合状态 `green`，1273 个 points，update queue 为 0。
- 没有遗留 `update_knowledge` 进程，也没有在 `data` 下发现 `.tmp/.bak/.backup/.old/.orig/.temp/.log` 文件。

机器报告位于 `data/reports/update-9be5379be8f84404a8aeb7444e5c04af.json`（本地历史产物，不随仓库分发）。

### 3.3 自动化验证

以下命令均以当前 `.venv` 执行并返回成功：

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.smoke
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m compileall -q src scripts tests
git diff --check
```

全套测试通过；输出为 `ss... [77%]`、`..................... [100%]`，其中 `s` 为既有的显式集成测试跳过标记，不是 M4 离线失败。smoke 使用 InMemory + deterministic + offline，不访问 Qdrant、Ollama 或云端 API。

## 4. 安全与可靠性结论

- 仅允许 HTTP/HTTPS，无凭据 URL；初始 URL 和每次重定向都限制在允许域名并阻止本机、私网、链路本地等解析地址。
- sitemap 是不可信 XML，使用 `defusedxml` 解析；带 DTD/实体声明的内容按 `bad_sitemap` 拒绝，不进入 URL 发现流程。
- robots 异常按保守策略跳过来源；429 使用 `Retry-After` 并受总等待上限约束；5xx 有有限退避。
- 每页有超时、重试、重定向和响应大小上限；单页错误不会中止其他页面。
- 更新顺序为“清洗/分块/嵌入/验证 → 删除旧版本 → 标记 indexed”；失败不会先删除旧版本。
- `.env`、`.venv`、原始语料、Qdrant 数据和未提交文件均未删除；本阶段没有执行文件删除。

## 5. 保留但未删除的疑似无用/实验文件

| 文件/目录 | 保留原因 | 删除前还需的证据 |
|---|---|---|
| `data/knowledge_manifest.sqlite3`、`data/qdrant*` 或旧 acceptance 集合 | 来自前阶段/旧后端的本地试验和用户工作成果，不属于明确垃圾；删除会丢失可恢复状态 | 用户明确确认不再需要，并再次核对 Git/运行配置/引用 |
| 根目录 `.env`、`.venv` | 环境和本地配置，且可能含敏感值 | 不应自动删除；需用户自行迁移或清理 |
| 现有历史计划、审计报告和未跟踪开发文件 | 属于项目过程资料或当前工作树修改，不能因未被源码引用而判定无用 | 用户确认归档/删除范围 |

## 6. 暂未修改的问题

### P0/P1

当前没有在 M4 验收范围内确认的 P0/P1 问题。

### P2

1. 当前真实采集使用 `--max-pages 30`，四个来源的枚举均未完整；因此没有执行大规模完整 sitemap 导入，也没有对不完整来源做自动下线。这是受控范围，不是数据完整性结论。
2. 抓取依赖公网站点可达性和站点当前 HTML 结构；站点改版后应重新检查清洗质量。
3. 更新 CLI 要求 API 进程停止以保证单进程维护窗口；尚未实现跨进程锁或在线更新协调。

### P3

1. README 尚未在 M4 单独补充采集/增量更新操作章节，计划中的统一文档整理留到后续文档阶段处理。
2. 历史 terminal job 记录保留在 SQLite 中用于审计；它们不是当前未完成任务。

## 7. 下一阶段条件

M4 门禁已满足。下一步可进入 M5（heading-aware 分块、BM25 中文 token、请求级 retrieval mode 和可选重排器懒加载）；进入后应继续保持当前 Qdrant 集合/清单隔离策略，不直接复用旧 `.env` 实验配置。
