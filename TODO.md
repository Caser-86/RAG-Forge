# RAG-Forge 后续事项（已提交开发基线）

核对日期：2026-10-27。适用源码基线 `a14db8e`；本地有尚未提交的进一步整改，不能将其完成状态套用于本分支。

- [x] 修复原 Windows CI 的 18 条依赖告警，并更新 local/Docker 中 filelock；四锁复查无已知漏洞，见[依赖整改记录](docs/reports/dependency-remediation-2026-10-27.md)。GitHub 当前提交 CI 仍须确认。
- [ ] 权利人确认代码与第三方分发范围，补齐根 LICENSE 并核对元数据。
- [ ] 确认稳定语料/索引身份，核对或重新生成候选，真实审核者完成 100 题 Golden。
- [ ] 冻结 calibration 20 / test 80 split，在查看 test 输出前确定配置、模型 digest、硬件与阈值。
- [ ] 运行正式 retrieval/chunking/generation 实验及人工答案评审；候选试跑仅标 provisional。
- [ ] 选择目标 profile、备份和维护窗口，完成持久化切换、恢复与真模型抽样。
- [ ] 对准备发布的实际代码重新执行离线/平台/安全/依赖/浏览器/wheel/Compose 门禁并核对远端 CI。
- [ ] 审查本地后续整改再决定代码提交与集成；本次文档整理不上传或合并它们。
- [ ] 对可再生缓存/构建物按 Git 状态和用途单独清理，保留用户数据、环境文件和验收证据。

`golden.jsonl` 在此代码基线为空，冻结 split 与根 LICENSE 缺失。正式发布仍未通过；本次未运行门禁或服务，不把旧机器的运行状态写为当前事实。

入口见 [README](README.md)，操作与历史导航见[文档索引](docs/README.md)。
