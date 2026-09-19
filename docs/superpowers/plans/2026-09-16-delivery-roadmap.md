# RAG-Forge 后续交付执行计划表

> **For agentic workers:** 执行时使用 superpowers:executing-plans，按任务逐项验证；涉及代码修复先使用 systematic-debugging 与 test-driven-development。本文件是规划，不代表已执行。

**Goal:** 在保留用户现有工作和数据的前提下，完成可信评测、持久化运行验收和可复现交付，明确区分“本地可用”与“允许正式发布”。

**Architecture:** 保留现有 Python/FastAPI、混合检索、重排、Ollama 和 Qdrant 架构。先建立真实人工审核数据，再校准并冻结配置，最后用独立测试集验收；运行配置、索引身份和评测结果必须一一对应。

**Tech Stack:** Python >=3.10、FastAPI、Pydantic、NumPy、BM25、Qdrant、Ollama、可选 sentence-transformers/PyTorch、pytest、Windows PowerShell、Docker Compose。

**Spec:** `RAG-Forge_本地RAG项目改造执行计划.md`；`docs/superpowers/plans/2026-09-12-product-readiness-audit.md`；`docs/RELEASE.md`；用户本轮“规划下后续，制定计划表”。

## Global Constraints

- 稳定性 > 正确性 > 可维护性 > 简洁性；不扩展技术栈，不进行大规模重构或全量依赖升级。
- 当前工作树有大量修改和未跟踪文件，均视为用户资产；不自动提交、暂存、覆盖或删除。
- 不删除数据库、语料、索引、迁移、许可证、模型缓存和用户配置；不输出密钥。
- AI 预审不能冒充真人审核；不代填审核身份、版权归属或许可证事实。
- 只在 calibration 集调参，test 集不得用于选择模型、阈值或分块参数。
- 本地验收不等于正式发布；输入门禁 READY 不等于质量、安全和法律验收通过。
- 制定计划时仅新增规划文件；执行阶段按授权逐项推进，不自动切换运行配置或启动发布。

## 一、当前基线与证据范围

2026-09-16 已读取现有发布清单、验收报告、release 配置和相关脚本，并检查 Git 状态。

| 项目 | 当前认识 | 后续处理 |
|---|---|---|
| 主体工程 | 历史报告记载 M0–M8 已有实现及验收，M9 部分完成，M10 为限定范围工程验收 | 不重做全部工程；R1 核对，R8 对最终快照复验 |
| 自动化质量 | 历史记录为 224 passed、2 skipped，覆盖率 83%；不是本轮复测结果 | R8 重新执行并明确跳过原因 |
| Golden | `benchmarks/golden.jsonl` 当前仅 1 字节；冻结 split 缺失 | R2 是质量验收关键路径 |
| 许可证 | 根目录 LICENSE 缺失，pyproject 声明 MIT 不足以确认权利归属 | R3 并行确认，禁止自动编造 |
| 评测配置 | release 配置为 qdrant_local、2200/200；历史候选 server 索引为 800/100 | R1 建立身份记录，R4 比较并冻结，不能混用结果 |
| 默认运行 | 历史记录中的默认配置尚未切到候选持久化索引 | R7 先读取当前状态确认，避免基于旧记录覆盖 |
| 发布状态 | 现有报告为 PARTIAL / 不发布 | 只有独立门禁有证据后才能更新 |

不能据此给出精确完成百分比：工程任务数量不等于产品验收权重，真实问答质量尚无正式结果。

## 二、总计划表

工期为工作量估算，不是承诺；模型运行、下载、硬件能力与人工响应会影响日历时间。可并行项重叠后，预计约 **4–7 个工作日**，不含等待权利确认与异常修复。

