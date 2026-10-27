# M9 阶段报告：Golden Set 与可复现实验基础设施

日期：2026-09-12

## 结论

M9 的数据集治理和实验框架已落地，并用当前本地处理语料完成了 provisional 管线试运行；M9 的最终 Gate 尚未完成。原因是 `golden.jsonl` 仍为空，100 条题目目前全部是 `candidate`，没有人工审核者可以代签 Golden Set。真实 Ollama 双模型已完成候选样本采样，但样本仍未人工审核，不能升级为正式质量结论。

## 数据集状态

- 当前语料：`data/processed/web`，332 个 markdown/text 文档；按当前 `heading-window-v2` 分块配置生成 5,042 个 chunk。此前 5,240 个 chunk 是旧 schema 1 快照，不按当前代码复用。
- 候选集：[candidates.jsonl](../../benchmarks/candidates.jsonl)，共 100 条，分布为基础 20、定义 15、关键词 15、改写 15、跨语言 15、跨文档 10、无答案 10。
- 每条候选含唯一 ID、问题、`expected_doc_ids`、答案、类别、`review_status`、来源路径、corpus identity 和 index identity。
- `benchmarks/golden.jsonl` 已预留但为空；评测脚本默认要求 `review_status: reviewed`，只有 `--allow-candidate` 才允许 provisional 试运行。
- 校验已覆盖 ID/问题去重、文档 ID 存在性、answerable 与 `expected_doc_ids` 一致性、类别和人工审核字段；审核工具会在受限扫描范围内优先定位答案或问题中的章节标题，降低长文核对成本。
- 语料扩充后已重新生成候选集，避免沿用旧 corpus identity。本轮只读结构预审：100/100 条来源文件存在，100/100 条文档 ID 合法，answerable/expected_doc_ids 约束错误 0，重复问题 0，类别分布仍为 20/15/15/15/15/10/10；90 条可回答题中 21 条答案可逐字在来源中找到。其余 69 条可能是摘要或改写，字符串不完全相等不能判定错误，仍需人工确认语义完整性。

## provisional 检索实验

结果文件：`data/reports/m9-candidate-retrieval.json`（本地历史产物，不随仓库分发）。使用 deterministic embedder 和独立 in-memory store，不能解释为真实 embedding 模型成绩。

| 模式 | Hit@5 | Recall@5 | MRR | 状态 |
|---|---:|---:|---:|---|
| dense | 0.011 | 0.006 | 0.004 | 100 条成功运行 |
| hybrid | 0.878 | 0.833 | 0.417 | 100 条成功运行 |
| hybrid_rerank | — | — | — | 100 条均明确记录 reranker 不可用 |

answerable 分母为 90；无答案题单列。请求 top-k=10 时每条返回 10 条，`returned_count` 和短返回数均已保存。以上分数只用于验证评测链路，不用于产品宣传或 M9 Golden 结论。

延迟也已拆分保存：当前 332 文档 corpus 下，hybrid 首条冷启动约 38.865 ms，预热后 p50/p95 约 38.520/51.318 ms；dense 首条约 27.719 ms，预热后 p50/p95 约 26.390/32.120 ms。这些是 deterministic/in-memory 管线的工程耗时。

## provisional 生成实验

结果文件：`data/reports/m9-candidate-generation.json`（本地历史产物，不随仓库分发）。证据先按 hybrid 检索一次并按题保存 hash，切换两个请求模型时复用同一证据缓存，没有重复检索。配置后端是 `offline`，所以实际回答模型字段为 `offline`，不是本地 Gemma；这验证了隔离、引用、拒答和失败记录逻辑，但不是生成质量评测。

两组均为 100/100 成功执行；离线代理的引用合法率均值为 0.25，answerable 题有引用覆盖率为 0.167。拒答混淆矩阵和逐题预测均在 JSON 中保存，未运行或失败项不会从分母删除。

## 真实 Ollama 生成采样

结果文件：`data/reports/m9-candidate-generation-ollama-20.json`（本地历史产物，不随仓库分发）。该次运行使用 `configs/experiments-ollama.yaml`、本地 Ollama 的 `gemma3:4b` 与 `gemma4:e4b`，从旧的 116 文档候选快照取前 20 条；两模型均为 20/20 `ok`，实际模型字段与请求模型一致。因为数据集是旧 `candidate` 快照，输出明确标记 `provisional: true`，不能作为当前 corpus 或 Golden 指标；正式审核后必须重新运行。

| 模型 | TP | TN | FP | FN | 引用合法率均值 | answerable 引用覆盖率 | 冷启动 ms | 预热 p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:4b | 2 | 3 | 15 | 0 | 0.150 | 0.167 | 0.94 | 0.10 / 33069.28 |
| gemma4:e4b | 2 | 3 | 15 | 0 | 0.150 | 0.167 | 0.15 | 0.17 / 138633.57 |

这次采样显示当前候选题/检索/拒答组合存在明显的 answerable 误拒答信号（FP=15/15 个模型样本口径中的 answerable 误拒答计数），应先人工核对候选答案与 evidence 是否完整，再决定是数据集问题、检索问题还是拒答阈值问题。模型运行成功不等于回答质量达标；超大的 p95 也应在固定硬件和预热策略下重新测量。

