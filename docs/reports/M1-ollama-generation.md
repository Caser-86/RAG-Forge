# M1 Ollama 生成与请求级模型切换报告

## 范围

- 分支：`codex/local-rag-m0`
- 本阶段只实现生成后端、模型发现、请求级模型选择和兼容 API；检索仍使用 deterministic + InMemory，未把本阶段结果当作检索质量结论。
- 未删除源码、资源、数据或用户未提交文件。

## 已实现

- 新增 `src/ragforge/ollama_client.py`：封装 `/api/tags`、非流式 `/api/chat`、健康检查和资源关闭；连接失败、超时、模型不存在、协议错误分别分类；不自动重试，不伪装流式响应。
- 新增显式 `generation_backend=ollama|api|offline`，默认本地 Ollama；默认模型为 `gemma3:4b`，allowlist 为 `gemma3:4b`、`gemma4:e4b`。
- 新增 `OllamaGenerator`；请求模型作为局部参数传递，不修改共享 Settings 或生成器默认模型。
- 新增 `/api/models`、`/api/chat`、`/api/health`，保留 `/ask`、`/query`、`/ingest`、`/health`。
- 生成模型选择必须同时通过 allowlist 和已安装模型检查；`bge-m3` 被配置校验拒绝进入生成 allowlist。
- 非 ASCII API key 使用 UTF-8 bytes 比较，避免 `hmac.compare_digest` 对非 ASCII 字符串抛 `TypeError`。
- `scripts.smoke` 显式使用 offline 后端，避免默认本地模型改变离线 smoke 语义。
- 更新 `.env.example`、README、依赖声明和 M1 测试/集成测试。

## 验证证据

### 本机 Ollama 协议

实际读取 `http://127.0.0.1:11434/api/tags` 成功，响应含标准 `models[].name` 字段；当时可见模型为 `bge-m3:latest`、`gemma3:4b`、`gemma4:e4b`、`qwen3:0.6b`。bge 的 `:latest` 别名只用于 embedding 展示，不进入生成 allowlist。

### 测试与静态检查

- 全量离线回归：46 passed，1 skipped（默认跳过本地服务集成测试）。
- MockTransport Ollama 客户端测试：列表、生成请求体、模型不存在、连接失败、超时、服务端错误、非法/空响应、健康状态。
- TestClient API 测试：成功模型列表、两模型交错调用、未知/未安装模型 422、服务不可用 503、超时 504、非 ASCII key 的 401。
- 真实 Ollama 集成测试：`tests/integration/test_ollama_generation.py --run-ollama`，两种模型均真实生成成功。
- `ruff check`：通过。
- `compileall`：通过。
- `scripts.smoke`：退出码 0，明确走 offline。
- `git diff --check`：通过；Git 仅提示现有工作树文件的换行转换警告。

### 真实 API 验收

隔离启动 API 后，先导入 `data/raw/docs/bge-rag.md`，无需重启或重新摄入完成以下调用：

- `GET /api/models`：200，返回两个 generation 模型、`bge-m3` embedding、`qwen3:0.6b` utility，`missing_models=[]`。
- `POST /api/chat` + `gemma3:4b`：200，`requested_model` 与 `model` 均为 `gemma3:4b`，有非拒答答案。
- 紧接 `POST /api/chat` + `gemma4:e4b`：200，`requested_model` 与 `model` 均为 `gemma4:e4b`，有非拒答答案。
- 旧 `POST /ask`：200，返回引用字段和答案；无需更改配置或重启。
- 真实调用耗时受本机模型加载影响：gemma3 约 5 秒，gemma4 首次切换约 42 秒；当前实现选择串行可验证性，不承诺并行模型加载。

## 本阶段未处理

- embedding 仍是原有后端；Ollama `/api/embed` 属于 M2。
- Qdrant 持久化、索引身份、完整 metadata 和生命周期释放属于 M3。
- retrieval_mode、rewrite、history、详细 Citation/Trace 属于后续阶段。
- `reranker_available` 当前反映显式 `use_rerank` 配置；重排模型能力核验留在 M5。
