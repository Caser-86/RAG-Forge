# RAG-Forge 技术讲解（开发基线）

文档核对：2026-10-27。对应已提交源码基线 `a14db8e`；当前分支范围见 [README](README.md)，运行流程见[Demo](docs/DEMO.md)。

可以说明的实现包括：Ollama embedding/生成、Dense/BM25 双路检索、RRF 融合、可选 CrossEncoder、引用/拒答、Web UI 与 Trace、candidate benchmark 和审核工具。本地后续 readiness、PDF worker 与恢复/安全整改未随本次文档更新提交。

RRF 按排序融合，常数 `k` 也是参数；重排对 query-passage 成对打分，raw 分数未校准。不能承诺混合检索或重排在所有数据上优于基线，应展示固定数据上的对照结果。

引用编号、证据选择和拒答规则不等于答案语义全部正确；token 覆盖代理也不是事实准确率。正式结论需要真实审核的 Golden、冻结 split 与人工答案评审。

演示前确认实际模型、profile、语料和 API key。InMemory 的 CLI 与 API 不共享数据，Qdrant Local 的独立写入应避开 API 占用窗口。Trace 展示用于诊断，UI 清空不会自动删除服务端 Trace。

旧的模型服务名称、单次 rerank 分数和 MLQA 数字只保留于[历史评测](docs/reports/legacy-mlqa-evaluation.md)，不作为当前配置或发布质量。历史阶段验收见[验收范围](docs/reports/final-acceptance.md)。
