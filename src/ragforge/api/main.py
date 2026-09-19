"""FastAPI 服务：保留旧接口，并提供本地模型发现与聊天接口。"""
from __future__ import annotations

import hmac
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Annotated, Literal, NoReturn, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from ..config import get_settings
from ..observability import setup_logging
from ..ollama_client import (
    OllamaClient,
    OllamaModelNotFound,
    OllamaProtocolError,
    OllamaTimeout,
    OllamaUnavailable,
)
from ..pipeline import RAGForge
from ..retriever.rerank import Reranker, RerankerUnavailable
from .security import RateLimiter

setup_logging()
engine: RAGForge | None = None
engine_lock = RLock()
request_limiter = RateLimiter()
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine
    current = RAGForge()
    with engine_lock:
        engine = current
    try:
        yield
    finally:
        with engine_lock:
            current = engine
            engine = None
        close = getattr(current, "close", None)
        if close:
            close()


def validate_api_key(provided_key: str | None, expected_key: str) -> None:
    """配置了 API key 时拒绝缺失或不匹配的请求，且不记录密钥内容。"""
    matches = False
    if isinstance(provided_key, str):
        try:
            # compare_digest 对非 ASCII str 可能抛 TypeError；统一比较 UTF-8 bytes。
            matches = hmac.compare_digest(
                provided_key.encode("utf-8"), expected_key.encode("utf-8")
            )
        except (TypeError, UnicodeError):
            matches = False
    if expected_key and not matches:
        raise HTTPException(
            status_code=401,
            detail="需要有效的 API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def enforce_request_policy(
    request: Request,
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    retry_after = request_limiter.check(client_host, settings.rate_limit_per_minute)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后重试",
            headers={"Retry-After": str(retry_after)},
        )
    validate_api_key(api_key, settings.api_key)


app = FastAPI(
    title="RAG-Forge",
    version="0.1.0",
    lifespan=lifespan,
)


def _request_host(request: Request) -> str:
    raw_host = request.headers.get("host", "").strip().lower()
    if raw_host.startswith("[") and "]" in raw_host:
        return raw_host[1 : raw_host.index("]")]
    return raw_host.split(":", 1)[0]


def _host_allowed(host: str, allowed_hosts: list[str]) -> bool:
    return any(
        pattern == "*"
        or host == pattern
        or (pattern.startswith("*.") and host.endswith(pattern[1:]))
        for pattern in allowed_hosts
    )


def _security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    )
    return response


@app.middleware("http")
async def request_security_boundary(request: Request, call_next):
    settings = get_settings()
    if not _host_allowed(_request_host(request), settings.allowed_hosts):
        return _security_headers(
            JSONResponse(status_code=400, content={"detail": "不受信任的 Host"})
        )

    limit = settings.max_request_body_bytes
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_length = int(content_length)
        except ValueError:
            return _security_headers(
                JSONResponse(status_code=400, content={"detail": "无效的 Content-Length"})
            )
        if declared_length < 0 or declared_length > limit:
            return _security_headers(
                JSONResponse(status_code=413, content={"detail": "请求体超过大小限制"})
            )

    if request.method in {"POST", "PUT", "PATCH"}:
        body = bytearray()
        while True:
            message = await request._receive()
            if message.get("type") != "http.request":
                break
            body.extend(message.get("body", b""))
            if len(body) > limit:
                return _security_headers(
                    JSONResponse(status_code=413, content={"detail": "请求体超过大小限制"})
                )
            if not message.get("more_body", False):
                break
        request._body = bytes(body)

    return _security_headers(await call_next(request))


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    retrieval_mode: Literal["dense", "hybrid", "hybrid_rerank"] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class IngestRequest(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=128)


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    generation_model: str | None = Field(default=None, max_length=128)
    retrieval_mode: Literal["dense", "hybrid", "hybrid_rerank"] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    rewrite: bool = False
    history: list[HistoryMessage] = Field(default_factory=list, max_length=20)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query 不能为空")
        return value


class KnowledgeDocument(BaseModel):
    document_id: str
    title: str
    source: str
    source_url: str | None = None
    chunk_count: int


class KnowledgeResponse(BaseModel):
    knowledge_state: Literal["empty", "ready"]
    indexed_chunks: int
    documents: list[KnowledgeDocument]


class SourceChunkPreview(BaseModel):
    chunk_id: str
    title: str
    source: str
    source_url: str | None = None
    heading_path: list[str]
    chunk_index: int
    snippet: str


class SourcePreviewResponse(BaseModel):
    document_id: str
    title: str
    chunks: list[SourceChunkPreview]


