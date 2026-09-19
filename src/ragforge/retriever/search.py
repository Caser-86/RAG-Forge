"""检索入口：稠密 + BM25 → RRF 融合 → 可选重排 → 证据。"""
from __future__ import annotations

import time

from ..config import Settings
from ..embeddings import BaseEmbedder
from ..models import Chunk, Evidence
from ..observability import get_logger
from ..vectorstore import VectorStore
from .fusion import rrf_fuse
from .rerank import Reranker, RerankerUnavailable
from .sparse import BM25Index

logger = get_logger()


class Retriever:
    def __init__(self, store: VectorStore, embedder: BaseEmbedder,
                 bm25: BM25Index, settings: Settings, reranker: Reranker | None = None):
        self.store = store
        self.embedder = embedder
        self.bm25 = bm25
        self.settings = settings
        self.reranker = reranker or Reranker(settings.rerank_model, settings.use_rerank)
        self.last_timings: dict[str, float | None] = {
            "embedding": None,
            "dense": None,
            "sparse": None,
            "fusion": None,
            "rerank": None,
        }
        self.last_effective_mode: str | None = None

    def retrieve(
        self,
        query: str,
        *,
        mode: str | None = None,
        top_k: int | None = None,
    ) -> list[Evidence]:
        selected_mode = mode or self.settings.retrieval_mode
        selected_top_k = self.settings.top_k if top_k is None else top_k
        self.last_effective_mode = selected_mode
        self.last_timings = {
            "embedding": None,
            "dense": None,
            "sparse": None,
            "fusion": None,
            "rerank": None,
        }
        if selected_mode not in {"dense", "hybrid", "hybrid_rerank"}:
            raise ValueError(f"unsupported retrieval mode: {selected_mode}")
        if selected_top_k <= 0:
            return []

        dense = self._dense(query, max(self.settings.dense_top_k, selected_top_k))
        if selected_mode == "dense":
            return self._to_evidence(dense[:selected_top_k], [], [], selected_mode)

        sparse_start = time.monotonic()
        sparse = self.bm25.search(query, self.settings.sparse_top_k)
        self.last_timings["sparse"] = (time.monotonic() - sparse_start) * 1000
        fusion_start = time.monotonic()
        fused = rrf_fuse(dense, sparse, k=60)
        self.last_timings["fusion"] = (time.monotonic() - fusion_start) * 1000
        if selected_mode == "hybrid":
            return self._to_evidence(
                fused[:selected_top_k], dense, sparse, selected_mode
            )

        status = self.reranker.status()
        if not status["available"]:
            raise RerankerUnavailable(str(status["reason"]))
        candidates = fused[: max(self.settings.rerank_candidate_k, selected_top_k)]
        rerank_start = time.monotonic()
        reranked = self.reranker.rerank(query, candidates, selected_top_k)
        self.last_timings["rerank"] = (time.monotonic() - rerank_start) * 1000
        return self._to_evidence(reranked, dense, sparse, selected_mode)

    @staticmethod
    def _to_evidence(
        selected: list[tuple[Chunk, float]],
        dense: list[tuple[Chunk, float]],
        sparse: list[tuple[Chunk, float]],
        mode: str,
    ) -> list[Evidence]:
        dense_map = {c.id: s for c, s in dense}
        sparse_map = {c.id: s for c, s in sparse}
        if mode == "dense":
            return [
                Evidence(
                    chunk=chunk,
                    dense_score=score,
                    score_kind={"dense": "cosine"},
                )
                for chunk, score in selected
            ]

        fused = rrf_fuse(dense, sparse, k=60)
        fused_map = {c.id: s for c, s in fused}
        rerank_map = {
            c.id: score for c, score in selected
        } if mode == "hybrid_rerank" else {}
        evidences: list[Evidence] = []
        for chunk, _score in selected:
            score_kind = {"fused": "rrf"}
            if mode == "hybrid_rerank":
                score_kind["rerank"] = "cross_encoder"
            evidences.append(Evidence(
                chunk=chunk,
                dense_score=dense_map.get(chunk.id),
                sparse_score=sparse_map.get(chunk.id),
                fused_score=fused_map.get(chunk.id),
                rerank_score=rerank_map.get(chunk.id),
                score_kind=score_kind,
            ))
        return evidences

    def _dense(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        embedding_start = time.monotonic()
        vec = self.embedder.encode([query])[0]
        self.last_timings["embedding"] = (time.monotonic() - embedding_start) * 1000
        dense_start = time.monotonic()
        results = self.store.search(vec, top_k)
        self.last_timings["dense"] = (time.monotonic() - dense_start) * 1000
        return results

    def reranker_status(self) -> dict[str, object]:
        return self.reranker.status()

    def index_scope(self) -> None:
        logger.info("检索器就绪：向量文书=%s, BM25 片段=%s, 重排=%s",
                    len(self.store), len(self.bm25.chunks), self.settings.use_rerank)