## 本地组件集成验收

- `pytest -q tests/integration --run-ollama`：embedding 集成测试和双模型生成集成测试均通过，实际访问本机 Ollama，未启用网络下载。
- 本机缓存的 `bge-reranker-base`：`Reranker.status()` 返回 available，实际加载并完成一次单候选重排，返回 1 条 `float` 分数，耗时约 14.2 秒。
- 上述是组件可运行证据，不等于在人工 Golden Set 上的质量达标；正式指标仍受 Golden Set 门槛约束。

## provisional chunk 实验

结果文件：`data/reports/m9-candidate-chunking.json`（本地历史产物，不随仓库分发）。每个 chunk size 都重新创建 in-memory store、重新分块和重新摄取；overlap 固定 200。

| chunk size | chunks | Hit@5 | Recall@5 |
|---:|---:|---:|---:|
| 1200 | 3999 | 0.900 | 0.844 |
| 1800 | 3326 | 0.900 | 0.850 |
| 2200 | 3137 | 0.878 | 0.833 |
| 3000 | 2924 | 0.878 | 0.833 |

## 已实现的防错规则

- 检索指标支持按 document_id 去重，避免同一文档多个 chunk 造成排名与 Recall 偏差。
- answerable 题是 Hit/Recall/MRR 的主分母；无答案题单列，不与无 gold 的 Recall 混算。
- 引用合法率区分“未运行”和“运行但零引用”；零引用不会得到 100%。
- 拒答输出 answerable/unanswerable 两侧的 confusion matrix。
- 每题保存状态、证据 ID、证据文本 hash/摘要、模型身份、索引身份、耗时、异常；失败不会静默删除。
- reranker 不可用、返回数量不足和离线后端均在结果中显式记录。
- 生成实验支持逐题原子 checkpoint；checkpoint 会绑定 dataset、corpus/index identity、embedding digest、生成模型 digest 及 temperature/num_predict/seed/timeout，身份变化会拒绝恢复。

## 可恢复执行证据

已用候选数据和 diagnostic/offline 配置完成小样本 checkpoint 冒烟：同一命令连续运行两次，第二次复用已保存题目，不重新生成；checkpoint 中保存了逐题结果和证据 hash。该冒烟只证明恢复机制，不构成质量指标。

正式运行前必须先由人工审核并冻结 `golden.jsonl`，然后使用 `configs/experiments-release.yaml` 和独立 checkpoint；发布报告应保留 checkpoint、输出 JSON、配置、corpus hash 和 provider digest。

## M9 Gate

| 项目 | 状态 | 说明 |
|---|---|---|
| 100 条真实人工确认 Golden Set | PENDING | 当前 100 条均为 candidate，不能代签 |
| 三组实验脚本可复现 | PASS（provisional） | retrieval/generation/chunking 均已运行并保存 JSON |
| 指标单元测试 | PASS | `tests/test_metrics.py`、`tests/test_benchmark.py` |
| 真实 Gemma 生成对比 | PASS（20 条样本，provisional） | `gemma3:4b` / `gemma4:e4b` 均 20/20 `ok`；完整审核 Golden Set 对比仍待执行 |
| 冷启动与预热后 p50/p95 | PASS（provisional） | retrieval/generation/chunking JSON 已分别保存冷启动与预热分位数 |

M9 因人工审核后的 Golden Set 和正式质量口径仍未完成，不能宣布阶段 Gate 通过。下一步应先审核候选题，冻结校准集/最终测试集，再以 `benchmarks/golden.jsonl` 运行不带 `--allow-candidate` 的正式实验。

## 复现命令

```powershell
.\.venv\Scripts\python.exe -m scripts.build_golden_candidates --corpus data/processed/web --output benchmarks/candidates.jsonl
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\candidates.jsonl --config configs\experiments.yaml --experiment retrieval --allow-candidate --output data\reports\m9-candidate-retrieval.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\candidates.jsonl --config configs\experiments.yaml --experiment generation --allow-candidate --output data\reports\m9-candidate-generation.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\candidates.jsonl --config configs\experiments-ollama.yaml --experiment generation --allow-candidate --limit 20 --output data\reports\m9-candidate-generation-ollama-20.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\candidates.jsonl --config configs\experiments.yaml --experiment chunking --allow-candidate --output data\reports\m9-candidate-chunking.json
```

## 本轮执行更新

- 新增 `--checkpoint` 后，候选 diagnostic/offline 2 题冒烟第二次运行的 `resumed_counts` 为 `gemma3:4b=2`、`gemma4:e4b=2`，证明已完成题目不会再次生成。
- 当前 corpus 上另完成 2 题真实 Ollama 双模型试跑；两个模型均 `2/2 ok`，实际模型 digest 和显式生成参数已落盘。该输出仍是 `provisional`，不代表 Golden Set 质量。
- 正式 release 命令已增加 dataset SHA-256、corpus/index identity、embedding digest、generation model digest 和生成参数一致性校验；当前 `benchmarks/golden.jsonl` 为空，因此正式 release benchmark 有意保持未运行。