def _resolve_ingest_paths(
    paths: list[str],
    root: Path | None = None,
    max_bytes: int | None = None,
    max_total_bytes: int | None = None,
) -> list[Path]:
    settings = get_settings()
    ingest_root = (root or settings.ingest_root).resolve()
    ingest_limit = settings.max_ingest_bytes if max_bytes is None else max_bytes
    ingest_total_limit = (
        settings.ingest_total_bytes if max_total_bytes is None else max_total_bytes
    )
    if not ingest_root.is_dir():
        raise HTTPException(500, "摄入根目录不可用")

    resolved_paths: list[Path] = []
    total_bytes = 0
    for raw_path in paths:
        if not raw_path or not raw_path.strip():
            raise HTTPException(400, "摄入路径不能为空")
        requested = Path(raw_path)
        candidate = requested if requested.is_absolute() else ingest_root / requested
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(ingest_root)
        except ValueError as exc:
            raise HTTPException(400, "摄入路径必须位于允许的根目录内") from exc
        if not resolved.is_file():
            raise HTTPException(400, "摄入路径不存在或不是文件")
        if resolved.suffix.lower() not in {".md", ".txt", ".pdf", ".html", ".htm"}:
            raise HTTPException(400, "仅支持 md/txt/pdf/html 文件")
        file_size = resolved.stat().st_size
        if file_size > ingest_limit:
            raise HTTPException(413, "摄入文件超过大小限制")
        total_bytes += file_size
        if total_bytes > ingest_total_limit:
            raise HTTPException(413, "摄入文件总量超过限制")
        resolved_paths.append(resolved)
    return resolved_paths


def _raise_ollama_http_error(exc: Exception) -> NoReturn:
    if isinstance(exc, OllamaUnavailable):
        raise HTTPException(503, "Ollama 服务不可用") from exc
    if isinstance(exc, OllamaTimeout):
        raise HTTPException(504, "Ollama 请求超时") from exc
    if isinstance(exc, OllamaModelNotFound):
        raise HTTPException(422, "请求的 Ollama 模型未安装") from exc
    if isinstance(exc, OllamaProtocolError):
        raise HTTPException(502, "Ollama 返回了无效响应") from exc
    raise exc


def _list_ollama_models(settings) -> list[str]:
    if settings.generation_backend != "ollama":
        return []
    client = OllamaClient(
        settings.ollama_base_url,
        connect_timeout=settings.ollama_connect_timeout,
        generate_timeout=settings.ollama_generate_timeout,
    )
    try:
        return client.list_models()
    except (OllamaUnavailable, OllamaTimeout, OllamaModelNotFound, OllamaProtocolError) as exc:
        _raise_ollama_http_error(exc)
    finally:
        client.close()


def _is_installed(model: str, installed_models: list[str]) -> bool:
    if model == "bge-m3":
        return model in installed_models or "bge-m3:latest" in installed_models
    return model in installed_models


def _model_catalog(settings, installed_models: list[str]) -> dict:
    generation = (
        [
            model for model in settings.allowed_generation_models
            if _is_installed(model, installed_models)
        ]
        if settings.generation_backend == "ollama"
        else list(settings.allowed_generation_models)
    )
    embedding = ["bge-m3"] if _is_installed("bge-m3", installed_models) else []
    utility = ["qwen3:0.6b"] if _is_installed("qwen3:0.6b", installed_models) else []
    reranker = _reranker_status(settings)
    return {
        "generation": generation,
        "embedding": embedding,
        "utility": utility,
        "missing_models": [
            model for model in settings.allowed_generation_models if model not in generation
        ],
        "reranker_available": bool(reranker["available"]),
        "reranker_enabled": bool(reranker["enabled"]),
        "reranker_reason": reranker["reason"],
    }


def _reranker_status(settings) -> dict[str, object]:
    with engine_lock:
        current = engine
    if current is not None:
        status = getattr(current, "reranker_status", None)
        if status:
            return status()
    return Reranker(settings.rerank_model, settings.use_rerank).status()


