# RAG-Forge 总体验收表

2026-09-19 增量：A1–A3 评测可信性工程项已完成；当前全量回归为 243 passed、2 skipped。该结果不改变总体 `PARTIAL / 不发布` 结论：人工 Golden、正式 benchmark、许可证与最终交付门禁仍未完成。

2026-09-16 增量记录见 [R1 基线核对](R1-readiness-2026-09-16.md)：审核记录内容绑定已修复，本轮全量回归 229 passed、2 skipped；R1 仍有分块实验隔离、split 内容绑定等缺口。下文 2026-09-12 的运行状态属于历史证据，不代表本轮重新验证。

日期：2026-09-12

状态含义：`PASS` 表示当前证据满足该项；`PARTIAL` 表示自动化/组件部分完成但仍有范围缺口；`PENDING` 表示需要人工审核或受控环境才能确认；`SKIP` 表示按设计未在默认离线回归中启用。

| 阶段/范围 | 状态 | 当前证据 | 未完成项 |
|---|---|---|---|
| M0 基线与环境 | PASS | [M0-baseline.md](M0-baseline.md)、`check_environment --json`；Python 3.14.6，4 个必需 Ollama 模型齐全 | Python 3.10/3.11 未实测 |
| M1 Ollama 生成/模型切换 | PASS | [M1-ollama-generation.md](M1-ollama-generation.md)、`tests/integration --run-ollama` | 无 |
| M2 Ollama embedding | PASS | [M2-ollama-embedding.md](M2-ollama-embedding.md)、本机 embedding 集成测试 | 无 |
| M3 持久化与 metadata | PASS | [M3-persistence-metadata.md](M3-persistence-metadata.md)、Qdrant `ready=200` 与现有集合核对；全量候选索引另建独立集合并完成校验 | 当前 `.env` 仍为 `in_memory + local`，切换到 `qdrant_server + bge-m3` 新集合需按发布窗口显式决定 |
| M4 采集与增量 | PASS | [M4-acceptance.md](M4-acceptance.md) | 采集动作本身依赖联网 |
| M5 分块/检索/重排 | PASS | [M5-acceptance.md](M5-acceptance.md)、本机 reranker 实际单次重排 | 正式 rerank benchmark 尚待 Golden Set |
| M6 Citation/Refusal/Trace | PASS | [M6-acceptance.md](M6-acceptance.md)、对应单元测试与校准报告 | 语义支撑仍需人工/语义评测 |
| M7 Web UI | PASS | [M7-ui.md](M7-ui.md)、Playwright 页面验收与截图 | 无 |
| M8 Query Rewrite | PASS | [M8-query-rewrite.md](M8-query-rewrite.md)、20 条真实 qwen3 评测 | 默认仍保持 OFF |
| M9 Golden Set/benchmark | PARTIAL | [M9-benchmark.md](M9-benchmark.md)、当前语料候选集 100 条、离线三组实验、生成实验 checkpoint/身份校验链路、只读发布门禁 `scripts/release_gate.py` | `golden.jsonl` 尚为空；需人工审核、冻结 split，并运行正式 benchmark |
| M10 Windows/Docker/交付 | PASS | [M10-acceptance.md](M10-acceptance.md)、Windows 生命周期、受控断网最小 chat、当前 Dockerfile 实际构建、完整 Compose 双服务临时端口端到端 chat；另有 332 文档/5,042 chunk 当前 schema 2 候选索引及独立本机 Qdrant hybrid chat、Windows/Docker 依赖锁安装验证、Docker Compose 两套配置解析 | 正式运行时如宿主 6333/8001 被占用，可设置宿主端口变量；候选集合接入默认配置需显式执行 |
| 默认离线回归 | PASS | 当前工作树 `.venv` 全量为 243 passed、2 skipped；2 个 Ollama 集成测试按设计跳过；未激活系统 `python` 不作为交付环境 | 显式 `--run-ollama` 属于独立真实服务验证；2026-09-12 的 226 项结果仅保留在下方历史记录 |
| 敏感信息/垃圾扫描 | PASS（范围内） | 未发现被 Git 跟踪的敏感文件或密钥字面量；本地 `.env` 的 `RAG_LLM_API_KEY` 已确认被忽略，相关 148 个项目文件未发现泄露；Ruff 安全规则、URL scheme 限制与不可信 sitemap XML 防护通过；缓存和用户数据未删除 | 被策略阻止的物理缓存清理可另行执行；如密钥曾对外暴露应轮换 |

## 当前结论

项目当前可继续开发和本机运行，但总体验收不是 `PASS`：M9 的人工 Golden Set、正式 benchmark 和正式 reranker 校准仍未完成；大语料候选索引与全量 chat 已有证据。当前交付路径的依赖锁已完成验证，其他 Python/OS/CPU-GPU 组合未纳入支持声明。M10 的最小受控断网主链路与完整 Compose 容器端到端链路已有证据；所有 provisional 结果仍只能用于工程诊断，不能作为产品质量指标。新增的只读发布门禁实测为 `BLOCKED`，发布前另需补齐根目录许可证文本/权利人依据、人工 Golden 和冻结 split。

