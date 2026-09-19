import numpy as np
import pytest

import ragforge.retriever.search as search_module
from ragforge.config import Settings
from ragforge.embeddings import BaseEmbedder
from ragforge.models import Chunk
from ragforge.retriever.search import RerankerUnavailable, Retriever
from ragforge.retriever.sparse import BM25Index
from ragforge.vectorstore import InMemoryStore


class FakeEmbedder(BaseEmbedder):
    @property
    def dim(self):
        return 2

    def encode(self, texts):
        return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


class SpyStore(InMemoryStore):
    def __init__(self):
        super().__init__()
        self.search_limits = []

    def search(self, query_vector, top_k):
        self.search_limits.append(top_k)
        return super().search(query_vector, top_k)


class FakeReranker:
    enabled = True

    def __init__(self):
        self.calls = []

    def status(self):
        return {"available": True, "enabled": True, "reason": None}

    def rerank(self, query, candidates, top_k):
        self.calls.append((query, len(candidates), top_k))
        return list(reversed(candidates))[:top_k]


def _settings(**overrides):
    values = {
        "_env_file": None,
        "embedder_backend": "deterministic",
        "embedder_dim": 2,
        "generation_backend": "offline",
        "vector_store": "in_memory",
        "retrieval_mode": "hybrid",
        "dense_top_k": 20,
        "sparse_top_k": 20,
        "top_k": 5,
        "rerank_top_k": 5,
        "use_rerank": False,
    }
    values.update(overrides)
    return Settings(**values)


def _retriever(settings, *, reranker=None):
    store = SpyStore()
    chunks = [
        Chunk(id="c1", doc_id="d1", title="one", text="keyword one"),
        Chunk(id="c2", doc_id="d2", title="two", text="keyword two"),
    ]
    for chunk in chunks:
        store.add(chunk, np.array([1.0, 0.0], dtype=np.float32))
    return Retriever(store, FakeEmbedder(), BM25Index(chunks), settings, reranker=reranker)


def test_dense_mode_does_not_call_bm25_rrf_or_reranker(monkeypatch):
    retriever = _retriever(_settings())
    monkeypatch.setattr(retriever.bm25, "search", lambda *_args: pytest.fail("BM25 called"))
    monkeypatch.setattr(search_module, "rrf_fuse", lambda *_args, **_kwargs: pytest.fail("RRF called"))

    results = retriever.retrieve("keyword", mode="dense", top_k=1)

    assert len(results) == 1
    assert results[0].dense_score is not None
    assert results[0].sparse_score is None
    assert results[0].fused_score is None
    assert retriever.store.search_limits == [20]


def test_hybrid_rerank_honors_requested_top_k_and_preserves_score_kinds():
    reranker = FakeReranker()
    retriever = _retriever(_settings(use_rerank=True), reranker=reranker)

    results = retriever.retrieve("keyword", mode="hybrid_rerank", top_k=1)

    assert len(results) == 1
    assert reranker.calls == [("keyword", 2, 1)]
    assert results[0].dense_score is not None
    assert results[0].sparse_score is not None
    assert results[0].fused_score is not None
    assert results[0].rerank_score is not None


def test_hybrid_rerank_reports_unavailable_instead_of_silent_fallback():
    retriever = _retriever(_settings())

    with pytest.raises(RerankerUnavailable, match="disabled"):
        retriever.retrieve("keyword", mode="hybrid_rerank", top_k=1)
