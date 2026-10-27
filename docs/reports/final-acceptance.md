# RAG-Forge 验收范围（GitHub 开发基线）

文档核对：2026-10-27。结论：**PARTIAL / 不发布**。适用源码基线为 `a14db8e`，不是本机含未提交整改的工作树。

## 当前可确认的仓库状态

- 已提交本地 RAG、Ollama 模型路由、混合检索、Web UI、Trace、候选 benchmark 和审核工具。
- 此基线 `benchmarks/golden.jsonl` 为空，根 LICENSE 与 `benchmarks/golden-split.json` 缺失。
- 本次仅核对源码、文件树与文档，没有重跑该分支 pytest、模型、浏览器、Docker 或服务；不报告新的运行 PASS。
- 本地后续实现的 readiness、PDF 独立 worker、更新恢复与安全硬化未随此次文档提交发布，不能引用本地 628 项通过作为该提交的测试结果。

## 后续验收

权利人许可、真实人工审核、冻结 split、正式 benchmark、目标 profile、备份恢复和候选代码的完整运行验收仍需完成，见 [TODO](../../TODO.md)与[发布清单](../RELEASE.md)。

原总体验收表已保留为[历史记录](final-acceptance-history-2026-09-19.md)，其中 PASS、测试数量、模型列表、集合点数及本机路径仅指原记录日期。旧 MLQA 指标见[历史评测](legacy-mlqa-evaluation.md)，不作为当前正式质量结论。
