"""FastAPI 服务：/ask /query /ingest /health。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..observability import setup_logging
from ..pipeline import RAGForge

setup_logging()
app = FastAPI(title="RAG-Forge", version="0.1.0")
engine: RAGForge | None = None


class AskRequest(BaseModel):
    query: str = Field(min_length=1)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)


class IngestRequest(BaseModel):
    paths: list[str]


@app.on_event("startup")
def _startup() -> None:
    global engine
    engine = RAGForge()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "indexed_chunks": len(engine.store) if engine else 0}


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    if not engine:
        raise HTTPException(500, "engine not ready")
    ans = engine.ask(req.query)
    return {
        "trace_id": ans.trace_id,
        "answer": ans.answer,
        "refused": ans.refused,
        "citations": ans.citations,
        "evidences": [{"source": e.chunk.source, "rerank_score": round(e.rerank_score, 4)} for e in ans.evidences],
    }


@app.post("/query")
def retriever_query(req: QueryRequest) -> dict:
    if not engine:
        raise HTTPException(500, "engine not ready")
    evs = engine.retrieve_only(req.query)
    return {"hits": [
        {"source": e.chunk.source, "rerank_score": round(e.rerank_score, 4),
         "fused_score": round(e.fused_score, 4), "snippet": e.chunk.text[:120]} for e in evs
    ]}


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    if not engine:
        raise HTTPException(500, "engine not ready")
    if not all(p and Path(p).exists() for p in req.paths):
        raise HTTPException(400, "存在不存在的路径")
    n = engine.ingest_files(req.paths)
    return {"indexed_chunks": n}