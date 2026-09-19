# M0 基线与环境检查报告

日期：2026-09-11

分支：`codex/local-rag-m0`

## 基线状态

- 当前工作树在执行前已存在未提交修改，来自前一轮项目审计和安全加固；本阶段没有重置、覆盖或删除这些修改。
- M0 实现新增 `scripts/check_environment.py`、`tests/test_environment.py`、`tests/test_smoke.py`，并补充 `numpy` 直接依赖声明。
- `.env` 未被测试读取到 RAG 运行配置：Smoke 明确使用 `_env_file=None`、`in_memory`、`deterministic`、无 LLM key 和关闭 rerank。

## 实际环境

| 检查项 | 结果 | 证据 |
|---|---|---|
| Python | PASS，3.14.6 | `.venv\Scripts\python.exe --version` |
| 项目包 import | PASS | `check_environment --json` |
| Ollama CLI | PASS，已安装 | `Get-Command ollama` |
| Ollama HTTP | PASS，`http://127.0.0.1:11434` | `check_environment --json` |
| data 目录可写 | PASS | 检查器创建并清理临时探针文件 |
| editable 安装 | PASS | `pip install -e ".[local,vector,dev]"` |

## Ollama 模型

实际 `ollama list` 和 HTTP `/api/tags` 均检测到：

- `bge-m3:latest`，检查器按 `bge-m3` 等价匹配
- `gemma3:4b`
- `gemma4:e4b`
- `qwen3:0.6b`

缺失模型：无。

## 实际测试

```text
.venv\Scripts\python.exe -m pytest -q
29 passed

.venv\Scripts\python.exe -m scripts.smoke
exit code 0

ruff check . --exclude .venv --exclude .git --exclude .pytest_cache
All checks passed!

.venv\Scripts\python.exe -m compileall -q src scripts tests
exit code 0

.venv\Scripts\python.exe -m pip check
No broken requirements found.

.venv\Scripts\python.exe -m scripts.check_environment
exit code 0

git diff --check
exit code 0；仅有 Git 的 LF/CRLF 转换提示，无 whitespace error
```

## M0 验收结论

软件实现和本机环境检查均通过，可以进入 M1。M0 没有调用 Ollama 生成或 embedding 接口，因此 M1/M2 的真实模型功能仍需按计划单独验收。

已知限制：当前解释器为 Python 3.14.6；项目声明最低版本为 Python 3.10，README 的示例版本为 3.11。本阶段未在 3.10 或 3.11 解释器上重复运行，不能据此宣称这些版本已经实测通过。
