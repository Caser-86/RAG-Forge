import json

import pytest

from ragforge.models import Chunk
from ragforge.pipeline import RAGForge
from scripts.run_benchmark import (
    _chunking_storage,
    _chunking_variants,
    _settings,
)


def _config(tmp_path):
    return {
        "index": {
            "backend": "qdrant_local",
            "qdrant_path": str(tmp_path / "base-qdrant"),
            "qdrant_collection": "benchmark",
            "index_manifest_path": str(tmp_path / "base-manifest.json"),
            "embedder_backend": "deterministic",
            "embedder_model": "deterministic-v1",
            "embedder_dim": 8,
            "chunk_strategy": "heading_chars",
            "chunk_size": 2200,
            "chunk_overlap": 200,
        },
        "chunking": {
            "variants": [
                {"chunk_size": 800, "chunk_overlap": 100},
                {"chunk_size": 2200, "chunk_overlap": 200},
            ]
        },
    }


def _chunk(chunk_id: str, doc_id: str) -> Chunk:
    return Chunk(id=chunk_id, doc_id=doc_id, title=doc_id, text=f"text {chunk_id}")


def test_chunking_variants_are_explicit_and_validated(tmp_path):
    variants = _chunking_variants(_config(tmp_path))

    assert variants == [
        {"chunk_size": 800, "chunk_overlap": 100},
        {"chunk_size": 2200, "chunk_overlap": 200},
    ]

    invalid = _config(tmp_path)
    invalid["chunking"]["variants"].append({"chunk_size": 800, "chunk_overlap": 100})
    with pytest.raises(ValueError, match="duplicate"):
        _chunking_variants(invalid)


def test_chunking_storage_is_unique_and_persistent_indexes_do_not_mix(tmp_path):
    config = _config(tmp_path)
    corpus = {"sha256": "corpus-sha"}
    variants = _chunking_variants(config)
    storages = [_chunking_storage(config, variant, corpus) for variant in variants]

    assert len({json.dumps(storage, sort_keys=True) for storage in storages}) == 2
    assert storages[0]["qdrant_path"] != storages[1]["qdrant_path"]
    assert storages[0]["qdrant_collection"] != storages[1]["qdrant_collection"]
    assert storages[0]["index_manifest_path"] != storages[1]["index_manifest_path"]

    settings_a = _settings(
        config,
        experiment="retrieval",
        chunk_size=800,
        chunk_overlap=100,
        storage=storages[0],
    )
    settings_b = _settings(
        config,
        experiment="retrieval",
        chunk_size=2200,
        chunk_overlap=200,
        storage=storages[1],
    )

    first = RAGForge(settings_a)
    first.ingest_chunks([_chunk("a", "doc-a")])
    first.close()

    second = RAGForge(settings_b)
    second.ingest_chunks([_chunk("b", "doc-b")])
    second.close()

    reopened_a = RAGForge(settings_a)
    reopened_b = RAGForge(settings_b)
    try:
        assert reopened_a.store.count() == 1
        assert [item.doc_id for item in reopened_a.store.list_chunks()] == ["doc-a"]
        assert reopened_b.store.count() == 1
        assert [item.doc_id for item in reopened_b.store.list_chunks()] == ["doc-b"]
    finally:
        reopened_a.close()
        reopened_b.close()
