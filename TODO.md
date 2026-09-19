# RAG-Forge 待办事项

> 这是当前未完成事项的唯一汇总入口。已完成的 M0–M8、A1–A3 和历史方案不在这里重复列为待办。最近核对：2026-09-19。

## P0：阻塞正式发布

### 1. 补齐许可证事实与文本

- 状态：阻塞，不能由自动生成内容代替。
- 需要：项目权利人确认许可证选择、版权归属和允许分发的第三方材料；随后补齐根目录 `LICENSE`，并核对 `pyproject.toml` 元数据。
- 验收：`scripts.release_gate --json` 不再报告 `license_missing`，许可证文本与元数据一致。
- 依据：[`docs/RELEASE.md`](docs/RELEASE.md)。

### 2. 完成人工 Golden Set 审核

- 状态：未开始正式冻结；`benchmarks/candidates.jsonl` 有 100 条 candidate，`benchmarks/golden.jsonl` 为空。
- 需要：真实审核者逐题确认问题自然度、答案完整性、来源、可回答性和重复/泄漏风险；AI 预审只能作为辅助。
- 验收：100 条 reviewed 记录具备 reviewer、reviewed_at、source_refs 和稳定 corpus/index identity；无重复或非法来源。
- 入口：[`benchmarks/README.md`](benchmarks/README.md)、`scripts/review_benchmark.py`、`benchmarks/review-batch-01.md`。

### 3. 冻结 calibration/test split 并运行正式 benchmark

- 状态：依赖人工审核；`benchmarks/golden-split.json` 尚不存在。
- 需要：生成并核验 schema 2 split，先只在 calibration 集调参，再在 test 集运行 retrieval、chunking、generation 实验。
- 验收：正式命令不带 `--allow-candidate`；输出绑定题集内容 hash、语料/index identity、模型 digest 和 checkpoint identity；失败/跳过不从分母中删除。
- 入口：[`docs/superpowers/plans/2026-09-16-delivery-roadmap.md`](docs/superpowers/plans/2026-09-16-delivery-roadmap.md)、[`docs/reports/M9-benchmark.md`](docs/reports/M9-benchmark.md)。

## P1：交付前必须完成

### 4. 完成人工答案质量与拒答评审

- 审核正式 test 输出的正确性、证据支持、遗漏、虚构、引用有效性和拒答合理性。
- 分别报告各模型、可回答/不可回答类别、失败/超时和真实分母；不得用 AI 预评分代替人工结论。

### 5. 完成固定硬件下的正式性能验收

- 区分冷启动/预热、检索/首 token/完整生成、成功/失败/超时。
- 只有在正式 Golden 与冻结配置上取得的数据，才能用于质量或发布判断；当前 provisional 性能数据只用于工程诊断。

### 6. 完成持久化切换与恢复演练

- 在确认目标 profile 后，备份配置、manifest、语料和对应索引；保留旧集合，不覆盖用户现有数据。
- 实测 Qdrant Server/Local 重启、API recreate、manifest 恢复和抽样查询；记录恢复前后点数、来源和身份。
- 入口：[`docs/LOCAL-SETUP.md`](docs/LOCAL-SETUP.md)、[`docs/BACKUP-RESTORE.md`](docs/BACKUP-RESTORE.md)。

### 7. 执行最终交付门禁

- 至少包含全量 pytest、Ruff、pip check、wheel/Compose 构建、浏览器 E2E、Compose recovery、release gate、安全/依赖复核和工作树范围检查。
- 更新 [`docs/reports/final-acceptance.md`](docs/reports/final-acceptance.md)，逐项记录 PASS/PARTIAL/FAIL/NOT_RUN、命令、时间、profile、身份和风险。

## P2：可维护性与风险收尾

### 8. 明确默认运行 profile

- 当前工作区 `.env` 仍是用户本地配置，不能自动覆盖或替换。
- 在发布窗口明确选择 `in_memory`、`qdrant_local` 或 `qdrant_server`，并为选择的 profile 重新执行环境检查、索引身份检查和重启验收。

### 9. 评估长期文档归档策略

- 阶段验收报告、原始改造计划和面试材料有历史价值，本轮保留。
- 后续若归档，只能在补充引用和索引后进行，并在 Git 状态干净或用户明确指定范围时小批次操作。

### 10. 受控清理生成物

- `.venv/`、`build/`、`dist/`、缓存、`.playwright-cli/`、`output/` 和 `data/` 属于可再生或运行时内容，但当前工作区存在未提交开发成果。
- 清理前需逐目录确认 Git 忽略状态、是否被当前调试复用、是否需要保留验收证据；本轮文档同步不删除这些目录。

## 当前明确不做

- 不伪造人工审核、许可证或正式质量指标。
- 不修改默认 `.env`、不重建/删除用户索引、不删除 `data/`、migrations、资源和历史报告。
- 不为“看起来更干净”而大规模重构或升级依赖。
