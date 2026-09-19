# RAG-Forge 后续推进计划（2026-09-19）

> **For agentic workers:** 后续使用 superpowers:executing-plans 在当前任务逐项推进。修复遵循先复现、再测试、再最小修改；本轮仅规划，不执行实现。

**Goal:** 收尾 R1 的评测可信性缺口，完成真实 Golden 审核，再进入正式评测与本地交付。

**Architecture:** 保留现有架构；按实验身份隔离索引，统一审核、split、checkpoint 与发布门禁的数据身份检查。人工审核和工程修复并行，正式评测串行依赖两者完成。

**Tech Stack:** Python、pytest、Qdrant local/server、Ollama、FastAPI、PowerShell。

**Spec:** `2026-09-16-delivery-roadmap.md` 为总体交付计划；`../../reports/R1-readiness-2026-09-16.md` 为已执行证据；根目录 `RAG-Forge_本地RAG项目改造执行计划.md` 为原始需求。本文件细化下一批安排，不替代旧报告。

## Global Constraints

- 不删除用户数据、旧索引或当前未提交文件；不自动提交、切分支、切换默认配置或发布。
- 不新增大型功能，不扩展技术栈；只处理已确认的评测与交付缺口。
- 不代填真人审核或版权身份。AI 整理、预审和人工接受分别记录。
- 只在 calibration 集调参；test 结果不达标时保留真实结果。
- 229 passed、2 skipped 是 2026-09-16 的结果，本轮未重跑测试，不作为当前全量验收。

## Review Focus

1. 同一语料、不同分块大小/overlap 不应共享持久化索引；由 A1 临时 Qdrant 测试覆盖。
2. 同一配置但语料删改后，不应残留旧文档或混用 checkpoint；由 A1/A3 测试覆盖。
3. 题目 ID 不变但问题、答案、来源变化，旧 split 应拒绝；由 A2 参数化测试覆盖。
4. 调整重排模型或候选数量，旧 checkpoint 不应继续复用；由 A3 参数化测试覆盖。
5. 旧版/损坏的 split 或 checkpoint 应给出可操作错误，不覆盖原文件；由 A2/A3 测试覆盖。

## 一、工作顺序

| 顺序 | 对应原计划 | 工作内容 | 验收出口 | 估算 |
|---|---|---|---|---|
| A1 | R1 | 分块实验隔离，显式支持 800/100 与 2200/200 | 临时真实 Qdrant 上各组独立、重复运行不混入旧语料 | 0.5–1 天 |
| A2 | R1 | split 绑定完整题集内容，统一三处校验 | 修改同 ID 题目后 runner 和 gate 都拒绝旧 split | 0.5 天 |
| A3 | R1 | checkpoint 检索参数校验与整体验证 | 参数变更拒绝恢复；同配置正常恢复；回归通过 | 0.5 天 |
| B1 | R2 | 重写候选题并准备五批审核包 | 每题问题具体、答案可验证、有来源；仍标 candidate | 与 A 并行，0.5–1 天 |
| B2 | R2 | 真人审核 100 题、冻结 20/80 | 完整审核记录、类别覆盖、无近重复泄漏 | 依赖用户，约 3–5 小时 |
| C1 | R4 | 校准分块、检索、拒答与模型 | 仅使用 20 题校准，冻结配置和身份 | 0.5–1 天 |
| C2 | R5/R6 | 80 题正式评测、人工评分与性能报告 | 三种检索、两种生成；分母/失败/跳过完整 | 1–2 天及人工评分 |
| D1 | R7/R8/R9 | 恢复演练、配置切换、最终回归与交付 | 本地可复现；备份可恢复；安全/构建有证据 | 1–2 天 |
| L1 | R3 | 权利、许可证与分发范围 | 用户确认事实后补全文本；否则不对外发布 | 并行，等待另计 |

整体估算约 5–8 个工作日，取决于模型速度和缺陷修复，不含人工等待；不是固定交付日期。先按 A1–A3 两天左右的小批次执行和复核，不先启动全量模型实验。

## 二、下一批工程任务

### A1：分块实验独立索引

状态：已完成。独立 path/collection/manifest、显式 variants 和临时 Qdrant local 隔离测试均已验证。

文件：`scripts/run_benchmark.py`、`configs/experiments-release.yaml`、`tests/test_benchmark.py`；新增 `tests/test_benchmark_isolation.py` 承载临时 Qdrant 集成用例。

输入：实验配置、语料身份、分块参数。输出：每组独立的 path/collection/manifest，以及可追溯结果。

- [ ] 在 pytest `tmp_path` 下用 deterministic embedding 和真实 Qdrant local，复现先写一种分块参数、再运行另一组时的冲突；禁止访问用户现有索引。
- [ ] 将比较组显式配置为参数对，至少包含下列两组；保留现有配置未声明比较组时的可解释兼容行为。

```json
"chunking": {
  "variants": [
    {"chunk_size": 800, "chunk_overlap": 100},
    {"chunk_size": 2200, "chunk_overlap": 200}
  ]
}
```

