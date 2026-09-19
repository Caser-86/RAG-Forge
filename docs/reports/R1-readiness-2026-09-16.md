# R1 基线核对与首批执行记录

日期：2026-09-16。结论：**PARTIAL，尚未进入正式评测。**

## 本轮已执行

- Git 分支 `codex/local-rag-m0`，HEAD `abdd77aa2c51665270412cd9d66f4f75fc66cf9d`；普通 checkout，不是 linked worktree。原有工作树大量修改和未跟踪文件均保留，无提交、切分支或删除操作。该 HEAD 不能代表当前全部源码。
- Python 为项目 `.venv` 的 3.14.6；`pip check` 返回 `No broken requirements found`。
- 当前语料重新计算：332 文件，SHA256 `775af20c80b3cf313f04361d8fa837cff2b4ba259e04a5f128af8c80c40b2d44`，与候选题保存的 corpus identity 一致。
- 当前 Settings 安全字段确认：`in_memory / local / ollama`，分块 800/100。未修改 `.env`，未打印鉴权配置。
- release 配置仍为独立 `qdrant_local`、bge-m3 1024 维、2200/200；候选 manifest 为 schema 2、`qdrant_server`、800/100、collection `rag_forge_full_v2_20260912`。本轮只验证 manifest 文件，不宣称服务存活或实时点数。

## 修复与验证

| 文件 | 问题 | 本轮处理 |
|---|---|---|
| `scripts/review_benchmark.py` | 修改题目后仍按 ID 复用旧 accept/reject；可将未经复审的答案导出成 reviewed | 新决策保存内容 SHA256；内容变化重新提示；缺少哈希的旧接受记录拒绝导出，保留原文件 |
| `tests/test_benchmark_review.py` | 未覆盖过期审核记录 | 新增 5 个回归用例，覆盖问题/答案/来源变更、重新提示、旧格式记录 |
| `benchmarks/README.md` | 正式生成命令缺必需 split | 补齐 split/test 参数，说明旧审核记录必须重新确认 |
| 后续交付计划 | Recall@5 建议值 0.75 与原始需求 0.80 不一致 | 恢复原始 0.80，并补充 Recall@10 0.90、MRR 0.70 目标；目标不等于实际结果 |

按 TDD 执行：新增 5 个用例先全部失败（旧代码未拒绝过期记录），修复后限定回归通过。

