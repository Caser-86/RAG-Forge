# RAG-Forge 后续事项（GitHub 开发分支）

核对日期：2026-10-27。功能基线 `a14db8e`，依赖修复 `7dc6f22` 已通过 CI，已完成证据见[验收摘要](docs/reports/final-acceptance.md)，不在本页继续维护完成清单。本机未提交整改不能视为此分支已实现。

- [ ] 权利人确认代码与第三方分发范围，补齐根 LICENSE 并核对元数据。
- [ ] 确认稳定语料/索引身份，核对或重建候选，真实审核者完成 100 题 Golden。
- [ ] 冻结 calibration 20 / test 80 split，在查看 test 输出前确定配置、模型 digest、硬件与阈值。
- [ ] 运行正式 retrieval/chunking/generation 实验及人工答案评审；候选试跑仅标 provisional。
- [ ] 选择目标 profile、备份和维护窗口，完成持久化切换、恢复与真模型抽样。
- [ ] 审查本地未提交的安全、更新恢复、PDF 隔离与多平台 CI 改造，协调分支差异后再单独集成；文档整理不上传或合并它们。
- [ ] 对实际发布候选重新执行平台、安全、依赖、浏览器、wheel/镜像与 Compose 门禁，不把旧 CI 外推为完整发布验收。
- [ ] 升级旧远端 workflow 的 Action runtime，并复核仅统计生产源码的覆盖率口径；保留本次已验证的 CI 证据。
- [ ] 对可再生缓存/构建物按 Git 状态和用途单独清理；保留用户数据、开发文件和验收证据。

此分支 Golden 为空，冻结 split 与根 LICENSE 缺失，正式发布仍未通过。入口见 [README](README.md)，操作与历史导航见[文档索引](docs/README.md)。
