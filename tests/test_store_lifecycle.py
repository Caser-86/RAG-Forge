import numpy as np
import pytest

from ragforge.config import Settings
from ragforge import pipeline
from ragforge.models import Chunk
from ragforge.pipeline import RAGForge


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        embedder_backend="deterministic",
        embedder_dim=8,
        generation_backend="offline",
        vector_store="in_memory",
        use_rerank=False,
    )


def _chunk(chunk_id: str, doc_id: str, text: str) -> Chunk:
    return Chunk(id=chunk_id, doc_id=doc_id, title=doc_id, text=text, source=doc_id)


def test_ragforge_close_releases_all_owned_resources():
    engine = RAGForge(_settings())
    calls: list[str] = []

    class Closable:
        def __init__(self, name):
            self.name = name

        def close(self):
            calls.append(self.name)

    engine.embedder = Closable("embedder")
    engine.generator = Closable("generator")
    engine.store = Closable("store")

    engine.close()
    engine.close()

    assert calls == ["generator", "embedder", "store"]


def test_delete_document_rebuilds_bm25_without_deleted_text():
    engine = RAGForge(_settings())
    engine.ingest_chunks(
        [
            _chunk("c1", "d1", "unique alpha"),
            _chunk("c2", "d2", "unique beta"),
        ]
    )

    assert engine.delete_document("d1") == 1
    assert [chunk.doc_id for chunk in engine.bm25.chunks] == ["d2"]
    assert all("alpha" not in chunk.text for chunk in engine.bm25.chunks)
    assert len(engine.store) == 1


def test_inmemory_store_close_is_idempotent():
    engine = RAGForge(_settings())
    engine.store.add(_chunk("c1", "d1", "text"), np.ones(8, dtype=np.float32))

    engine.store.close()
    engine.store.close()
    assert engine.store.count() == 1


def test_constructor_failure_closes_resources_created_before_failure(monkeypatch):
    calls: list[str] = []

    class Embedder:
        dim = 8
        identity_digest = ""

        def close(self):
            calls.append("embedder")

    class Store:
        def close(self):
            calls.append("store")

    monkeypatch.setattr(pipeline, "build_embedder", lambda settings: Embedder())
    monkeypatch.setattr(pipeline, "build_store", lambda settings, dim, collection: Store())

    def fail_generator(settings):
        raise RuntimeError("generator construction failed")

    monkeypatch.setattr(pipeline, "build_generator", fail_generator)

    with pytest.raises(RuntimeError, match="generator construction failed"):
        RAGForge(_settings())

    assert calls == ["store", "embedder"]
