from unittest.mock import patch

import numpy as np
import pytest

from ragforge.config import Settings
from ragforge.embeddings import BaseEmbedder
from ragforge.models import Chunk, Document
from ragforge.generator import OfflineGenerator
from ragforge.query_rewriter import RewriteResult
from ragforge.pipeline import RAGForge


class CountingEmbedder(BaseEmbedder):
    def __init__(self, dim: int = 8):
        self._dim = dim
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> np.ndarray:
        self.calls.append(texts)
        return np.ones((len(texts), self._dim), dtype="float32")

    @property
    def dim(self) -> int:
        return self._dim


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        embedder_backend="deterministic",
        embedder_dim=8,
        # Pipeline trace/lifecycle tests must not depend on a live Ollama endpoint.
        generation_backend="offline",
        use_rerank=False,
    )


def _chunk(chunk_id: str = "c1", text: str = "Transformer uses attention") -> Chunk:
    return Chunk(id=chunk_id, doc_id="d1", title="doc", text=text, source="doc")


def test_ingest_batches_embedding_requests():
    engine = RAGForge(_settings())
    embedder = CountingEmbedder()
    engine.embedder = embedder

    engine.ingest_chunks([_chunk("c1"), _chunk("c2", "BM25 keyword")])

    assert embedder.calls == [["Transformer uses attention", "BM25 keyword"]]


def test_ingest_uses_one_batch_store_write():
    engine = RAGForge(_settings())
    calls = []
    original = engine.store.add_many

    def record(chunks, vectors):
        calls.append((len(chunks), vectors.shape))
        return original(chunks, vectors)

    engine.store.add_many = record
    engine.ingest_chunks([_chunk("c1"), _chunk("c2", "BM25 keyword")])

    assert calls == [(2, (2, 8))]

def test_reingesting_same_chunk_id_is_idempotent_in_memory():
    engine = RAGForge(_settings())

    engine.ingest_chunks([_chunk()])
    engine.ingest_chunks([_chunk()])

    assert len(engine.store) == 1
    assert [c.id for c in engine.store.list_chunks()] == ["c1"]


def test_ingest_document_same_version_retry_does_not_delete_existing_chunks():
    engine = RAGForge(_settings())
    document = Document(id="d1", title="doc", text="stable version", version=1)

    engine.ingest_document(document)

    with patch.object(engine.store, "delete_document_except_version", side_effect=RuntimeError("cleanup failed")):
        assert engine.ingest_document(document) == 1

    assert [chunk.text for chunk in engine.store.list_chunks()] == ["stable version"]


def test_ingest_document_cleanup_failure_keeps_old_and_new_versions():
    engine = RAGForge(_settings())
    old = Document(id="d1", title="doc", text="old version", version=1)
    new = Document(id="d1", title="doc", text="new version", version=2)

    engine.ingest_document(old)
    with patch.object(engine.store, "delete_document_except_version", side_effect=RuntimeError("cleanup failed")):
        with pytest.raises(RuntimeError, match="cleanup failed"):
            engine.ingest_document(new)

    assert {chunk.text for chunk in engine.store.list_chunks()} == {"old version", "new version"}


def test_ingest_document_partial_write_failure_removes_only_candidate_chunks():
    engine = RAGForge(_settings())
    old = Document(id="d1", title="doc", text="old version", version=1)
    new = Document(id="d1", title="doc", text="# New\n\n" + "new " * 120, version=2)
    engine.ingest_document(old)

    original_add = engine.store.add
    calls = 0

    def fail_after_first(chunk, vector):
        nonlocal calls
        calls += 1
        original_add(chunk, vector)
        if calls == 1:
            raise RuntimeError("write failed")

    with patch.object(engine.store, "add", side_effect=fail_after_first):
        with pytest.raises(RuntimeError, match="write failed"):
            engine.ingest_document(new)

    assert [chunk.text for chunk in engine.store.list_chunks()] == ["old version"]


def test_rebuilds_bm25_from_existing_store_when_retriever_is_lazy():
    engine = RAGForge(_settings())
    engine.store.add(_chunk(), np.ones(8, dtype="float32"))
    engine.retriever = None
    engine.bm25 = type(engine.bm25)([])

    engine._ensure_retriever()

    assert [c.id for c in engine.retriever.bm25.chunks] == ["c1"]