| 编号 | 优先级 | 工作包 | 前置依赖 | 负责人 | 预计工作量 | 交付物与退出条件 |
|---|---|---|---|---|---|---|
| R1 | P1 | 基线、评测命令及身份一致性核对 | 无 | 助手 | 0.5 天 | 基线清单；明确索引/模型/配置身份；相关回归通过 |
| R2 | P1 | 100 题真实审核及 20/80 冻结 | R1 数据核对 | 助手整理、用户审核 | 0.5–1.5 天；人工约 3–5 小时 | 100 条有效审核记录，20 calibration / 80 test，无泄漏 |
| R3 | P1，发布阻塞 | 许可证及分发边界确认 | 可立即并行 | 用户确认权利，助手落实 | 工程 0.25–0.5 天，等待另计 | 正确许可证、元数据一致、第三方分发清单 |
| R4 | P1 | 校准检索、分块和拒答策略 | R1、R2 | 助手 | 0.5–1 天 | calibration 比较结果、冻结配置与身份清单 |
| R5 | P1 | 正式独立测试集评测 | R4 | 助手 | 0.5–1.5 天，视硬件 | 三种检索与两种生成模型的可追溯结果；无降级冒充 |
| R6 | P1 | 答案人工评审及性能判定 | R5，可分批衔接 | 助手汇总、用户评分 | 0.5–1 天；人工约 2–4 小时 | 正确性、引用、拒答、延迟报告；失败项明确归档 |
| R7 | P1 | 持久化运行、备份恢复与切换验收 | R4，正式切换需 R5/R6 通过 | 助手；用户确认目标配置 | 0.5 天 | 重启可用、隔离恢复成功、可回滚、不损坏旧索引 |
| R8 | P1 | 最终回归、安全、打包及有限清理 | R5–R7；发布需 R3 | 助手 | 0.5–1 天 | 同一快照的门禁证据；逐文件清理记录或无删除说明 |
| R9 | P2 | 验收归档和交付说明 | R8；正式发布需 R3 | 助手 | 0.25 天 | 最终验收表、已知限制、启动/恢复说明、发布判断 |

关键路径：R1 → R2 → R4 → R5 → R6 → R7 → R8 → R9。

并行路径：R3 可与 R1–R7 并行；R7 的备份准备可与 R5 并行，但不提前更换默认运行版本。

## 三、任务明细与验收方法

2026-09-16 执行进度：R1 部分完成，R2 首批材料已准备；详见 `docs/reports/R1-readiness-2026-09-16.md`。未完成项不得以回归通过替代。

### R1：建立可复现基线，消除评测歧义

**文件：** 读取 `pyproject.toml`、`configs/experiments-release.yaml`、`scripts/run_benchmark.py`、`scripts/review_benchmark.py`、`docs/RELEASE.md`；按实际发现小幅修正 `benchmarks/README.md`；更新 `docs/reports/final-acceptance.md` 的基线说明。

**输入 / 输出：** 输入现有工作树与历史报告；输出当前快照标识、配置身份、可执行评测命令。R2/R4 不得跳过该身份核对。

