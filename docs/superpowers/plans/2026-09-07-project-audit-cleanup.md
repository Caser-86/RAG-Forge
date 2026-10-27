# RAG-Forge Project Audit and Cleanup Implementation Plan

> 历史记录：保留原日期、命令、版本和阶段结论，仅用于溯源；不作为当前安装指南或待办。现行状态见[验收摘要](../../reports/final-acceptance.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不删除用户工作成果和不改变公开问答接口的前提下，修复已确认的正确性、安全性和可维护性问题，并清理明确的临时产物。

**Architecture:** 保留现有“摄入—向量库—混合检索—重排—生成”的分层结构。通过 VectorStore 的统一 chunk 枚举接口恢复持久化 Qdrant 的 BM25，批量化摄入 embedding，并在 API 层限制摄入路径到配置根目录；配置使用 Pydantic 校验，避免未知后端静默降级。

**Tech Stack:** Python 3.10+, Pydantic Settings, FastAPI, NumPy, rank-bm25, Qdrant client, sentence-transformers, pytest, Ruff, Docker Compose。

**Spec:** 用户提供的“高级代码审计 + 项目清理 + 架构优化工程师”审计要求。

## Global Constraints

- 不删除当前已修改文件：`docker-compose.yml`、`src/ragforge/ingest/chunker.py`、`src/ragforge/pipeline.py`、`src/ragforge/vectorstore.py`。
- 不删除 `data/`、`.venv/`、`.pytest_cache/` 或任何未跟踪开发文件；这些属于数据、环境或用户工作成果。
- 非明确临时产物不删除，先完成路径/字符串/配置/构建/测试/Git 引用检查。
- 不升级全部依赖，不改变技术栈，不改变 `/ask`、`/query`、`/ingest` 的响应主字段。
- 每个修复批次运行针对性测试和完整验证；无法验证的外部 Docker/Qdrant/LLM 状态必须明确报告。

---

### Task 1: 修复配置边界和依赖声明

**Files:**
- Modify: `src/ragforge/config.py`
- Modify: `src/ragforge/embeddings.py`
- Modify: `src/ragforge/vectorstore.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 环境变量 `RAG_*` 和现有 `Settings` 构造方式。
- Produces: 对后端、embedding 后端、top-k、分块参数的 fail-fast 校验；未知向量库不再静默回退到 InMemory；确定不使用的直接依赖被移除。

- [x] **Step 1: Write failing tests** for invalid backend names, invalid chunk overlap, and unknown vector store.
- [x] **Step 2: Run** `pytest tests/test_config.py -q` and confirm the new validation tests fail before implementation.
- [x] **Step 3: Implement** typed/validated settings, explicit deterministic backend selection, and explicit vector-store dispatch; make deterministic embedding honor configured dimension.
- [x] **Step 4: Remove only confirmed unused direct dependencies** (`markdown-it-py`, `httpx`, `tqdm`) after source/script/test/build reference checks; keep `datasets` because `fetch_data.py` imports it.
- [x] **Step 5: Run** `pytest tests/test_config.py -q` and `ruff check . --exclude .venv --exclude .git --exclude .pytest_cache`.

### Task 2: 修复摄入性能、重复状态和持久化 BM25

**Files:**
- Modify: `src/ragforge/pipeline.py`
- Modify: `src/ragforge/vectorstore.py`
- Modify: `src/ragforge/retriever/search.py`
- Modify: `src/ragforge/retriever/fusion.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_vectorstore.py`

**Interfaces:**
- Consumes: `VectorStore.add/search/__len__` and existing `RAGForge.ingest_chunks/retrieve_only` APIs.
- Produces: `VectorStore.list_chunks()`, batch embedding ingestion, stable upsert semantics for repeated chunk IDs, and BM25 reconstruction from a persistent store.

- [x] **Step 1: Write failing tests** for batch embedding, repeated ingestion not duplicating in-memory chunks, and retriever reconstruction from stored chunks.
- [x] **Step 2: Run** the focused tests and confirm failure.
- [x] **Step 3: Implement** `list_chunks`, batch `encode`, idempotent in-memory replacement, and BM25 rebuild from persisted chunks.
- [x] **Step 4: Remove dead imports and redundant branches** reported by Ruff in the touched retrieval/pipeline modules without broad formatting.
- [x] **Step 5: Run** focused tests, `pytest -q`, and `python -m compileall -q src scripts tests`.

### Task 3: 加固 API 摄入边界和并发状态

**Files:**
- Modify: `src/ragforge/api/main.py`
- Modify: `src/ragforge/config.py`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `RAG_INGEST_ROOT`, `IngestRequest.paths`, and the existing API routes.
- Produces: paths constrained under an allowed root (including symlink resolution), non-empty request validation, and serialized engine mutation/retrieval access.

- [x] **Step 1: Write failing tests** for rejecting paths outside the ingest root, rejecting missing files, and accepting a file inside the root.
- [x] **Step 2: Run** focused API tests and confirm failure.
- [x] **Step 3: Implement** root-constrained resolution, a lock around engine state access, and a compose volume/env mapping that matches the container path.
- [x] **Step 4: Update** README and `.env.example` with the relative-path API contract and security note.
- [x] **Step 5: Run** focused API tests, `ruff check`, and a local FastAPI import/route smoke check.

### Task 4: 文档、临时产物和最终审计验证

**Files:**
- Modify: `README.md`
- Modify: `INTERVIEW_GUIDE.md`
- Delete: `build.log` (only after Git/reference verification)
- Delete: `up.log` (only after Git/reference verification)
- Test: `tests/`

**Interfaces:**
- Consumes: actual configuration names, supported backends, tested startup commands, and the final Git/file inventory.
- Produces: documentation consistent with code and a concise audit report in the final response.

- [x] **Step 1: Re-scan** all filenames, extensions, path strings, dynamic imports, glob/scan logic, Git status, and ignored files.
- [x] **Step 2: Delete only** the two confirmed ignored local logs after confirming they are not tracked or referenced; retain data, virtualenv, caches, docs, and all modified files.
- [x] **Step 3: Run** the full available test suite, compile check, Ruff, and Docker Compose config validation.
- [x] **Step 4: Compare** README commands and environment names against the implementation and record unverified external-service limitations.
- [x] **Step 5: Report** fixed files, deleted files, retained suspicious files, P0–P3 findings, and follow-up recommendations with evidence.

---

## Phase 2: 安全建议落地

**Goal:** 在保持无 key 本地开发兼容性的前提下，落地 API 认证、进程内限流、远程 Qdrant 认证和不可信检索文本隔离。

- [x] **Step 1: Write failing tests** for optional API key validation, rate limiting, and untrusted-context prompt markers.
- [x] **Step 2: Run focused tests** and confirm missing security helpers fail during collection.
- [x] **Step 3: Implement** constant-time API key validation, bounded sliding-window rate limiting, and FastAPI-wide policy dependency.
- [x] **Step 4: Harden generation and vector-store configuration** with explicit untrusted context delimiters and optional Qdrant API key forwarding.
- [x] **Step 5: Update** `.env.example`, README, and the security report; run the full verification suite.
