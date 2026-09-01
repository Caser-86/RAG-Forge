"""编排层：文档 → 索引 → 检索 → 生成，串联整条链路并产出 trace。"""
from __future__ import annotations

from pathlib import Path

from .config import Settings, get_settings
from .embeddings import BaseEmbedder, build_embedder
from .generator import _BaseGenerator, build_generator
from .ingest import Chunker, load_documents
from .models import Answer, Chunk, Document, Evidence
from .observability import get_logger, new_trace_id, timer
from .retriever import Retriever
from .retriever.sparse import BM25Index
from .vectorstore import VectorStore, build_store

logger = get_logger()


class RAGForge:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.embedder: BaseEmbedder = build_embedder(self.settings)
        self.store: VectorStore = build_store(self.settings, self.embedder.dim)
        self.bm25 = BM25Index([])
        self.chunker = Chunker(self.settings.chunk_size, self.settings.chunk_overlap)
        self.retriever: Retriever | None = None
        self.generator: _BaseGenerator = build_generator(self.settings)
        self._all_chunks: list[Chunk] = []

    # ---- 摄取 ----
    def ingest_files(self, paths: list[str | Path]) -> int:
        docs = load_documents([Path(p) for p in paths])
        chunks: list[Chunk] = []
        for doc in docs:
            chunks.extend(self.chunker.chunk(doc))
        return self.ingest_chunks(chunks)

    def ingest_chunks(self, chunks: list[Chunk]) -> int:
        for i, c in enumerate(chunks):
            vec = self.embedder.encode([c.text])[0]
            self.store.add(c, vec)
        self._all_chunks = chunks
        self.bm25 = BM25Index(chunks)
        self.retriever = Retriever(self.store, self.embedder, self.bm25, self.settings)
        self.retriever.index_scope()
        return len(chunks)

    # ---- 问答 ----
    def ask(self, query: str) -> Answer:
        trace_id = new_trace_id()
        with timer("retrieve", logger):
            evidences = self.retriever.retrieve(query) if self.retriever else []
        with timer("generate", logger):
            answer = self.generator.generate(query, evidences, trace_id)
        logger.info("[trace %s] query=%r hits=%d best=%.4f",
                    trace_id, query, len(evidences),
                    max((e.rerank_score or e.fused_score for e in evidences), default=0.0))
        return answer

    def retrieve_only(self, query: str) -> list[Evidence]:
        if not self.retriever:
            return []
        with timer("retrieve", logger):
            return self.retriever.retrieve(query)