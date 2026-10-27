# 文档清理与现状同步记录

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

日期：2026-09-19（Asia/Shanghai）

## 范围与保护条件

本轮读取了项目根目录、`docs/`、`benchmarks/`、配置、构建文件、脚本和主要 API/配置源码，并核对了 `git status`、当前分支和最近验证结果。工作树包含大量未提交和未跟踪的用户开发文件，因此没有执行 reset、checkout、commit、批量删除或覆盖 `.env`。

本轮目标是让“入口文档、当前上下文、未完成事项和历史证据”分工清晰，不把历史报告改写成当前结果。

## 文档分类结论

| 分类 | 文件/目录 | 处理 |
|---|---|---|
| 现行入口 | `README.md`、`CONTEXT.md`、`TODO.md` | 保留并同步；`CONTEXT.md`/`TODO.md` 为本轮新增入口 |
| 操作手册 | `docs/LOCAL-SETUP.md`、`docs/DEVELOPMENT.md`、`docs/DEMO.md`、`docs/BACKUP-RESTORE.md`、`docs/INDEX-MIGRATION.md`、`docs/RELEASE.md` | 保留；内容与脚本/配置对应 |
| 评测与验收证据 | `docs/reports/`、`benchmarks/README.md`、`benchmarks/review-batch-01.md` | 保留；按日期和 provisional/PARTIAL 标记使用 |
| 设计与执行历史 | 根目录原始计划、`docs/superpowers/plans/` | 保留；有需求、决策和回滚信息，不能当作当前状态 |
| 辅助材料 | `INTERVIEW_GUIDE.md`、`security_best_practices_report.md`、`docs/images/m7-debug.png` | 保留；分别用于面试演示、安全审计和 UI 证据 |
| 运行/生成物 | `data/`、`build/`、`dist/`、缓存、`.venv/`、`.playwright-cli/`、`output/`、根目录截图 | 本轮不删除；它们未被纳入文档清理范围，且工作树有未提交用户成果 |

## 已执行同步

- 新增 `CONTEXT.md`：记录技术栈、模块职责、入口 API、运行 profile、当前 243 passed/2 skipped 回归基线和发布阻塞。
- 新增 `TODO.md`：汇总真正未完成的人工审核、正式 benchmark、许可证、恢复演练和最终门禁；不重复列已完成阶段。
- 新增 `docs/README.md`：按入口、日常运维、评测、验收和历史材料分类，避免使用者在阶段报告中寻找当前结论。
- README 增加当前状态入口，修正首次安装时保护已有 `.env` 的写法，并在采集命令前明确安装 `collector` extra；补充 Docker base profile 的 API key/生成后端边界。
- 面试指南改为“辅助/历史演示材料”定位，区分 Ollama 默认路径与 API 兼容路径，避免把 raw reranker 分数或旧云端模型写成默认事实。
- 安全审计报告补充复核日期，修正请求体/摄入总量限制和接口描述，去掉易失效的源码行号引用。
- 总体验收表将当前 2026-09-19 回归与 2026-09-12 历史回归分开，避免 226 项历史数字覆盖当前基线。
- 发布清单将门禁阻塞状态更新到当前核对日期。

## 删除与保留决定

本轮删除文件数：**0**。

没有文件满足“既明确可再生、又不属于用户当前开发/验收成果、且没有动态/历史价值”的全部条件。尤其是空的 `benchmarks/golden.jsonl` 是发布门禁输入，不是垃圾；原始计划、阶段报告和首批审核包是审计证据；缓存/构建物虽可再生，但当前工作树状态不足以授权批量物理清理。

## 当前可验证结论

- `pytest`：243 passed、2 skipped。
- `ruff check scripts src tests`：通过。
- `pip check`：通过。
- `scripts.release_gate --json`：BLOCKED，阻塞为 `license_missing`、`golden_empty`、`split_missing`。
- 本轮未修改业务代码、依赖、索引、语料、`.env` 或公开 API。
