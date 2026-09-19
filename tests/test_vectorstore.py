from types import SimpleNamespace

import numpy as np

from ragforge.models import Chunk
from ragforge.vectorstore import InMemoryStore, QdrantStore

from ragforge.vectorstore import _collection_vector_size


def test_collection_vector_size_reads_unnamed_vector_config():
    info = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors=SimpleNamespace(size=1024))
        )
    )

    assert _collection_vector_size(info) == 1024


def test_collection_vector_size_returns_none_for_unknown_shape():
    assert _collection_vector_size(SimpleNamespace()) is None


def test_qdrant_count_uses_server_side_active_filter_without_scrolling():
    calls = []

    class Client:
        def count(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(count=7)

        def scroll(self, **kwargs):
            raise AssertionError("count must not scroll all payloads")

    store = QdrantStore.__new__(QdrantStore)
    store._client = Client()
    store._collection = "collection"
    store._closed = False

    assert store.count() == 7
    assert calls[0]["collection_name"] == "collection"
    assert calls[0]["exact"] is True
    assert calls[0]["count_filter"].must_not


def test_inmemory_add_many_preserves_idempotent_add_semantics():
    store = InMemoryStore()
    chunks = [
        Chunk(id="c1", doc_id="d", title="d", text="one", source="d"),
        Chunk(id="c2", doc_id="d", title="d", text="two", source="d"),
    ]
    vectors = np.ones((2, 4), dtype=np.float32)

    store.add_many(chunks, vectors)
    store.add_many(chunks, vectors)

    assert store.count() == 2
