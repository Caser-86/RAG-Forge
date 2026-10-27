# RAG-Forge 验收范围（GitHub 开发分支）

核对日期：2026-10-27。结论：**PARTIAL / 不发布**。功能基线为 `a14db8e`，另含依赖修复 `7dc6f22`；不是本机含未提交整改的工作树。

## 已验证与未验证

| 检查 | 证据及边界 |
|---|---|
| 依赖修复提交 CI | [40459161031](https://github.com/Caser-86/RAG-Forge/actions/runs/40459161031) 成功：243 passed、2 skipped，lint、mypy、wheel 与依赖审计通过 |
| CI 结论的文档提交 | [40459571999](https://github.com/Caser-86/RAG-Forge/actions/runs/40459571999) 成功；与修复提交代码和依赖相同 |
| 四份运行锁的已知公告 | 2026-10-27 复查无已知漏洞，版本、provider 与 profile 安装边界见[依赖整改](dependency-remediation-2026-10-27.md) |
| 模型、浏览器、Docker 与用户服务 | 本轮未手动运行；未完成目标部署与最终安全验收，不沿用历史 PASS |
| 发布输入 | 此分支 Golden 为空、根 LICENSE 与冻结 split 缺失；本轮只读文件核对，不声称运行过本地后续的严格门禁 |

本分支已有 Ollama、混合检索、UI、Trace 与候选评测工具，但没有本机后续的 readiness、PDF 独立 worker、更新恢复及安全硬化实现；本地 628 项通过不能套用为本分支的测试结果。远端旧 coverage 配置含测试代码，不与本地 source/scripts 覆盖率混用。CI 的 Node 20 弃用提示仍需后续升级 workflow；当前 runner 自动使用 Node 24 后运行成功。

## 发布缺口

权利人许可、真实人工审核、冻结 split、正式 benchmark、目标 profile、备份恢复和候选代码的完整运行验收仍需完成，见 [TODO](../../TODO.md)与[发布清单](../RELEASE.md)。CI 通过不等于这些事项完成。

旧验收表保留于[历史记录](final-acceptance-history-2026-09-19.md)，阶段 PASS、模型列表、集合点数与本机路径只指原日期。旧 MLQA 指标见[历史评测](legacy-mlqa-evaluation.md)，不作为当前正式质量结论。
