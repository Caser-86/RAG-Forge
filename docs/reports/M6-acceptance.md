# M6 验收报告：Citation、工程拒答、Trace

日期：2026-09-12

## 结论

M6 的工程门禁通过。Citation 只从最终发送给模型的 Evidence 建立，越界或缺失引用会被拒答；空 Evidence 在生成前拒答；Trace 具备短期、有界存储并受 API key 策略保护。

本阶段没有把 RRF 排名或 CrossEncoder raw logit 当作概率。独立语义标注集尚未建立，因此拒答阈值状态明确记录为 `uncalibrated`。

## 已验证项

| 项目 | 结果 | 证据 |
|---|---|---|
| 上下文预算与编号 | PASS | `tests/test_citations.py`：预算裁剪后再编号，Citation 映射实际 chunk |
| Prompt 防注入 | PASS | 检查闭合标签、假 system 指令、恶意来源字符串；正文经过 HTML 编码并置于不可信数据区 |
| 引用解析 | PASS | 正常、重复、`[0]`、越界、无引用、inline/fenced code 标记均有测试 |
| Citation 真实性 | PASS | `document_id/chunk_id/title/url/snippet` 均来自 `Evidence`，重复引用按首次出现顺序去重 |
| 生成后拒答 | PASS | 无有效引用、越界引用、模型声明信息不足分别产生明确理由 |
| 阈值语义 | PASS | `rerank_score=0`、负 raw logit、未执行重排分开处理；仅显式 `normalized`/`probability` 分数进入阈值 |
| 关键约束支持 | PASS | 错误码、数值约束缺失时返回 `insufficient_support`；普通词不要求字面重叠，保留跨语言空间 |
| Trace 字段与耗时 | PASS | Pipeline 测试覆盖 query、model、mode、候选、context、引用、阶段耗时和未执行阶段 |
| TraceStore | PASS | 线程安全测试、容量 100/可配置、TTL、单值长度上限、过期返回空 |
| Trace API | PASS | `/api/traces/{trace_id}` 返回结构化记录，404、401 均有测试 |

## 固定校准样本

命令：

```text
python -m scripts.calibrate_refusal --fixtures tests/fixtures
```

结果来自 22 条无答案样本和 22 条有答案样本；只运行固定规则，不在评测集上反复调阈值：

| 模式 | 阈值 | 样本 | 正确拒答 | 漏拒 | 误拒 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| engineering_offline | 0.15 | 无答案 22 | 22 | 0 | — | PASS |
| engineering_offline | 0.15 | 有答案 22 | — | — | 0（0%） | PASS |

无答案正确拒答率为 100%，超过“大部分”门槛；有答案误拒率为 0%。这只是固定 Evidence/OfflineGenerator 的工程验收，不代表真实 LLM 的语义拒答质量。真实模型仍需独立的人工标注校准集和独立评测集。

## 防护局限

- HTML 编码能避免常见 XML/标签闭合和伪指令边界混淆，但不能替代模型层面的提示注入防御。
- v1 只验证引用编号和关键实体/数值是否存在，不验证每个句子是否被对应证据事实支撑；`citation_support_status` 默认 `unverified`。
- Trace 是进程内短期存储，重启后消失；它不是审计数据库，也不应长期保存完整语料。
- Trace 查询接口继承全局 API key 和限流策略；生产部署仍应配置 TLS、反向代理认证和更严格的日志策略。

## 回归命令

```text
python -m pytest -q
python -m compileall -q src scripts
python -m scripts.smoke
python -m pip check
```
