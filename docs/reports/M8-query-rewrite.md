# M8 验收报告：可选 Query Rewrite

日期：2026-09-12

## 结论

M8 的可选 Query Rewrite 已实现并完成真实本地模型评估。默认关闭，显式开启后只使用 `qwen3:0.6b` 做检索查询改写；原始问题仍用于最终回答，改写失败会回退原问题并写入 Trace。该阶段没有把改写延迟或“改写成功”误报为检索质量提升，因此不建议默认开启。

## 已完成

- 新增 `src/ragforge/query_rewriter.py`，固定 utility model 为 `qwen3:0.6b`，接口接收当前 query 与有上限的 history，只要求模型输出单条检索查询。
- 新增 `tests/test_query_rewriter.py` 与 `tests/fixtures/rewrite_cases.jsonl`；覆盖关闭路径、超时/不可用、空输出、过长输出、`think`、多行、结构化包装、提示泄漏、新数字和关键实体丢失等回退条件。
- 配置新增 `rewrite_enabled=false`、`rewrite_model=qwen3:0.6b`、输出长度上限和 history 消息上限。
- Pipeline 保留 `original_query` 供生成，仅把 `rewritten_query` 传给检索；Trace 保存改写状态、原因、结果和耗时；改写不触发 reindex。
- API 接收 `rewrite` 与最多 20 条 user/assistant history；页面提供默认关闭的 Query Rewrite 开关，history 只随当前请求发送，不落盘、不跨用户共享。
- 真实模型输出发现了维度表达式 `1024x1024`、模型/版本中的数字边界情况；已将数字安全校验改为检查全部数字片段，并重新运行单元测试和真实样例。

## 真实 20 条样例

评估文件：[m8-rewrite-eval.json](../../data/reports/m8-rewrite-eval.json)。评估使用本机 Ollama 的 `qwen3:0.6b`，比较同一批固定 query 的 OFF/ON 改写路径；样例保留 `expected_doc_ids`，但本次脚本是 rewrite-only 对比，没有把它冒充成独立的向量检索 Recall 实验。

| 指标 | 结果 |
|---|---:|
| 样例数 | 20 |
| 实际改写成功 | 4 |
| 安全回退原 query | 9 |
| 关键实体/错误码/版本/产品名保留 | 20/20 |
| OFF 平均耗时 | 0.003 ms |
| ON 平均耗时 | 1874.842 ms |

回退原因：`new_numeric_fact` 2 条、`prompt_leak` 3 条、`structured_output` 4 条。其余 7 条安全通过但输出与原问题等价，未将“发生调用”算作有收益。

## Gate 对照

| Gate | 结果 | 证据 |
|---|---|---|
| 默认 OFF | PASS | 配置默认值与关闭路径单元测试 |
| ON 可运行 | PASS | 真实 `qwen3:0.6b` 20 条样例 |
| 原 query / rewritten query 分工明确 | PASS | Pipeline 与 Trace 测试 |
| Trace 完整 | PASS | 改写状态、原因、耗时和查询字段均持久于 Trace |
| 失败可回退 | PASS | 单元测试 + 真实回退统计 |
| 关键实体保护 | PASS | 20/20 |
| 延迟与质量如实记录 | PASS | 真实 JSON；没有宣称 Recall 改善 |
| 切换生成模型不改变 rewrite model | PASS | rewrite model 固定配置与 Pipeline 路径 |
| 改写触发 reindex | PASS | 改写仅位于 query path，未调用索引构建 |

## 限制与后续

当前验证证明了接口、隔离、回退和安全约束；它没有证明 Query Rewrite 能提高实际检索指标。若要启用，需要在 M9 的独立 Golden Set 上对 OFF/ON 分别测 Hit@K、Recall@K、MRR、拒答和端到端延迟，并保留失败样本。由于当前 ON 平均耗时约 1.875 秒且回退比例较高，默认保持 OFF。

## 验证命令

```text
.\.venv\Scripts\python.exe -m pytest -q tests/test_query_rewriter.py tests/test_api_models.py tests/test_pipeline.py
.\.venv\Scripts\python.exe -m scripts.run_rewrite_eval --fixtures tests/fixtures --output data/reports/m8-rewrite-eval.json
node --check src/ragforge/api/static/app.js
```
