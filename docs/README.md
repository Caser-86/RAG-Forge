# RAG-Forge 文档索引

这里按“使用者先看什么、维护者再看什么、哪些只是历史证据”组织文档。阶段报告保留原始日期，不代表当前状态；当前状态以根目录 `README.md`、`CONTEXT.md`、`TODO.md` 和本页说明为准。

## 先看这几份

| 目的 | 文档 |
|---|---|
| 安装、启动、API 和能力边界 | [`../README.md`](../README.md) |
| 快速理解架构、模块和当前基线 | [`../CONTEXT.md`](../CONTEXT.md) |
| 查看尚未完成事项 | [`../TODO.md`](../TODO.md) |
| 五分钟 Windows 演示 | [`DEMO.md`](DEMO.md) |

## 日常使用与运维

- [`LOCAL-SETUP.md`](LOCAL-SETUP.md)：新环境、Qdrant profile、索引建立和启停。
- [`DEVELOPMENT.md`](DEVELOPMENT.md)：开发环境、锁文件和回归命令。
- [`BACKUP-RESTORE.md`](BACKUP-RESTORE.md)：语料、索引身份和 SQLite 状态的备份恢复。
- [`INDEX-MIGRATION.md`](INDEX-MIGRATION.md)：索引身份变化、候选重建和回滚。
- [`RELEASE.md`](RELEASE.md)：发布清单、门禁和当前阻塞条件。

## 评测与实验

- [`../benchmarks/README.md`](../benchmarks/README.md)：candidate、Golden、审核和正式 benchmark 规则。
- [`reports/M9-benchmark.md`](reports/M9-benchmark.md)：M9 评测基础设施和 provisional 结果。
- [`../benchmarks/review-batch-01.md`](../benchmarks/review-batch-01.md)：首批人工审核材料，不等于已审核 Golden。
- [`../docs/superpowers/plans/2026-09-19-next-steps.md`](superpowers/plans/2026-09-19-next-steps.md)：A1–A3 工程修复记录及后续人工工作边界。

## 验收与安全证据

- [`reports/final-acceptance.md`](reports/final-acceptance.md)：总体验收结论，当前仍为 `PARTIAL / 不发布`。
- [`reports/project-audit.md`](reports/project-audit.md)：项目级代码、配置、资源和风险审计。
- [`reports/R1-readiness-2026-09-16.md`](reports/R1-readiness-2026-09-16.md)：R1 基线与 A1–A3 收尾证据。
- [`reports/M0-baseline.md`](reports/M0-baseline.md) 至 [`reports/M10-acceptance.md`](reports/M10-acceptance.md)：按阶段保存的历史验收证据。
- [`../security_best_practices_report.md`](../security_best_practices_report.md)：安全审计快照；发布前仍需按目标 profile 复核。

## 设计与历史材料

- [`superpowers/plans/2026-09-16-delivery-roadmap.md`](superpowers/plans/2026-09-16-delivery-roadmap.md)：总体交付路线。
- [`superpowers/plans/2026-09-12-product-readiness-audit.md`](superpowers/plans/2026-09-12-product-readiness-audit.md)：成品化审查和任务拆解。
- [`superpowers/plans/2026-09-11-local-rag-implementation.md`](superpowers/plans/2026-09-11-local-rag-implementation.md)：本地 RAG 改造原始实施计划。
- [`superpowers/plans/2026-09-07-project-audit-cleanup.md`](superpowers/plans/2026-09-07-project-audit-cleanup.md)：早期审计清理计划。
- 根目录 [`RAG-Forge_本地RAG项目改造执行计划.md`](../RAG-Forge_本地RAG项目改造执行计划.md)：原始需求与产品目标，保留作需求来源，不作为当前完成状态。

## 阅读规则

1. 需要当前结论时，先看 `CONTEXT.md`、`TODO.md` 和 `reports/final-acceptance.md` 顶部的最新增量。
2. 带日期的阶段报告只证明当时的环境、数据或代码快照；不要直接复用其中的数字作为当前指标。
3. `benchmarks/candidates.jsonl` 和 `review-batch-01.md` 是候选/审核材料；只有真实审核后进入 `golden.jsonl` 的内容才能用于正式 benchmark。
4. `data/`、`build/`、`dist/`、`.venv/`、各类缓存和运行日志不属于公开文档入口，清理前必须核对 Git 状态和恢复价值。