- [ ] 运行 `git status --short`、`git diff --stat`，记录当前改动边界；Git 提交号不能单独代表脏工作树，另记录评测相关文件哈希。
- [ ] 对照原始计划逐项核对 M0–M10，区分已实现、历史验证、待本轮验证、缺失；若发现新的 P0/P1，先记录范围和依赖，不默认扩大开发。
- [ ] 记录 Python/依赖版本、模型 tag/digest、语料快照、manifest、分块参数、Qdrant 模式和 collection；不展示密钥或完整环境配置。
- [ ] 确认 release 的 2200/200 与候选索引的 800/100 是不同实验身份；保持独立 collection/path/manifest，不通过改 manifest 冒充重建。
- [ ] 核对 runner 的索引隔离、重复运行、断点恢复和过期 checkpoint 检查；发现缺陷先加失败用例，再最小修复。
- [x] 核对审核进度是否绑定题目内容；修改过问题/答案/来源的题目必须重新审核，旧 accept 不能自动沿用。已补内容哈希与 5 个回归用例。
- [x] 修正正式生成评测示例：必须带 `--split`，明确 calibration/test；正式评测不带 `--allow-candidate` 或 `--limit`。
- [x] 执行以下限定回归；本轮修复后 38 passed，全量 229 passed、2 skipped。

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_benchmark.py tests/test_benchmark_review.py tests/test_index_identity.py tests/test_release_gate.py
```

**验收：** 配置身份无混淆，限定回归通过；当前不具备运行环境时标记 NOT_RUN 并列缺失条件，不沿用历史 PASS。

### R2：分五批完成 Golden 审核

**文件：** `benchmarks/candidates.jsonl`、`benchmarks/review-progress.jsonl`、`benchmarks/golden.jsonl`、`benchmarks/golden-split.json`、`benchmarks/README.md`。

**输入 / 输出：** 输入候选题和语料；输出 100 条真实审核题目及绑定内容哈希的 20/80 split。

- [ ] 按每批 20 题展示问题、预期答案、来源路径与关键证据；先由助手标记歧义、来源缺失和近重复。
- [ ] 用户逐题选择通过、修改或拒绝；记录真实审核人和时间，不自动批量接受。
- [ ] 拒绝题补充替代题，修改题重新审核；保留审计轨迹，避免覆盖已有人工判断。
- [ ] 检查七类覆盖：基础20、定义15、关键词15、改写15、跨语言15、跨文档10、不可回答10；需要调整分类时显式说明原因。
- [ ] 可回答题验证证据确实支持答案；不可回答题验证当前语料缺乏充分依据，不强行添加来源。
- [ ] 冻结前检查近重复、同一问题改写和同源模板泄漏；不可仅依赖完全相同字符串检测。
- [ ] 使用现有交互审核工具导出；审核人由实际参与者提供，不能使用虚构占位姓名。

```powershell
.\.venv\Scripts\python.exe -m scripts.review_benchmark --help
# 在有真实审核人身份后，通过 --reviewer 参数执行交互审核；完成后使用 --freeze-split。
.\.venv\Scripts\python.exe -m pytest tests/test_benchmark_review.py tests/test_benchmark.py
```

- [ ] 冻结 20 calibration / 80 test，记录数据哈希和类别分布。测试集不得提前用于试验选择。

**验收：** 100 题均有真实有效审核记录；来源可访问，split 无重叠且哈希有效；题目质量审核不能由 schema 校验替代。

### R3：确认权利与分发范围

**文件：** 经权利人确认后创建 `LICENSE`；同步 `pyproject.toml`、`README.md`、`docs/RELEASE.md`。

**输入 / 输出：** 输入用户确认的权利归属、许可选择和分发范围；输出可核验法律文本与第三方清单。此任务不阻塞本地校准。

- [ ] 用户确认是仅个人本地使用、团队内部交付还是公开发布，并确认自己是否有权授权全部项目代码。
- [ ] 用户确认许可证、版权主体与年份；不能从作者字段自动推定这些事实。
- [ ] 分别列出代码依赖、模型、语料、静态资源的来源与许可；公开分发前核验官方许可条款，不把代码 MIT 推及所有资源。
- [ ] 在获得事实后补全 LICENSE 并同步元数据；未确认时保留发布阻塞，仍可继续本地评测。

**验收：** 文件内容、元数据和用户确认一致；缺少授权的第三方内容不进入分发包。非空文件检查不代表法律合规。

### R4：仅使用 calibration 校准并冻结

**文件：** `configs/experiments-release.yaml`、`docs/reports/M9-benchmark.md`；结果输出 `data/reports/release-calibration-*.json`，不默认提交私有内容。

- [ ] 先固定语料与 embedding 模型 digest；记录 CPU/GPU、内存、并发、模型预热状态。
- [ ] 在独立索引中比较现有 800/100 与 release 2200/200 分块配置，不覆盖现有可用索引。
- [ ] 比较 dense、hybrid、hybrid_rerank；记录重排加载成功与否、质量收益和时间成本。
- [ ] 校准拒答阈值；将可回答误拒与不可回答漏拒分开，不能只优化一个指标。
- [ ] 仅依据 calibration 结果选择配置、模型和阈值；冻结配置、manifest、模型 digest 与数据哈希。

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments-release.yaml --split benchmarks/golden-split.json --split-partition calibration --experiment retrieval --output data/reports/release-calibration-retrieval.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments-release.yaml --split benchmarks/golden-split.json --split-partition calibration --experiment chunking --output data/reports/release-calibration-chunking.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments-release.yaml --split benchmarks/golden-split.json --split-partition calibration --experiment generation --checkpoint data/reports/release-calibration-generation-checkpoint.jsonl --output data/reports/release-calibration-generation.json
```

**验收：** 所有选择都有 calibration 证据；真实模型不可用时停止该实验，不用 deterministic/offline 结果替代。若现有 chunking runner 的比较组不覆盖上述参数，先小幅补齐配置能力和测试，再运行，不能伪称已比较。

### R5：执行正式 test 评测

**文件：** 冻结后的 `configs/experiments-release.yaml`；`data/reports/release-test-*.json`；`docs/reports/M9-benchmark.md`。

- [ ] 验证配置、数据与模型哈希未变；test 使用与 calibration 不同的输出和 checkpoint。
- [ ] 对 80 道 test 题运行三种检索模式；分别记录 Hit、Recall、MRR/nDCG 和失败样本。
- [ ] 对配置中的两种真实生成模型执行答案生成；记录实际完成数量、超时、错误、引用和拒答。

