# M9 Golden Set 与实验说明

`candidates.jsonl` 是从当前本地已处理技术文档按固定规则生成的 100 条候选题，分布为：基础 20、定义 15、关键词 15、改写 15、跨语言 15、跨文档 10、无答案 10。候选题包含 `corpus_identity`、`index_identity`、来源路径和生成方法，全部标记为 `review_status: candidate`。

`golden.jsonl` 预留给人工审核后的冻结集，目前为空。没有真实审核者、审核时间和审核记录时，评测脚本会拒绝把候选题当作 Golden Set；这不是失败吞掉，而是保护分母和结论真实性。

人工审核时应逐条确认：问题是否自然、答案是否被证据完整支持、`expected_doc_ids` 是否准确、无答案题是否确实不可答、是否存在重复问题或语义泄漏。交互工具会在通过 corpus 路径校验后扫描有限长度的原文，并优先展示 `expected_answer`/问题命中的证据窗口；预览仍有长度上限，不会自动接受题目。通过审核的行复制到 `golden.jsonl`，补齐 `review_status: reviewed`、`reviewer` 和 `reviewed_at`，并保持 corpus/index identity 不变。

## 候选集生成

```powershell
.\.venv\Scripts\python.exe -m scripts.build_golden_candidates --corpus data/processed/web --output benchmarks/candidates.jsonl
```

人工审核与冻结（需要真实审核者在终端逐题输入 `a`/`r`/`d`）：

```powershell
.\.venv\Scripts\python.exe -m scripts.review_benchmark --reviewer "your-name" --freeze-split
```

## 实验规则

- 审核进度通过 `content_sha256` 绑定候选题内容；问题、答案、来源或身份信息变更后必须重新审核。旧版缺少内容哈希的记录保留，但不能直接导出为已审核题；重新运行交互审核即可追加新决策，不要手工补哈希冒充复审。

- 检索指标按 `document_id` 去重，answerable 题单独作为 Hit/Recall/MRR 分母；无答案题单列。
- 每题保存预测、证据、模型、索引身份、耗时和失败/跳过状态。
- 未运行、零引用、模型失败和 reranker 不可用不会伪装成 0% 或 100% 的成功率。
- `--allow-candidate` 只用于管线试运行，输出必须标注 provisional，不能作为 Golden 结果。
- 生成实验支持 `--checkpoint path.json`；每完成一道题就原子写入。恢复时会严格比较 dataset、corpus/index identity、模型 digest 和 temperature/num_predict/seed/timeout，身份变化必须使用新 checkpoint。

`--freeze-split` 会在所有 accepted 行已人工审核的前提下生成带 hash 的 split，并以类别 round-robin 方式为 calibration 集保留各类别覆盖；正式 benchmark 使用 `--split ... --split-partition test`。

真实 Ollama 冒烟采样可以使用：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\candidates.jsonl --config configs\experiments-ollama.yaml --experiment generation --allow-candidate --limit 20 --output data\reports\m9-candidate-generation-ollama-20.json
```

该命令用于验证本地模型通信、实际模型身份、引用/拒答记录和耗时；`--limit 20` 只是成本可控的样本检查。正式结论必须先完成人工审核并写入 `golden.jsonl`，再去掉 `--allow-candidate`，不能用候选样本替代 Golden Set。

可恢复的生成试跑示例：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks\golden.jsonl --config configs\experiments-release.yaml --split benchmarks\golden-split.json --split-partition test --experiment generation --checkpoint data\reports\m9-release-generation.checkpoint.json --output data\reports\m9-release-generation.json
```

该命令要求 `golden.jsonl` 已由真实审核者冻结；中断后用完全相同的命令恢复。`--limit` 只适合 candidate/diagnostic 试跑，release profile 会拒绝采样冒充全量结果。
