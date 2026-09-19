import numpy as np
import pytest

from ragforge.models import Chunk
from ragforge.vectorstore import QdrantStore, VectorStoreOpenError


def _chunk(chunk_id: str, doc_id: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        doc_id=doc_id,
        title=f"title-{doc_id}",
        text=f"text-{chunk_id}",
        source=f"source-{doc_id}",
        source_url="https://example.test/doc",
        heading_path=["root"],
        chunk_index=1,
    )


def test_local_qdrant_survives_explicit_close_and_reopen(tmp_path):
    path = tmp_path / "qdrant"
    store = QdrantStore(path=path, collection="test", dim=3)
    store.upsert(_chunk("c1", "d1"), np.array([1.0, 0.0, 0.0], dtype=np.float32))
    assert store.count() == 1
    store.close()

    reopened = QdrantStore(path=path, collection="test", dim=3)
    try:
        assert reopened.exists("c1")
        hits = reopened.search(np.array([1.0, 0.0, 0.0], dtype=np.float32), 1)
        assert hits[0][0].source_url == "https://example.test/doc"
        assert hits[0][0].heading_path == ["root"]
    finally:
        reopened.close()


def test_two_local_qdrant_clients_fail_with_clear_lock_error(tmp_path):
    path = tmp_path / "qdrant"
    first = QdrantStore(path=path, collection="test", dim=3)
    try:
        with pytest.raises(VectorStoreOpenError, match="already|close|占用"):
            QdrantStore(path=path, collection="test", dim=3)
    finally:
        first.close()


def test_delete_document_isolated_and_persists_after_reopen(tmp_path):
    path = tmp_path / "qdrant"
    store = QdrantStore(path=path, collection="test", dim=3)
    store.upsert(_chunk("c1", "d1"), np.array([1.0, 0.0, 0.0], dtype=np.float32))
    store.upsert(_chunk("c2", "d1"), np.array([0.0, 1.0, 0.0], dtype=np.float32))
    store.upsert(_chunk("c3", "d2"), np.array([0.0, 0.0, 1.0], dtype=np.float32))

    assert store.delete_document("d1") == 2
    assert store.count() == 1
    assert not store.exists("c1")
    assert store.exists("c3")
    store.close()

    reopened = QdrantStore(path=path, collection="test", dim=3)
    try:
        assert reopened.count() == 1
        assert [chunk.doc_id for chunk in reopened.list_chunks()] == ["d2"]
    finally:
        reopened.close()