```powershell
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments-release.yaml --split benchmarks/golden-split.json --split-partition test --experiment retrieval --output data/reports/release-test-retrieval.json
.\.venv\Scripts\python.exe -m scripts.run_benchmark --dataset benchmarks/golden.jsonl --config configs/experiments-release.yaml --split benchmarks/golden-split.json --split-partition test --experiment generation --checkpoint data/reports/release-test-generation-checkpoint.jsonl --output data/reports/release-test-generation.json
```

- [ ] 确认没有候选数据放行、截断题目、静默 reranker 降级或过期 checkpoint 混入。
- [ ] 若 test 不达标，保留本次 FAIL；新一轮改进只能使用 calibration/训练证据，必要时另建未见测试集，不能反复调到旧 test 通过。

**验收：** 报告完整、可追溯、可恢复；评测执行成功与质量达标分别判定。

### R6：人工答案评审和性能验收

**文件：** `docs/reports/M9-benchmark.md`、`docs/reports/final-acceptance.md`；逐题评分保存在本地评测结果目录。

- [ ] 助手整理每题的答案、引文与来源片段；隐藏模型标签进行人工评审，避免偏好影响。
- [ ] 人工分别判断正确性、证据支持、遗漏、虚构及拒答是否合理；有争议的题目保留理由，不由助手自动改成通过。
- [ ] 两模型若各生成 80 题，则报告应覆盖最多 160 份答案；缺失答案算失败或单列，不能悄悄缩小分母。
- [ ] 延迟区分冷启动/热启动、检索/首 token/完整生成、成功/超时；至少 30 次热检索，生成优先使用全部正式样本。
- [ ] 按下面预先冻结的验收目标判定；若原始需求另有明确指标，R1 核对后优先使用原始要求并记录差异。

| 指标 | 建议验收目标（不是当前结果） | 计数约定 |
|---|---|---|
| Hit@5 | >= 0.80 | 可回答 test 题；报告分子/分母 |
| Recall@5 | >= 0.80（原始需求目标） | document_id 去重口径；低于目标如实报告 |
| Recall@10 | >= 0.90（原始需求目标） | document_id 去重口径 |
| MRR | >= 0.70（原始需求目标） | 报告实际使用的截断 K；优化争取 0.75 |
| 不可回答拒答召回 | >= 0.90 | 不可回答 test 子集；同时报告样本数 |
| 可回答误拒率 | <= 0.20 | 可回答 test 子集 |
| 引用有效率 | 100% | 已给出的引用能定位；另统计应该引用却未引用的答案 |
| 答案正确且有证据支持 | >= 0.80 | 人工评分，不以字符串匹配替代 |
| 热检索 p95 | 建议 <= 2 秒 | 固定硬件、配置与单请求并发条件 |
| 完整生成 p95 | 建议 <= 120 秒 | 固定模型、上下文与输出长度；超时不从统计中抹去 |

**验收：** 分开报告各模型、各类别和配置；小样本类别给出分子/分母并说明不确定性，不能将少量样本概括为稳定生产质量。

### R7：持久化切换与恢复验收

**文件：** 本地 `.env`（敏感，不提交）、`docs/LOCAL-SETUP.md`、`docs/INDEX-MIGRATION.md`、`docs/BACKUP-RESTORE.md`、`docs/reports/M10-acceptance.md`。

- [ ] 读取当前运行 profile，确认是否仍需切换；列出目标 Qdrant 地址、collection、manifest、模型与分块身份，获得用户对目标的确认。
- [ ] 备份原配置和必要数据，记录备份位置与恢复方法；保留旧 collection，不直接清空重建。
- [ ] 若 R4 胜出参数不同于现有候选索引，创建新 collection 并完整摄入、校验，不只修改参数标签。
- [ ] 在隔离实例/collection 恢复备份，比较文档/点数、抽样检索和 manifest；备份文件存在不等于恢复成功。
- [ ] R5/R6 达标后切换目标 profile，检查健康、检索、引用、拒答和增量更新；重启 API 再验证。
- [ ] 演练恢复原配置；若新版本失败立即回到已知可用配置，并保留诊断数据。

**验收：** 当前运行身份与验收配置一致，重启后数据可用，恢复路径实测成功，无用户数据丢失。

### R8：最终门禁、回归和小批量清理