## 关键运行状态

- Ollama：`http://127.0.0.1:11434`，`bge-m3:latest`、`gemma3:4b`、`gemma4:e4b`、`qwen3:0.6b` 均可发现。
- Qdrant：安装于 `D:\Program Files\Qdrant Server`，当前 `ready=200`；旧集合 `rag_forge_m4_acceptance_v1`、`rag_forge_m4_ollama_v1` 和历史 schema 1 集合未改变；当前 schema 2 候选集合 `rag_forge_full_v2_20260912` 为 5,042 points，独立 manifest 为 `data/index_manifest_full_v2_20260912.json`，未自动切换默认用户配置。
- RAG-Forge API：当前没有遗留的 `data/run/ragforge.pid.json` 状态文件。

## 2026-09-12 本轮最终复核

- 工作树未执行 commit、reset、checkout 或覆盖用户 `.env`；所有既有未提交源码、数据、资源和文档均保留。
- `.venv` 全量回归：226 项收集，224 通过、2 个 Ollama 集成测试按设计跳过；Ruff 基础规则、生产源码扩展规则和安全规则均通过；`mypy src/ragforge --ignore-missing-imports --check-untyped-defs` 对 30 个源文件无错误；`pip check` 通过；覆盖率门禁通过，整体 83%。
- README、docs、benchmarks 和 requirements 中的本地 Markdown 链接复核 35 个，0 个失效；M4 报告中 3 个不可移植的 `/D:/...` 链接已改为相对路径。
- wheel 构建成功；Docker Compose base 与 Ollama 组合配置解析成功；本次 Compose 隔离 project 完成 `ingest → API recreate → indexed_chunks 保持不变`，新构建镜像用户为 `ragforge` 非 root。
- `verify_browser_e2e.ps1` 成功覆盖 health/model、问答、Citation、Markdown 导出、清空、Enter 发送和 390/1280 响应式检查。
- Windows `start.ps1` 已在 18085 端口完成真实 start/status/stop；本地子进程优先加载当前 `src/`，停止后自有 PID 状态文件已清除。
- `pip-audit --strict -r requirements/windows-vector-dev-py314-piptools.txt` 返回 `No known vulnerabilities found`；审计范围和日期见依赖审计报告。
- `ruff check --select S src scripts` 返回 `All checks passed`；环境检查拒绝非 HTTP(S) URL，采集器对带实体声明的 sitemap 返回 `bad_sitemap`，并使用 `defusedxml` 依赖。
- 真实 Ollama candidate 2 题双模型试跑成功，记录了 provider model digest 和显式生成参数；第二次相同命令复用 checkpoint 中两个模型各 2 题。该结果仍是 provisional。
- 当前 schema 2 Qdrant profile 以独立 API 端口完成加载验证：health 显示 5,042 chunks、knowledge 显示 332 个文档，hybrid 返回 5 条命中；真实 `gemma3:4b` chat 返回 `grounded=true`、2 条引用且 `citation_invalid=false`，临时 API 已安全停止。
- 当前 schema 2 候选 profile 的真实性能诊断已保存：30 次 warm hybrid 检索 p50=102.260ms、p95=118.043ms；3 次 Gemma 生成 p50=17,476.817ms、p95=17,587.678ms。详见 `data/reports/performance-real-qdrant-v2-20260912.json`；该结果不作为正式 Golden 性能门槛。
- 重建脚本的 Qdrant 写入已改为按 embedding batch 使用 `add_many()`，并以回归测试确认不再逐点 upsert；当前全量候选重建仍按独立新集合运行，不覆盖旧集合。
- 人工审核工具现会展示受限原文预览，并优先定位候选答案/问题附近的证据窗口，再以类别 round-robin 生成带 hash 的 calibration/test split；当前因没有真实审核记录，仍未生成正式 Golden 或 split。
- `python -m scripts.release_gate --json` 已加入只读发布前置检查；当前明确报告 `license_missing`、`golden_empty`、`split_missing`，退出码为 1，未伪造或修改任何发布输入。
- 2026-09-13 复核：发布门禁仍为 `BLOCKED`，`golden.jsonl` 仍为 0 条，根目录仍无 `LICENSE`，未生成 `golden-split.json`；本轮只修正了不可回答题空 `source_refs` 的合法校验边界，并未写入这些外部事实。
- `configs/experiments-release.yaml` 对空的 `benchmarks/golden.jsonl` 按设计拒绝运行，未生成伪正式报告。
- 本轮重新启动已安装的 Qdrant Server 时，先复现并定位了带空格安装路径的 PowerShell 参数引用问题；使用带引号的 `--config-path` 后服务稳定监听 `127.0.0.1:6333`，`/readyz` 返回 200，当前 schema 2 集合为 green、5,042 points，历史 schema 1 集合保持不变。
- 物理缓存/构建产物删除未执行：删除命令被当前环境安全策略拒绝；相关路径已被 `.gitignore` 隔离，且没有删除任何业务文件。

因此本报告结论保持 `PARTIAL / 不发布`，不能因为自动化回归全绿而升级为正式发布通过。