def _score(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _citation_payload(citation) -> dict[str, object]:
    return citation.model_dump()


def _select_generation_model(settings, requested: str | None, installed_models: list[str]) -> str:
    default_model = (
        settings.llm_model
        if settings.generation_backend == "api"
        else settings.default_generation_model
    )
    selected = (requested or default_model).strip()
    if selected not in settings.allowed_generation_models:
        raise HTTPException(422, "请求的生成模型不在 allowlist 中")
    if settings.generation_backend == "ollama" and not _is_installed(selected, installed_models):
        raise HTTPException(422, "请求的生成模型未安装")
    return selected


def _engine_snapshot():
    with engine_lock:
        return engine


@app.get("/api/knowledge", response_model=KnowledgeResponse, dependencies=[Depends(enforce_request_policy)])
def knowledge() -> dict[str, object]:
    current = _engine_snapshot()
    if not current:
        raise HTTPException(500, "engine not ready")
    chunks = current.store.list_chunks()
    documents: dict[str, dict[str, object]] = {}
    for chunk in chunks:
        entry = documents.setdefault(
            chunk.doc_id,
            {
                "document_id": chunk.doc_id,
                "title": chunk.title,
                "source": chunk.source,
                "source_url": chunk.source_url,
                "chunk_count": 0,
            },
        )
        entry["chunk_count"] = cast(int, entry["chunk_count"]) + 1
    return {
        "knowledge_state": "ready" if chunks else "empty",
        "indexed_chunks": len(chunks),
        "documents": list(documents.values()),
    }


@app.get("/api/sources", response_model=SourcePreviewResponse, dependencies=[Depends(enforce_request_policy)])
def source_preview(
    document_id: str = Query(min_length=1, max_length=4096),
    limit: int = Query(default=20, ge=1, le=128),
) -> dict[str, object]:
    current = _engine_snapshot()
    if not current:
        raise HTTPException(500, "engine not ready")
    chunks = [chunk for chunk in current.store.list_chunks() if chunk.doc_id == document_id]
    if not chunks:
        raise HTTPException(404, "来源文档不存在")
    chunks.sort(key=lambda chunk: chunk.chunk_index)
    return {
        "document_id": document_id,
        "title": chunks[0].title,
        "chunks": [
            {
                "chunk_id": chunk.id,
                "title": chunk.title,
                "source": chunk.source,
                "source_url": chunk.source_url,
                "heading_path": chunk.heading_path,
                "chunk_index": chunk.chunk_index,
                "snippet": chunk.text[:800],
            }
            for chunk in chunks[:limit]
        ],
    }


def _export_payload(record: dict[str, object]) -> dict[str, object]:
    citations = record.get("citations")
    if not isinstance(citations, list):
        citations = []
    return {
        "trace_id": record.get("trace_id", ""),
        "query": record.get("original_query", ""),
        "answer": record.get("answer", ""),
        "model": record.get("model"),
        "refused": bool(record.get("refused", False)),
        "refusal_reason": record.get("refusal_reason"),
        "citations": citations,
    }


@app.get("/api/export/{trace_id}", dependencies=[Depends(enforce_request_policy)])
def export_trace(
    trace_id: str,
    output_format: Literal["json", "markdown"] = Query(default="markdown", alias="format"),
) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", trace_id):
        raise HTTPException(400, "trace id 格式无效")
    current = _engine_snapshot()
    getter = getattr(current, "get_trace", None) if current else None
    record = getter(trace_id) if getter else None
    if record is None:
        raise HTTPException(404, "trace 不存在或已过期")
    payload = _export_payload(record)
    if output_format == "json":
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=ragforge-result.json"},
        )

    lines = [
        "# RAG-Forge 问答结果",
        "",
        f"- Trace: `{payload['trace_id']}`",
        f"- 模型: `{payload['model'] or 'unknown'}`",
        "",
        "## 问题",
        "",
        str(payload["query"]),
        "",
        "## 回答",
        "",
        str(payload["answer"]),
        "",
        "## 引用",
        "",
    ]
    for citation in cast(list[object], payload["citations"]):
        if not isinstance(citation, dict):
            continue
        index = citation.get("index", "?")
        title = citation.get("title") or citation.get("source") or citation.get("chunk_id") or "stored evidence"
        url = citation.get("url")
        suffix = f" — {url}" if isinstance(url, str) and url else ""
        lines.append(f"- [{index}] {title}{suffix}")
        snippet = citation.get("snippet")
        if isinstance(snippet, str) and snippet:
            lines.append(f"  - {snippet}")
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=ragforge-result.md"},
    )


@app.get("/health", dependencies=[Depends(enforce_request_policy)])
def health() -> dict:
    settings = get_settings()
    with engine_lock:
        current = engine
    reranker = _reranker_status(settings)
    return {
        "status": "ok",
        "indexed_chunks": len(current.store) if current else 0,
        "reranker_available": bool(reranker["available"]),
        "reranker_reason": reranker["reason"],
    }


@app.get("/api/health", dependencies=[Depends(enforce_request_policy)])
def api_health() -> dict:
    return health()


