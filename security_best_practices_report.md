# RAG-Forge Security Best Practices Report

> 历史审计记录：下列发现和“当前实现”对应原审计日期及源码基线 `a14db8e`。2026-10-27 仅整理文档，未重做安全审计；本机后续硬化不属于此分支。

2026-10-27 更新：旧 Windows 锁的 18 条告警及 local/Docker 的 filelock 告警已通过版本更新处理；四份锁重新查询无已知漏洞。详见[依赖整改记录](docs/reports/dependency-remediation-2026-10-27.md)。此结论仅覆盖锁内包版本的已知公告，不表示完整安全审计或正式发布通过；下列内容仍为历史安全审计。

复核日期：2026-09-19。本文是安全审计快照；发布前仍需在目标部署 profile 上重新核验。

## Executive summary

本次审计覆盖 Python/FastAPI 源码、配置、脚本、Docker Compose、依赖、测试、文档和工作区生成物。未发现仓库中提交的明文密钥、命令执行、动态 import 或 subprocess 注入路径。高风险本地文件读取问题已修复；API 已支持可选 key 认证和进程内限流，检索文档也已明确标记为不可信数据。生产环境仍必须配置 API key、网关认证、TLS 和共享限流/配额。

## Resolved findings

### SBP-001 — P1 — /ingest 任意本地路径读取（已修复）

原实现只检查 Path.exists()，部署在可访问网络的 API 上时，调用者可提交任意服务器可读文件路径并将其摄入索引。

当前实现将路径解析到 `RAG_INGEST_ROOT` 下，解析 symlink 后再次检查目录边界，并限制文件类型；实现位于 `src/ragforge/api/main.py` 的 `_resolve_ingest_paths`。单文件默认限制为 10 MiB，摄入总量默认限制为 32 MiB。

### SBP-002 — P2 — 未限制请求资源消耗（已部分修复）

原 API 对 query 和批量摄入没有长度/数量上限。当前 query 限制为 4000 字符，摄入路径数量限制为 128，单文件默认限制为 10 MiB，请求体默认限制为 128 KiB，单次摄入总量默认限制为 32 MiB。

当前 API 通过 `RAG_RATE_LIMIT_PER_MINUTE` 默认按客户端地址限制每分钟 60 次；请求体大小和摄入总量也有独立限制。仍未实现每用户配额和跨进程共享限流；生产环境应在网关增加这些控制。

## Partially resolved findings

### SBP-003 — P1 — API 认证依赖运维配置（部分修复）

`/api/chat`、`/ask`、`/query` 和 `/ingest` 等 API 通过统一依赖校验 `X-API-Key`，使用常量时间比较。未配置时为了保持本地开发兼容性不会强制认证；Compose 将宿主机端口绑定到 `127.0.0.1`。

如果使用 `--host 0.0.0.0`、修改端口绑定或部署到共享网络，必须配置 key，并在网关增加 OIDC/管理员权限、请求审计和 TLS；`/ingest` 应单独置于管理员网络。

### SBP-004 — P2 — 检索文档的 Prompt Injection 防护仍需纵深（部分修复）

当前系统 Prompt 明确将资料视为不可信数据，并要求忽略资料中的指令、角色设定、提示词泄露和工具调用要求；用户问题与检索内容也使用 `<retrieved_context>` / `<question>` 分隔。引用编号范围和缺失引用有工程校验，但恶意文档仍可能影响模型输出，因此这不是完整的 Prompt Injection 消除方案。

后续仍建议做内容来源分级、敏感信息脱敏、引用编号范围校验，并在需要工具调用时增加独立的权限策略。

### SBP-006 — P2 — 限流器为单进程状态

当前 `RateLimiter` 使用有界字典和锁，能防止单进程中的突发请求和无限 key 增长，见 `src/ragforge/api/security.py`。但多 worker、多副本或多节点部署时，每个进程各自计数，不能作为生产级全局配额。

建议在反向代理、API Gateway 或 Redis 等共享存储中实现跨实例限流；保留当前实现作为本地开发和单进程兜底。

## Open findings

### SBP-005 — P2 — LLM 密钥依赖本地 .env 运维保护

原审计曾记录本机环境文件的保护问题；本次没有读取任何本地 `.env`，不再将旧机器的密钥存在性写成当前事实。运行环境、打包、日志和备份仍需排除敏感配置。

建议：确认该 key 未出现在提交、构建上下文或日志中；若曾经暴露，立即轮换；生产环境使用 secret manager 或运行时注入。

## Checks performed

- 搜索了 eval、exec、subprocess、os.system、动态 import、glob/directory scan 和私钥标记；未发现项目源码中的命令执行或反射加载路径。
- 检查了 .env、.gitignore、.dockerignore；.env 未被 Git 跟踪，Docker build context 排除了 .env。
- Qdrant 与 API Compose 宿主机端口均绑定 loopback；Qdrant 镜像已固定为 digest。
- 测试覆盖了 API 路径边界、文件大小、API key 校验、限流窗口、Prompt 不可信上下文标记、配置校验、重复摄入和持久化索引重建。
