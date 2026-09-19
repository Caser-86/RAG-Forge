# RAG-Forge 五分钟 Demo（Windows）

## 0:00–1:00 启动与状态

在仓库根目录打开 PowerShell：

```powershell
.\.venv\Scripts\python.exe -m scripts.check_environment --json
.\scripts\start.ps1
.\scripts\status.ps1
```

启动脚本默认使用 `127.0.0.1:8000`、一个 worker 和项目虚拟环境。若使用 Ollama，开始前确保 `bge-m3` 与默认生成模型已安装；`gemma4:e4b`、`qwen3:0.6b` 等可选模型缺失会被明确提示。

## 1:00–2:30 混合检索问答

打开 `http://127.0.0.1:8000`，在 Chat 中选择生成模型、`Hybrid + BM25` 和 Top-K=5，提问：

```text
BGE-M3 的向量维度是多少？BGE-Reranker 在链路中负责什么？
```

确认回答出现来源编号和来源卡片；若当前索引尚未摄入 `data/raw/docs/bge-rag.md`，先执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.ingest_docs data/raw/docs
```

## 2:30–3:30 Debug Trace

切到 Debug，确认能看到 trace id、阶段耗时、候选证据、最终 context、raw output 和 citation。分数的 calibration 会标明是否只是 raw/uncalibrated，不能当作概率。

## 3:30–4:15 切换模型与拒答

切换到另一个已安装的生成模型，使用同一个问题再次提问；只验证生成模型切换，不应触发重新索引。然后提问一个完全不在语料中的问题，确认出现 `REFUSED` 与拒答原因，而不是编造答案。

## 4:15–5:00 配置与关闭

在 Settings 中查看服务状态、索引 chunk 数、当前模式和 Query Rewrite。Query Rewrite 默认 OFF；开启时只改写检索 query，原问题仍用于回答，失败会回退并记录 Trace。

真实 benchmark 入口和当前 provisional 结果见 [`M9-benchmark.md`](reports/M9-benchmark.md)。在 Golden Set 尚未人工冻结前，只能演示候选集管线；报告中的 20 条 Ollama 双模型采样是旧 116 文档快照的通信/链路证据，不能把这些数字当作当前语料或发布指标。当前 332 文档候选索引已另行完成真实 hybrid → Gemma → Citation/Trace 验证，正式质量结论仍需人工 Golden Set。

结束时：

```powershell
.\scripts\stop.ps1
.\scripts\status.ps1
```

`stop.ps1` 只会在 PID、启动时间、项目路径和 uvicorn 命令行均匹配时停止自有服务，不会停止 Ollama，也不会触碰 Qdrant 数据。

如果 API 运行在 Docker Desktop 容器中而 Ollama 运行在 Windows 宿主机上，使用 `docker-compose.ollama.yml` override；容器内地址必须是 `http://host.docker.internal:11434`，不能使用宿主机视角的 `127.0.0.1:11434`。

如果宿主机已经有 Qdrant 占用 6333，Compose 的默认端口仍保持 6333/8001；可在 PowerShell 中临时改宿主映射端口后启动：

```powershell
$env:RAGFORGE_QDRANT_HOST_PORT = "16333"
$env:RAGFORGE_API_HOST_PORT = "18002"
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

两个变量只改变宿主机映射端口，不改变 Compose 网络内的 `qdrant:6333` 或 API 容器端口 8000。