**文件：** `tests/`、`scripts/verify_browser_e2e.ps1`、`scripts/verify_compose_recovery.ps1`、`docs/RELEASE.md`、`docs/reports/project-audit.md`、`docs/reports/final-acceptance.md`。

- [ ] 在最终配置和代码快照执行下面门禁，逐条保留命令、退出码、时间和环境；缺少工具先记录，不自动升级整套依赖。

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
powershell -NoProfile -File scripts/verify_browser_e2e.ps1
powershell -NoProfile -File scripts/verify_compose_recovery.ps1 -RunRecreate
.\.venv\Scripts\python.exe -m scripts.release_gate --json
```

- [ ] 真实 Ollama/Qdrant 集成测试单列；Compose 演练使用脚本的隔离项目，不停止用户已有服务。
- [ ] 核验安装包包含必要静态资源、不含 `.env`、私有语料、向量数据和密钥；用隔离环境执行安装与启动检查。
- [ ] 联网依赖审计记录日期、工具版本与数据库来源；确认高危问题实际适用性，不虚报零风险。
- [ ] 复核 loopback、非 loopback 鉴权、Host 白名单、路径与请求体限制、trace 访问和日志脱敏；记录真实测试证据。
- [ ] 清理前逐文件检查 Git、静态/动态引用、构建和测试；用户未提交及未跟踪开发文件不自动删除。
- [ ] 仅清理已验证可再生且无用户价值的 A 级产物，每批可恢复、清理后立即验证；B/C 级继续保留并说明证据缺口。不得递归删除工作区根、data 或模型目录。
- [ ] 将每个删除路径、原因、验证证据、等级及恢复方式写入审计报告；无安全候选时明确写“本轮未删除”。

**验收：** 无未解决 P0/P1；门禁不得静默跳过。只有许可证缺失时可标记“本地验收通过 / 正式发布阻塞”，不能整体写 PASS。

### R9：交付归档

**文件：** `README.md`、`docs/LOCAL-SETUP.md`、`docs/RELEASE.md`、`docs/reports/final-acceptance.md`、本计划表。

- [ ] 更新每项 PASS/PARTIAL/FAIL/NOT_RUN，附证据路径、日期、快照和适用范围。
- [ ] 给出普通用户可照做的启动、提问、查看引用、停机、重启、更新语料与恢复步骤。
- [ ] 汇总已修复项、已删除项、保留疑似文件、P0–P3 未完成项；不将文档完成算作功能通过。
- [ ] 列出运行配置、数据/索引/模型身份和已知硬件限制；私有数据不进入公开文档。
- [ ] 明确结论：本地交付通过、带限制交付或不通过；正式发布单独判断。不自动 push、建 PR 或上传制品。

**验收：** 新使用者按说明能复现已验收路径，所有未完成项有负责人、条件和下一步，不以笼统完成率收尾。

## 四、建议排期与用户参与

| 时间窗口 | 主线 | 可并行事项 | 用户参与 |
|---|---|---|---|
| 第 1 天 | R1；准备 R2 第一批 20 题 | R3 确认用途与版权 | 审核第一批、确认分发范围 |
| 第 2–3 天 | R2 剩余题目、冻结；开始 R4 | R7 备份方案准备 | 完成题目审核 |
| 第 3–4 天 | R4 冻结、R5 正式运行 | R3 文本落实、R6 分批整理 | 对已生成答案评分 |
| 第 4–6 天 | R6、R7、R8 | 文档校对 | 确认目标配置与争议答案 |
| 第 6–7 天 | 异常修复缓冲、R9 | 无额外功能扩展 | 阅读最终验收结论 |

这是相对排期：人工审核未完成时后续时间顺延；不能通过伪造审核、复用过期 checkpoint 或缩小测试集赶进度。

## 五、执行停止条件与范围控制

- 发现可能破坏数据、需要变更公开 API 或扩大依赖/架构：先说明影响与选项，不直接实施。
- 机器缺模型、磁盘不足或服务不可达：给出实际诊断和最小修复步骤，保留 checkpoint，不无限重试。
- 等待人工时，只继续独立的基线、文档或备份准备；不反复刷新相同门禁制造进度。
- 本轮不新增 UI 大改、多租户、云部署、Agent 编排等功能；这些属于验收后的独立产品迭代。
- 下一步推荐在当前任务中按 R1 开始，同时准备 R2 第一批；不必另建任务。实施前读取原始需求与本计划，以真实结果勾选复选框。