- [ ] 给实验索引使用稳定的配置/语料身份命名；不同身份不共用 path、collection 或 manifest。不要改旧 manifest 冒充重建，也不要清空用户 collection。
- [ ] 验证三类实际行为：两组可连续运行；同身份重跑点数不膨胀；语料删改后新实验不会检索到旧文档。
- [ ] 验证异常后资源已关闭，临时 Qdrant 可重新打开；非法 overlap、重复参数组在写入前报错。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_benchmark_isolation.py tests/test_index_identity.py tests/test_qdrant_persistence.py
```

出口：真实临时存储的测试通过，而不只是比较路径字符串。

### A2：冻结题集内容校验

状态：已完成。split schema 2、题集内容摘要以及 reviewer/runner/release gate 三处一致性检查均已验证。

文件：`scripts/review_benchmark.py`、`scripts/run_benchmark.py`、`scripts/release_gate.py`、`src/ragforge/evaluation/benchmark.py`；测试 `tests/test_benchmark_review.py`、`tests/test_benchmark.py`、`tests/test_release_gate.py`。

输入：审核后的原始 JSON 行（包括 source_refs）。输出：绑定内容的新 split；review、runner、gate 采用相同身份规则。

- [ ] 先加入行为测试：保持 ID 不变，分别修改 question、expected_answer、source_refs、corpus_identity，旧 split 必须失效。
- [ ] 在公共 evaluation 模块统一内容规范化与哈希规则，避免在三处复制实现；原始来源字段不得在转换 BenchmarkCase 时丢失校验机会。
- [ ] split 升级版本并带完整题集内容摘要；题集顺序变化可按明确规则规范化，但内容变化不得被忽略。
- [ ] runner 和 release gate 同步识别新协议。旧版 split 不静默放行，提示重新冻结；不得自动补哈希伪造旧审核证据。
- [ ] 测试重复 ID、重叠分区、缺失题、损坏哈希、旧版文件均拒绝；失败不覆盖 Golden/split；合法 20/80 分区正常加载。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_benchmark_review.py tests/test_benchmark.py tests/test_release_gate.py
```

出口：三个入口针对同一修改都得到一致结果，不能只有 UI 或导出端检查。

### A3：断点恢复身份与 R1 收尾

状态：已完成。检索/重排/生成 top-k 与索引存储身份已纳入 checkpoint identity；全量回归、Ruff、pip check 均已验证。

文件：`scripts/run_benchmark.py`、`tests/test_benchmark.py`、`benchmarks/README.md`、`docs/reports/R1-readiness-2026-09-16.md`。

- [ ] 列出所有影响证据与生成的参数，核对 checkpoint 当前覆盖范围；重点验证 dense_top_k、sparse_top_k、rerank_candidate_k、rerank_top_k、rerank_model 与生成 top_k。
- [ ] 对每种变化写参数化测试：保存旧 checkpoint 后改变一项，恢复必须拒绝；完全相同身份可恢复且不重复生成已完成答案。
- [ ] 将缺失契约加入身份，保留原 checkpoint 文件；旧 checkpoint 给出新建文件的提示，不自动改写。
- [ ] 检查证据 cache 与身份校验顺序，不能先复用旧答案再发现证据变化。
- [ ] 跑限定回归和全量回归、Ruff；记录实际命令和结果，不预先写通过数。

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check scripts src tests
.\.venv\Scripts\python.exe -m pip check
```

- [ ] 更新 R1 报告：上述缺口全部有证据后才能关闭 R1；历史 M0–M10 集成证据仍保留原日期。

## 三、人工评测如何降低操作负担

- 助手先把第一批 20 题改成具体问题，补齐答案要点和对应原文；替换大会宣传、空泛评价与章节过渡语题目。
- 使用独立修订候选文件保留原始候选；未经用户审核的修订不能直接进入 golden。
- 每次只让用户处理一批，不要求操作命令。回复格式为“题号：通过 / 修改意见 / 拒绝原因”，由助手整理为可核对记录。
- 五批完成后检查七类覆盖、重复/近重复和来源，再冻结 20/80。首批基础题不能代表全题集已合格。
- 两模型生成后，助手匿名整理答案和来源供人工评分；AI 预评分不能冒充人工正确率。

## 四、评测与交付边界

正式命令沿用总体计划 R4/R5，必须指定 frozen split 和 calibration/test 分区。A1–A3 完成后先用小型合成语料验证工具，不用候选真实题集的分数选最终参数。

原始质量目标：Recall@5 >=0.80、Recall@10 >=0.90、MRR >=0.70、引用有效率 100%。低于目标保留真实结果与原因，不修改文档假装通过；人工正确性、误拒和性能另外报告。

本地交付验收包括持久化重启、备份恢复、模型切换、引用/拒答、浏览器、构建与安全检查；许可证和第三方分发范围作为正式对外发布的独立门禁。

## 五、本次规划核对范围

2026-09-19 读取总体计划和 R1 报告，并核对 runner/reviewer 文件哈希与关键函数位置；A1、A2、A3 已执行完成。全量 pytest 为 243 passed、2 skipped，Ruff 和 pip check 通过。A1 使用临时 Qdrant local 做了实际隔离验证；A2 已将 split 升级到 schema 2 并绑定题集内容摘要；A3 已把检索和生成 top-k 等参数纳入 checkpoint identity。本次没有重建用户索引、切换默认配置或启动正式 benchmark；B1/B2、C1/C2、D1、L1 仍未完成。

建议保持当前任务内逐项执行，每完成 A1/A2/A3 一项就给出修复、测试、剩余风险；不为了进度重复生成同类报告或扩大重构范围。
