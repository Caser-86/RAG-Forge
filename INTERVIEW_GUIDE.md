# RAG-Forge 技术讲解（main）

文档核对：2026-10-27；仅适用于当前 `main` 的早期 API 代码。安装、接口与分支差异见 [README](README.md)。

## 可说明的实现

文档分块后经 embedding 入库，问题经过 Dense/BM25 检索和 RRF 融合，可选 CrossEncoder 重排，再将证据交给生成后端。API 提供 `/ask`、`/query`、`/ingest` 与 `/health`。

RRF 按排序而非原始相似度融合，常数 `k` 仍是参数。CrossEncoder 的 raw 分数不是已校准概率；效果须以固定数据集比较，不能由某个高分示例推断准确率。

生成后端采用 OpenAI-compatible 接口；未配置 key 时的离线输出用于链路演示。不能把 main 讲解成已具备开发分支的 Ollama 路由、Web UI、受保护 Trace 或 PDF worker。

## 演示边界

- 先检查实际配置、依赖、模型和语料，不假设宿主机缓存路径可移植。
- 用 README 的 deterministic/InMemory smoke 验证基础流程；真实模型结果另列。
- InMemory 的 CLI 与 API 进程不共享索引，向目标 API 摄入后才演示查询。
- 本分支的摄入路径和 API 访问应限制在受信本机；部署前需要重新做安全验收。
- 答案中的引用和拒答规则不等于语义事实保证；token 覆盖代理也不是准确率。

旧 README/面试稿中的分数、云端模型名称和指标仅作[历史记录](docs/reports/legacy-mlqa-evaluation.md)，不作为当前默认配置或发布结果。第三方模型/数据和根许可证需分别确认。
