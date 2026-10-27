# RAG-Forge 五分钟 Demo（Windows）

对应 GitHub 已提交开发基线 `a14db8e`。演示前按[本地部署](LOCAL-SETUP.md)完成环境与语料准备；本页不假设用户机器已有某个模型、文件或服务。

## 准备

- 选择正式或隔离 profile；检查 Ollama 与配置允许的模型。默认 embedding 为 `bge-m3`、生成为 `gemma3:4b`，其他模型按实际安装情况选择。
- 使用已确认许可、已摄入的示例文档，事先准备一个可答问题和一个无证据问题。
- `qdrant_local` 的 CLI 摄入/更新应在 API 停止的维护窗口执行，随后启动 API；不要并发打开同一本地持久库。
- `in_memory` 的 CLI 进程与 API 进程不共享内存。向正在运行的演示 API 添加文档应使用其 `POST /ingest`，路径必须位于配置的 ingest root 内。
- Windows 脚本遵守本机执行策略；若被拒绝，记录未运行，在允许执行脚本的环境补验。

## 0:00–1:00 启动与检查

```powershell
.\.venv\Scripts\python.exe -m scripts.check_environment --json
.\scripts\start.ps1
.\scripts\status.ps1
```

默认地址 `http://127.0.0.1:8000`。此基线提供 `/api/health`，没有 `/api/ready`；检查知识库已摄入后再演示有效检索。已配置 API key 时，请求需携带 `X-API-Key`。

## 1:00–2:30 问答与引用

打开页面，选择已安装的生成模型、Hybrid 与 Top-K，提出与实际已摄入文档相符的问题。确认答案、引用卡片和所选检索模式；不要预设具体分数或将某次回答当作正式准确率。

## 2:30–3:30 Debug Trace

查看 trace id、耗时、候选、最终 context、raw output 和 citation。raw rerank 分数未校准，不是概率；编号映射正确也不等于答案语义已审核。

## 3:30–4:15 模型切换与无证据问题

若有另一个允许且已安装的模型，切换后提出同一问题。再提无证据问题，观察拒答及原因；若未拒答，记录为待评审结果，不掩盖它。Query Rewrite 默认关闭，开启后只改检索 query，失败按实现回退。

## 4:15–5:00 导出、清空与关闭

导出 Markdown，清空会话，并核对 Debug 展示已清空。UI 清空不会删除服务端 Trace；服务端按条数/TTL 保留。

```powershell
.\scripts\stop.ps1
.\scripts\status.ps1
```

启动和停止脚本使用相同的 `RAG_RUN_DIR`。停止只针对身份匹配的自有 API 进程，不停止 Ollama 或删除 Qdrant 数据。

## Docker 与评测入口

Docker Desktop 连接宿主 Ollama 时使用 `docker-compose.ollama.yml` 和 `host.docker.internal`；宿主映射端口可通过 `RAGFORGE_API_HOST_PORT`、`RAGFORGE_QDRANT_HOST_PORT` 调整。详见[本地部署](LOCAL-SETUP.md)。

演示只验证功能链路。正式 Golden/split 与 benchmark 见[评测手册](../benchmarks/README.md)，历史采样结果见[M9 报告](reports/M9-benchmark.md)。