def test_ingest_rejects_embedding_shape_before_writing():
    engine = RAGForge(_settings())

    class WrongShapeEmbedder(CountingEmbedder):
        def __init__(self):
            super().__init__(dim=8)

        def encode(self, texts: list[str]) -> np.ndarray:
            return np.ones((len(texts), 7), dtype="float32")

    engine.embedder = WrongShapeEmbedder()

    with pytest.raises(ValueError, match=r"expected \(1, 8\)"):
        engine.ingest_chunks([_chunk()])

    assert len(engine.store) == 0


def test_ask_persists_trace_with_executed_and_unexecuted_phase_timings():
    values = _settings().model_dump()
    values["generation_backend"] = "offline"
    engine = RAGForge(Settings(**values))
    engine.ingest_chunks([_chunk()])

    answer = engine.ask("attention", retrieval_mode="hybrid")
    trace = engine.get_trace(answer.trace_id)

    assert trace is not None
    assert trace["original_query"] == "attention"
    assert trace["rewritten_query"] == "attention"
    assert trace["rewrite"] is False
    assert trace["effective_mode"] == "hybrid"
    timings = trace["timings"]
    assert timings["embedding"] is not None
    assert timings["dense"] is not None
    assert timings["sparse"] is not None
    assert timings["fusion"] is not None
    assert timings["rerank"] is None
    assert timings["generation"] is not None
    assert timings["total"] >= timings["generation"]
    assert trace["citations"][0]["chunk_id"] == "c1"


def test_dense_trace_marks_sparse_fusion_and_rerank_as_unexecuted():
    engine = RAGForge(_settings())
    engine.ingest_chunks([_chunk()])

    answer = engine.ask("attention", retrieval_mode="dense")
    trace = engine.get_trace(answer.trace_id)

    assert trace is not None
    timings = trace["timings"]
    assert timings["embedding"] is not None
    assert timings["dense"] is not None
    assert timings["sparse"] is None
    assert timings["fusion"] is None
    assert timings["rerank"] is None


def test_generation_error_still_leaves_a_debuggable_error_trace():
    engine = RAGForge(_settings())
    engine.ingest_chunks([_chunk()])

    class FailingGenerator:
        last_context_bundle = None
        last_raw_output = None

        def generate(self, *args, **kwargs):
            raise RuntimeError("simulated generation failure")

    engine.generator = FailingGenerator()
    with pytest.raises(RuntimeError, match="simulated generation failure"):
        engine.ask("attention")

    assert len(engine.trace_store) == 1
    trace = engine.trace_store.get(next(iter(engine.trace_store._items)))
    assert trace["error"]["type"] == "RuntimeError"


def test_rewrite_uses_rewritten_query_for_retrieval_but_original_for_generation_and_trace():
    values = _settings().model_dump()
    values["generation_backend"] = "offline"
    settings = Settings(**values)
    engine = RAGForge(settings)
    embedder = CountingEmbedder()
    engine.embedder = embedder
    engine.generator = OfflineGenerator(settings)
    engine.ingest_chunks([_chunk()])

    class FakeRewriter:
        last_result = RewriteResult("Transformer attention", False, None, 2.5)
        calls = []

        def rewrite(self, query, history, *, enabled=None):
            self.calls.append((query, history, enabled))
            return "Transformer attention"

        def close(self):
            pass

    rewriter = FakeRewriter()
    engine.query_rewriter = rewriter
    answer = engine.ask(
        "它使用什么机制？",
        history=[{"role": "user", "content": "Transformer"}],
        rewrite=True,
    )
    trace = engine.get_trace(answer.trace_id)

    assert rewriter.calls == [
        ("它使用什么机制？", [{"role": "user", "content": "Transformer"}], True)
    ]
    assert embedder.calls[-1] == ["Transformer attention"]
    assert trace["original_query"] == "它使用什么机制？"
    assert trace["rewritten_query"] == "Transformer attention"
    assert trace["rewrite"] is True
    assert trace["rewrite_status"] == "applied"
    assert trace["rewrite_timing_ms"] == 2.5
