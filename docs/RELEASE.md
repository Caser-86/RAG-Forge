# 发布清单

> 文档核对：2026-10-27，对应源码基线 `a14db8e`。本次只核对文档/文件树，未重跑服务或发布门禁；不套用本机后续代码的测试结果。

当前项目仍属于本地 Beta 交付候选，不应把 provisional benchmark 或历史验收报告当作正式质量结论。

## 发布前必须完成

- [ ] 工作树范围已核对；没有把 `.env`、用户语料、Qdrant 数据、模型缓存、`data/reports/` 私密内容打进包。
- [ ] `requirements/` 中对应平台锁文件已按锁安装并通过 `pip check`。
- [ ] `pytest`、Ruff、wheel 构建和静态资源打包检查通过。
- [ ] Dockerfile 已按 Python 3.11 锁安装，运行用户为非 root，`/app/data` 持久化可写。
- [ ] `verify_browser_e2e.ps1` 与 `verify_compose_recovery.ps1 -RunRecreate` 通过；真实 Ollama/Qdrant 结果单列。
- [ ] `index_manifest`、语料快照、provider digest 和 benchmark corpus identity 已记录。
- [ ] Golden Set 已人工审核，reviewer/time/source_refs 完整，split 已冻结；正式 benchmark 不使用 candidate 或 deterministic/offline profile。
- [ ] 安全边界已复核：loopback 默认、非 loopback 有 API key、Host 白名单、body/摄入总量、CSP、限流和 trace 鉴权。
- [ ] 依赖审计已在联网环境执行并记录日期、工具版本和结果；高危可利用问题未被忽略。
- [ ] 许可证文本和版权归属已由项目权利人确认。

## 当前明确阻塞项

`pyproject.toml` 声明 MIT，但仓库根目录当前没有可核验的 `LICENSE` 文本，不能自行补写权利人或宣称许可证已完成。正式发布前必须由权利人补充正确许可证，或修正项目元数据。

## 自动化只读门禁

在项目虚拟环境中运行：

```powershell
$env:PYTHONPATH = "src"
python -m scripts.release_gate --json
```

命令只读取仓库文件，退出码 `0` 才表示发布前置输入齐备；退出码 `1` 表示仍有阻塞项，不会修改 `.env`、Golden Set、索引或许可证。它会检查必需发布文件、非空 `LICENSE`、符合 benchmark schema 且已人工审核的 100 条题目及 20/80 hash-valid split；可回答题必须有来源，不可回答题允许合法的空来源，并列出机器可读的阻塞编号。

这是输入完整性门禁，不替代上方发布清单中的 Docker/Compose、浏览器 E2E、依赖漏洞审计、安全边界和工作树范围复核；即使输入门禁返回 `READY`，所有运行时门禁仍必须有独立证据。

截至 2026-09-19，门禁实测结果仍为 `BLOCKED`：`license_missing`、`golden_empty`、`split_missing`。这三个条件必须由权利人/真实审核流程补齐，不能由自动化脚本代填。

## 发布候选内容

至少包含：源码、`pyproject.toml`、对应锁文件、`Dockerfile`、Compose 文件、README、`docs/`、测试和静态资源。发布包不包含 `.venv`、`build/`、`dist/`、`.pytest_cache/`、`.playwright-cli/`、用户 `data/` 或任何环境密钥。

## 交付记录

最终记录应引用 [reports/final-acceptance.md](reports/final-acceptance.md)，并为每个门禁写明 `PASS/PARTIAL/FAIL/NOT_RUN`、命令、时间、运行 profile、数据身份和未完成风险。只要 P0/P1 或上述必需项未通过，就标记为“不发布”。
