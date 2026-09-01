"""检索入口：稠密 + BM25 → RRF 融合 → 可选重排 → 证据。"""
from __future__ import annotations

import numpy as np

from ..config import Settings
from ..embeddings import BaseEmbedder
from ..models import Chunk, Evidence
from ..observability import get_logger, timer
from ..vectorstore import VectorStore
from .fusion import rrf_fuse
from .rerank import Reranker
from .sparse import BM25Index

logger = get_logger()


class Retriever:
    def __init__(self, store: VectorStore, embedder: BaseEmbedder,
                 bm25: BM25Index, settings: Settings):
        self.store = store
        self.embedder = embedder
        self.bm25 = bm25
        self.settings = settings
        self.reranker = Reranker(settings.rerank_model, settings.use_rerank)

    def retrieve(self, query: str) -> list[Evidence]:
        dense_k = max(self.settings.top_k, self.settings.rerank_top_k, 4)
        sparse_k = self.settings.sparse_top_k

        dense = self._dense(query, dense_k)
        sparse = self.bm25.search(query, sparse_k)

        fused = rrf_fuse(dense, sparse, k=60)
        rerank_map: dict[str, float] = {}
        if self.settings.use_rerank and self.reranker.enabled and fused:
            reranked = self.reranker.rerank(query, fused, self.settings.rerank_top_k)
            rerank_map = {c.id: s for c, s in reranked}
        else:
            reranked = fused[: self.settings.top_k]

        # 组装证据（保留各阶段分数便于 trace 与评测）
        dense_map = {c.id: s for c, s in dense}
        sparse_map = {c.id: s for c, s in sparse}
        fused_map = {c.id: s for c, s in fused}

        evidences = []
        for c, rscore in reranked:
            evidences.append(Evidence(
                chunk=c,
                dense_score=dense_map.get(c.id, 0.0),
                sparse_score=sparse_map.get(c.id, 0.0),
                fused_score=fused_map.get(c.id, 0.0),
                rerank_score=rerank_map.get(c.id, 0.0),
            ))
        return evidences

    def _dense(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        vec = self.embedder.encode([query])[0]
        return self.store.search(vec, top_k)

    def index_scope(self) -> None:
        logger.info("检索器就绪：向量文书=%s, BM25 片段=%s, 重排=%s",
                    len(self.store), len(self.bm25.chunks), self.settings.use_rerank)