@app.get("/api/models", dependencies=[Depends(enforce_request_policy)])
def models() -> dict:
    settings = get_settings()
    return _model_catalog(settings, _list_ollama_models(settings))


@app.post("/api/chat", dependencies=[Depends(enforce_request_policy)])
def chat(req: ChatRequest) -> dict:
    settings = get_settings()
    installed_models = _list_ollama_models(settings)
    selected_model = _select_generation_model(settings, req.generation_model, installed_models)
    with engine_lock:
        current = engine
    if not current:
        raise HTTPException(500, "engine not ready")
    try:
        ans = current.ask(
            req.query,
            model=selected_model,
            retrieval_mode=req.retrieval_mode,
            top_k=req.top_k,
            history=[item.model_dump() for item in req.history],
            rewrite=req.rewrite,
        )
    except RerankerUnavailable as exc:
        raise HTTPException(503, "请求的重排模式不可用") from exc
    except (OllamaUnavailable, OllamaTimeout, OllamaModelNotFound, OllamaProtocolError) as exc:
        _raise_ollama_http_error(exc)
    return {
        "trace_id": ans.trace_id,
        "answer": ans.answer,
        "refused": ans.refused,
        "refusal_reason": ans.refusal_reason,
        "grounded": ans.grounded,
        "citations": ans.citations,
        "citation_details": [_citation_payload(citation) for citation in ans.citation_details],
        "citation_invalid": ans.citation_invalid,
        "citation_support_status": ans.citation_support_status,
        "requested_model": selected_model,
        "model": ans.model or selected_model,
        "requested_mode": req.retrieval_mode or settings.retrieval_mode,
        "effective_mode": req.retrieval_mode or settings.retrieval_mode,
        "rewrite": req.rewrite,
        "evidences": [
            {
                "source": e.chunk.source,
                "dense_score": _score(e.dense_score),
                "sparse_score": _score(e.sparse_score),
                "fused_score": _score(e.fused_score),
                "rerank_score": _score(e.rerank_score),
                "score_kind": e.score_kind,
            }
            for e in ans.evidences
        ],
    }


@app.post("/ask", dependencies=[Depends(enforce_request_policy)])
def ask(req: AskRequest) -> dict:
    with engine_lock:
        current = engine
    if not current:
        raise HTTPException(500, "engine not ready")
    try:
        ans = current.ask(req.query)
    except RerankerUnavailable as exc:
        raise HTTPException(503, "配置的重排模式不可用") from exc
    return {
        "trace_id": ans.trace_id,
        "answer": ans.answer,
        "refused": ans.refused,
        "refusal_reason": ans.refusal_reason,
        "grounded": ans.grounded,
        "citations": ans.citations,
        "citation_details": [_citation_payload(citation) for citation in ans.citation_details],
        "citation_invalid": ans.citation_invalid,
        "citation_support_status": ans.citation_support_status,
        "evidences": [{"source": e.chunk.source, "rerank_score": _score(e.rerank_score)} for e in ans.evidences],
    }


@app.post("/query", dependencies=[Depends(enforce_request_policy)])
def retriever_query(req: QueryRequest) -> dict:
    with engine_lock:
        current = engine
    if not current:
        raise HTTPException(500, "engine not ready")
    try:
        evs = current.retrieve_only(req.query, req.retrieval_mode, req.top_k)
    except RerankerUnavailable as exc:
        raise HTTPException(503, "请求的重排模式不可用") from exc
    return {"hits": [
        {"source": e.chunk.source, "rerank_score": _score(e.rerank_score),
         "fused_score": _score(e.fused_score), "dense_score": _score(e.dense_score),
         "sparse_score": _score(e.sparse_score), "score_kind": e.score_kind,
         "snippet": e.chunk.text[:120]} for e in evs
    ]}


@app.get("/api/traces/{trace_id}", dependencies=[Depends(enforce_request_policy)])
def trace(trace_id: str) -> dict:
    with engine_lock:
        current = engine
        getter = getattr(current, "get_trace", None) if current else None
        record = getter(trace_id) if getter else None
    if record is None:
        raise HTTPException(404, "trace 不存在或已过期")
    return record


@app.post("/ingest", dependencies=[Depends(enforce_request_policy)])
def ingest(req: IngestRequest) -> dict:
    paths = _resolve_ingest_paths(req.paths)
    with engine_lock:
        current = engine
    if not current:
        raise HTTPException(500, "engine not ready")
    try:
        n = current.ingest_files(paths)
    except FileNotFoundError as exc:
        raise HTTPException(400, "摄入文件在处理前已不存在") from exc
    return {"indexed_chunks": n}


@app.get("/", include_in_schema=False)
def web_root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
