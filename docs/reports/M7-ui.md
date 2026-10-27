# M7 验收报告：原生 Web UI

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](final-acceptance.md)。

日期：2026-09-12

## 结论

M7 的静态资源、API 集成和真实浏览器主流程通过。页面不依赖 Node 构建，支持 Chat / Debug / Settings 三个视图；模型、检索模式和 Top-K 均由可见控件控制，回答和 Trace 均按安全文本节点渲染。

## 已完成

- 新增 `src/ragforge/api/static/index.html`、`app.css`、`app.js` 和 `favicon.svg`。
- 页面启动分别读取 `/api/models`、`/api/health`；非 Ollama 后端也能正确暴露 allowlist 模型。
- `/api/chat` 返回后自动读取对应 Trace；Debug 展示阶段耗时、候选分数、最终 context 和 raw output。
- Citation 的标题、编号和安全 URL 使用 DOM 节点与 `textContent`，仅允许 `http` / `https`，新窗口带 `noopener noreferrer`；拒绝 `javascript:` / `data:` 协议。
- API key 只放在当前页面内存，请求通过 `X-API-Key` header 发送，不写 URL、HTML 源码或 `localStorage`。
- M7 阶段 Query Rewrite 控件固定禁用并标明 M8；M8 完成后改为默认关闭的可选开关，切换生成模型仍只影响下一次请求。
- 请求序号与 `AbortController` 防止迟到响应覆盖当前会话；页面支持 loading、错误、重试（重新发送）、清空会话、小屏单列和 reduced-motion。
- `pyproject.toml` 已声明 `api/static/*` package data，wheel 检查确认 HTML/CSS/JS 均被打包。

## 浏览器验收

使用 `playwright-cli` 访问 `http://127.0.0.1:8000`，服务使用隔离的 `in_memory` 索引：

| 场景 | 结果 |
|---|---|
| 根页面与静态资源 | PASS，页面、CSS、JS、favicon 均返回成功 |
| Chat / Debug / Settings 切换 | PASS |
| 无答案 | PASS，显示 `REFUSED · no_evidence` |
| Ollama 两模型同题 | PASS，分别验证 `gemma3:4b` 与 `gemma4:e4b`，未重新索引 |
| Citation 与 Debug | PASS，实际显示来源、候选、context、raw output、耗时 |
| API key 错误与页内恢复 | PASS，401 反馈清晰，输入 key 后恢复 READY |
| reranker 不可用 | PASS，选项显示“当前不可用”，请求反馈 503，不静默降级 |
| 正常流程浏览器控制台 | PASS，无 JS exception 或 warning；401/503 场景产生的 HTTP error 仅为预期服务错误反馈 |

已保存无密钥、无私人语料的 Debug 页面截图：[m7-debug.png](../images/m7-debug.png)。

## 验证命令

```text
python -m pytest -q tests/test_web_ui.py tests/test_api_models.py tests/test_api.py tests/test_api_security.py
node --check src/ragforge/api/static/app.js
python -m pip wheel . --no-deps --wheel-dir <temporary-dir>
python -m pytest -q
```