| 命令 | 本轮结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_benchmark.py tests/test_benchmark_review.py tests/test_index_identity.py tests/test_release_gate.py` | 修改前 33 passed；修改后 38 passed |
| `.venv/Scripts/python.exe -m pytest` | **229 passed, 2 skipped，14.81 秒**；未启用真实 Ollama 集成测试 |
| `.venv/Scripts/python.exe -m ruff check scripts/review_benchmark.py tests/test_benchmark_review.py` | All checks passed |
| `.venv/Scripts/python.exe -m pip check` | No broken requirements found |

没有运行正式 benchmark、构建、浏览器 E2E 或服务切换；不把上述单元回归当作这些项目的验收证据。

## R1 尚待处理的明确问题

1. **P1：持久化分块实验没有隔离各组路径。** `_run_chunking()` 依次改变 chunk_size，但 `_settings()` 返回相同 qdrant_path、collection 和 manifest；持久化身份检查会拒绝不同分块参数复用同一 manifest。需用真实临时 Qdrant local 建最小测试，给每组配置独立索引及 manifest，确认重复运行不会混入旧语料。
2. **P1：冻结 split 未绑定题目全文。** `freeze_split()` 哈希覆盖 ID 分组和类别计数；`load_frozen_split()` 检查分组哈希和 ID 集合，不能发现相同 ID 的答案变更。需新增题目内容变化后拒绝加载的测试，并统一审核端、runner、release gate 的内容身份协议。现有生成 checkpoint 包含数据文件哈希，不能替代首次运行的 split 校验。
3. **P2：分块比较组与计划不一致。** runner 当前固定为 1200/1800/base/3000，overlap 共用配置，不覆盖 800/100 与 2200/200 成对比较。应在隔离修复后以明确配置表达比较组。
4. **P2：checkpoint 检索契约需进一步核对。** 当前 `_identity()` 未列出全部候选数量与重排模型参数；虽然证据 cache 另有一致性检查，仍需测试参数变化是否能在复用结果前可靠拒绝。
5. M0–M10 历史结果仍保留原日期；本轮未逐项重做集成验收，不能把整个 R1 勾为完成。

审核内容哈希绑定的是候选行（含声明的 corpus identity），不是实时重新读取来源后的内容证明。语料若变更，应重算 corpus identity 并重新审核，不应手工修改哈希绕过审核。

## R2 首批材料

已准备 [首批 20 题审核包](../../benchmarks/review-batch-01.md)，保留原题、原答案、来源链接和原文片段，逐题注明 AI 预审意见。

- 所有题均使用宽泛章节问题并包含文件哈希，需自然化改写。
- 002、010、012、018、020 等存在宣传或过渡文本问题，不宜直接接受为标准答案。
- 未修改 candidates、golden、review-progress 或 split；没有生成任何人工审核身份或结果。
- 本批只有基础题，不代表七类题目覆盖已经完成。

## 可追溯文件哈希（本轮代码修复后）

| 文件 | SHA256 |
|---|---|
| `scripts/review_benchmark.py` | `263BE3DB967B722F8F6742F521A944F570436E5554B06620998A003C68582373` |
| `scripts/run_benchmark.py` | `9567B97811C69C91FAB3EFECFE4E77AB85588A6A508E2C680050FB7B5B025023` |
| `configs/experiments-release.yaml` | `BE58CEB6F93BD1F2354AF163B5647969106C0245308B19F14CEE2D37B03BCDE3` |
| `benchmarks/candidates.jsonl` | `5119987A687C84D7B962AECCEE883C1C7EC6FB66EF5DFCA354DFA8B318E0513C` |
| `data/index_manifest_full_v2_20260912.json` | `D3CF608E279A6EEEAAC9EC63841830339DFB675FAB480980A999A526D0CB0D03` |

下一批先修复分块实验隔离与 split 内容绑定，再继续准备自然化题目。真实审核和许可证权利确认仍需用户参与，但不阻碍这些限定工程修复。

## 2026-09-19 执行增量

按 [后续推进计划](../superpowers/plans/2026-09-19-next-steps.md) 完成 A1–A3：

- A1：`scripts/run_benchmark.py` 从显式 `chunking.variants` 读取 size/overlap；每个语料与参数组合使用独立 Qdrant path、collection、manifest。`configs/experiments-release.yaml` 已明确 800/100 与 2200/200 两组。`tests/test_benchmark_isolation.py` 使用临时 Qdrant local 验证两组连续运行、关闭后重开、数据不串库。
- A2：公共 `benchmark_content_sha256()` / `benchmark_dataset_content_sha256()` 统一审核题和题集身份；split 升级为 schema 2。reviewer 导出、benchmark runner 和 release gate 均拒绝同 ID 但内容变化的题集或旧 schema split。
- A3：index/checkpoint identity 已包含 dense/sparse top-k、rerank candidate/top-k/model、generation top-k、collection/path/manifest 等影响结果的参数；变更参数会拒绝旧 checkpoint。
- 全量验证：`.\.venv\Scripts\python.exe -m pytest` → **243 passed, 2 skipped, 6.87 秒**；`.\.venv\Scripts\python.exe -m ruff check scripts src tests` → `All checks passed`；`.\.venv\Scripts\python.exe -m pip check` → `No broken requirements found`。
- 全量测试初次出现的 1 个失败是 pipeline trace fixture 调用本机 Ollama `/api/chat` 得到 404；该测试实际验证检索 trace 阶段，已将 fixture 明确设为 offline。真实 Ollama 仍由显式 integration 测试单列，未把该环境问题隐藏成产品质量结论。

R1 的上述工程缺口已有当前证据，可以关闭；但这不等于 M9 或总体交付完成。Golden 仍为空、frozen split 仍不存在、根目录 LICENSE 仍缺失，正式 benchmark 尚未运行。
