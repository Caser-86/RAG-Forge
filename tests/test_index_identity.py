import json

import numpy as np
import pytest

import ragforge.index_manifest as index_manifest_module
from ragforge.config import Settings
from ragforge.index_manifest import (
    IndexIdentityMismatch,
    IndexManifestError,
    LegacyIndexError,
    build_index_manifest,
    ensure_compatible,
    load_manifest,
    write_manifest,
)
from ragforge.ingest.chunker import CHUNK_ALGORITHM_VERSION
from ragforge.models import Chunk
from ragforge.pipeline import RAGForge
from ragforge.vectorstore import build_store


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "embedder_backend": "deterministic",
        "embedder_model": "deterministic-v1",
        "embedder_dim": 8,
        "vector_store": "qdrant_local",
        "qdrant_collection": "test",
        "chunk_size": 800,
        "chunk_overlap": 100,
        "generation_backend": "offline",
        "use_rerank": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_manifest_is_written_atomically_and_loaded(tmp_path):
    path = tmp_path / "index_manifest.json"
    manifest = build_index_manifest(_settings(), dimension=8, active_collection="test")

    write_manifest(path, manifest)

    assert load_manifest(path) == manifest
    assert list(tmp_path.glob("*.tmp")) == []
    assert manifest["tokenizer_version"]
    assert manifest["schema_version"] == 2
    assert manifest["embedder_backend"] == "deterministic"
    assert manifest["embedding_digest"] == ""
    assert manifest["chunk_algorithm_version"] == CHUNK_ALGORITHM_VERSION


def test_manifest_write_retries_transient_windows_replace_error(tmp_path, monkeypatch):
    path = tmp_path / "index_manifest.json"
    manifest = build_index_manifest(_settings(), dimension=8, active_collection="test")
    original_replace = index_manifest_module.os.replace
    attempts = {"count": 0}

    def replace_with_transient_lock(source, target):
        if attempts["count"] == 0:
            attempts["count"] += 1
            raise PermissionError(5, "access denied")
        return original_replace(source, target)

    monkeypatch.setattr(index_manifest_module.os, "replace", replace_with_transient_lock)

    write_manifest(path, manifest)

    assert attempts["count"] == 1
    assert load_manifest(path) == manifest


def test_identity_mismatch_is_blocked_for_model_dimension_and_chunk_config(tmp_path):
    path = tmp_path / "index_manifest.json"
    manifest = build_index_manifest(_settings(), dimension=8, active_collection="test")
    write_manifest(path, manifest)

    for changed in (
        {"embedding_model": "other-model"},
        {"embedder_backend": "local"},
        {"embedding_digest": "sha256:other-model-revision"},
        {"dimension": 16},
        {"chunk_size": 1000},
        {"chunk_algorithm_version": "heading-window-v1"},
    ):
        expected = dict(manifest)
        expected.update(changed)
        with pytest.raises(IndexIdentityMismatch):
            ensure_compatible(load_manifest(path), expected)


def test_missing_or_corrupt_manifest_is_not_treated_as_known_identity(tmp_path):
    expected = build_index_manifest(_settings(), dimension=8, active_collection="test")

    with pytest.raises(LegacyIndexError):
        ensure_compatible(None, expected)

    path = tmp_path / "index_manifest.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        load_manifest(path)


def test_legacy_manifest_without_new_identity_fields_requires_reindex(tmp_path):
    path = tmp_path / "index_manifest.json"
    legacy = build_index_manifest(_settings(), dimension=8, active_collection="test")
    legacy["schema_version"] = 1
    for field in ("embedder_backend", "embedding_digest", "chunk_algorithm_version"):
        legacy.pop(field, None)
    path.write_text(json.dumps(legacy), encoding="utf-8")

    with pytest.raises(IndexManifestError, match="fields"):
        load_manifest(path)


def test_manifest_with_old_schema_number_is_rejected_even_if_fields_exist(tmp_path):
    path = tmp_path / "index_manifest.json"
    legacy = build_index_manifest(_settings(), dimension=8, active_collection="test")
    legacy["schema_version"] = 1
    path.write_text(json.dumps(legacy), encoding="utf-8")

    with pytest.raises(IndexManifestError, match="schema"):
        load_manifest(path)


def test_ragforge_refuses_nonempty_legacy_store_without_manifest(tmp_path):
    settings = _settings(
        qdrant_path=tmp_path / "qdrant",
        index_manifest_path=tmp_path / "index_manifest.json",
    )
    store = build_store(settings, 8)
    store.add(
        Chunk(id="legacy", doc_id="d1", title="old", text="old"),
        np.ones(8, dtype=np.float32),
    )
    store.close()

    with pytest.raises(LegacyIndexError, match="reindex"):
        RAGForge(settings)
