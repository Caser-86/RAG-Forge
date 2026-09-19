import logging
import time

import pytest

from ragforge.trace_store import TraceStore
from ragforge.observability import new_trace_id
from ragforge.config import Settings
from ragforge.pipeline import RAGForge


def test_trace_store_keeps_structured_records_and_enforces_capacity():
    store = TraceStore(max_entries=2, ttl_seconds=60, max_item_chars=20)
    store.put("trace-1", {"query": "secret question"})
    store.put("trace-2", {"query": "q2", "context": "x" * 100})
    store.put("trace-3", {"query": "q3"})

    assert store.get("trace-1") is None
    assert store.get("trace-3")["query"] == "q3"
    assert len(store) == 2
    assert len(store.get("trace-2")["context"]) <= 20


def test_trace_store_expires_records_and_returns_404_style_none():
    store = TraceStore(max_entries=10, ttl_seconds=0.01)
    store.put("trace-expired", {"status": "ok"})
    time.sleep(0.03)

    assert store.get("trace-expired") is None
    assert len(store) == 0


def test_trace_store_is_thread_safe_for_unique_ids():
    store = TraceStore(max_entries=100)
    for index in range(100):
        store.put(f"trace-{index}", {"index": index})

    records = [store.get(f"trace-{index}") for index in range(100)]
    assert all(record is not None for record in records)
    assert len({record["index"] for record in records}) == 100


def test_trace_ids_are_unique():
    trace_ids = {new_trace_id() for _ in range(200)}

    assert len(trace_ids) == 200


@pytest.mark.parametrize("trace_id", ["", "missing"])
def test_trace_store_missing_ids_are_not_synthesized(trace_id: str):
    store = TraceStore()
    assert store.get(trace_id) is None


def test_query_failure_logs_trace_id_and_error_type_without_query(caplog):
    settings = Settings(
        _env_file=None,
        embedder_backend="deterministic",
        embedder_dim=8,
        generation_backend="offline",
        vector_store="in_memory",
        use_rerank=False,
    )
    engine = RAGForge(settings)

    class BrokenRetriever:
        last_effective_mode = "hybrid"
        last_timings = {}

        def retrieve(self, query, mode=None, top_k=None):
            raise RuntimeError("synthetic failure")

    engine.retriever = BrokenRetriever()
    secret_query = "secret-query-do-not-log"
    with caplog.at_level(logging.ERROR, logger="ragforge"):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            engine.ask(secret_query)
    engine.close()

    messages = [record.getMessage() for record in caplog.records]
    assert any("stage=retrieve" in message and "error_type=RuntimeError" in message for message in messages)
    assert any("[trace " in message for message in messages)
    assert all(secret_query not in message for message in messages)
