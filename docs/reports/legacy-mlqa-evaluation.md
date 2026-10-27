# 旧版 MLQA 指标存档

2026-10-27 从早期 README 整理。原文未固定完整运行日期、代码/语料身份或模型 digest；本次没有重跑这些数字。当前说明见[README](../../README.md)。

旧文记录：MLQA.en.zh 取 100 条，按唯一 context 去重为 80 篇文档，按所属文档作为检索目标，旧命令为 `python -m scripts.run_eval data/raw/mlqa_en_zh.jsonl 10`。

| 指标 | dense_only | hybrid |
|---|---|---|
| Hit@10 / Recall@10 | 0.94 | 0.94 |
| MRR | 0.86 | 0.86 |
| faithfulness token 覆盖代理 | 0.11 | 未记录 |
| citation_support 代理 | 0.11 | 未记录 |
| refusal_rate | 0.45 | 未记录 |

这些是旧文本报告的数值，没有在本次验证。0.11 不等于真实忠实度，0.45 不证明拒答有效性；raw reranker 分数不能作为概率。旧文“显著增强反幻觉”“0–1 相关性分”的结论已从现行介绍移除。数据、模型和配置变化后不可直接复用。
