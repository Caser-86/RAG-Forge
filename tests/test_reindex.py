import numpy as np
import pytest

from ragforge.config import Settings
from ragforge.embeddings import DeterministicEmbedder
from ragforge.index_manifest import build_index_manifest, load_manifest, write_manifest
from ragforge.models import Chunk
from ragforge.pipeline import RAGForge
from ragforge.vectorstore import QdrantStore, build_store
from scripts import reindex as reindex_script


def test_reindex_verifies_candidate_before_switch_and_keeps_old_collection(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.txt").write_text("RAG combines retrieval and generation.", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vector_store="qdrant_local",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="active",
        index_manifest_path=tmp_path / "index_manifest.json",
        embedder_backend="deterministic",
        embedder_model="deterministic-v1",
        embedder_dim=8,
        generation_backend="offline",
        use_rerank=False,
    )

    old_store = build_store(settings, 8, collection="active")
    old_store.upsert(
        Chunk(id="old", doc_id="old-doc", title="old", text="old"),
        np.ones(8, dtype=np.float32),
    )
    write_manifest(
        settings.index_manifest_path,
        build_index_manifest(settings, dimension=8, active_collection="active"),
    )
    old_store.close()

    monkeypatch.setattr(reindex_script, "get_settings", lambda: settings)
    result = reindex_script.reindex(docs)

    assert result["verified"] is True
    candidate = result["candidate_collection"]
    assert load_manifest(settings.index_manifest_path)["active_collection"] == candidate

    preserved = QdrantStore(path=settings.qdrant_path, collection="active", dim=8)
    try:
        assert preserved.count() == 1
    finally:
        preserved.close()

    engine = RAGForge(settings)
    try:
        assert len(engine.store) == 1
        assert engine.store.list_chunks()[0].text == "RAG combines retrieval and generation."
    finally:
        engine.close()


def test_reindex_embeds_and_upserts_in_configured_batches(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    for index in range(3):
        (docs / f"note-{index}.txt").write_text(f"document {index}", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vector_store="qdrant_local",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="active",
        index_manifest_path=tmp_path / "index_manifest.json",
        embedder_backend="deterministic",
        embedder_model="deterministic-v1",
        embedder_dim=8,
        embedder_batch_size=2,
        generation_backend="offline",
        chunk_strategy="char",
        chunk_size=100,
        chunk_overlap=0,
        use_rerank=False,
    )

    class RecordingEmbedder:
        dim = 8

        def __init__(self):
            self.batch_lengths: list[int] = []

        def encode(self, texts):
            self.batch_lengths.append(len(texts))
            return DeterministicEmbedder(self.dim).encode(texts)

        def close(self):
            return None

    embedder = RecordingEmbedder()
    monkeypatch.setattr(reindex_script, "get_settings", lambda: settings)
    monkeypatch.setattr(reindex_script, "build_embedder", lambda _settings: embedder)

    result = reindex_script.reindex(docs)

    assert result["indexed_chunks"] == 3
    assert embedder.batch_lengths == [2, 1]


def test_reindex_writes_each_embedding_batch_in_one_store_call(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    for index in range(3):
        (docs / f"note-{index}.txt").write_text(f"document {index}", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vector_store="qdrant_local",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="active",
        index_manifest_path=tmp_path / "index_manifest.json",
        embedder_backend="deterministic",
        embedder_model="deterministic-v1",
        embedder_dim=8,
        embedder_batch_size=2,
        generation_backend="offline",
        chunk_strategy="char",
        chunk_size=100,
        chunk_overlap=0,
        use_rerank=False,
    )

    class RecordingStore:
        def __init__(self):
            self.chunks: list[Chunk] = []
            self.batch_lengths: list[int] = []
            self.single_writes = 0

        def add_many(self, chunks, vectors):
            self.batch_lengths.append(len(chunks))
            self.chunks.extend(chunks)

        def upsert(self, chunk, vector):
            self.single_writes += 1
            self.chunks.append(chunk)

        def count(self):
            return len(self.chunks)

        def search(self, query_vector, top_k):
            return [(self.chunks[0], 1.0)] if self.chunks else []

        def close(self):
            return None

    store = RecordingStore()
    monkeypatch.setattr(reindex_script, "get_settings", lambda: settings)
    monkeypatch.setattr(reindex_script, "build_embedder", lambda _settings: DeterministicEmbedder(8))
    monkeypatch.setattr(reindex_script, "build_store", lambda *_args, **_kwargs: store)

    result = reindex_script.reindex(docs, collection="candidate")

    assert result["indexed_chunks"] == 3
    assert store.batch_lengths == [2, 1]
    assert store.single_writes == 0


@pytest.mark.parametrize("candidate", ["active", "legacy"])
def test_reindex_rejects_existing_collection_before_writing(tmp_path, monkeypatch, candidate):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.txt").write_text("new document", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        vector_store="qdrant_local",
        qdrant_path=tmp_path / "qdrant",
        qdrant_collection="active",
        index_manifest_path=tmp_path / "index_manifest.json",
        embedder_backend="deterministic",
        embedder_model="deterministic-v1",
        embedder_dim=8,
        generation_backend="offline",
        use_rerank=False,
    )

    existing = build_store(settings, 8, collection=candidate)
    existing.upsert(
        Chunk(id="existing", doc_id="existing-doc", title="existing", text="keep me"),
        np.ones(8, dtype=np.float32),
    )
    existing.close()

    monkeypatch.setattr(reindex_script, "get_settings", lambda: settings)
    with pytest.raises(ValueError, match="must be a new collection"):
        reindex_script.reindex(docs, collection=candidate)

    preserved = QdrantStore(path=settings.qdrant_path, collection=candidate, dim=8)
    try:
        assert [chunk.text for chunk in preserved.list_chunks()] == ["keep me"]
    finally:
        preserved.close()
