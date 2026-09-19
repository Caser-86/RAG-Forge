from pathlib import Path

import pytest
from pydantic import ValidationError

from ragforge.config import Settings
from ragforge.embeddings import DeterministicEmbedder, build_embedder


def test_settings_reject_unknown_vector_store():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vector_store="pgvector")


def test_settings_reject_unknown_embedder_backend():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, embedder_backend="mystery")


def test_settings_reject_overlap_that_can_never_advance():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_size=100, chunk_overlap=100)


def test_local_generation_defaults_and_bge_is_not_a_generation_model():
    settings = Settings(_env_file=None)
    assert settings.generation_backend == "ollama"
    assert settings.default_generation_model == "gemma3:4b"
    assert settings.allowed_generation_models == ["gemma3:4b", "gemma4:e4b"]
    assert settings.use_rerank is False

    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_generation_models=["bge-m3"])


def test_api_generation_requires_llm_model_in_explicit_allowlist():
    with pytest.raises(ValidationError, match="llm_model"):
        Settings(
            _env_file=None,
            generation_backend="api",
            llm_model="deepseek-chat",
            allowed_generation_models=["gemma3:4b"],
        )


def test_env_example_does_not_define_empty_numeric_generation_values():
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    lines = {line.strip() for line in example.splitlines()}

    for name in ("RAG_GENERATION_TEMPERATURE", "RAG_GENERATION_NUM_PREDICT", "RAG_GENERATION_SEED"):
        assert f"{name}=" not in lines
        assert any(line.startswith(f"# {name}=") for line in lines)


def test_ollama_embedding_defaults_and_batch_size():
    settings = Settings(_env_file=None, embedder_backend="ollama")
    assert settings.embedder_backend == "ollama"
    assert settings.embedder_model == "bge-m3"
    assert settings.embedder_batch_size == 16


def test_retrieval_and_heading_chunk_defaults_are_explicit():
    settings = Settings(_env_file=None)

    assert settings.retrieval_mode == "hybrid"
    assert settings.dense_top_k == 20
    assert settings.sparse_top_k == 20
    assert settings.top_k == 5
    assert settings.chunk_strategy == "heading_chars"
    assert settings.chunk_size == 2200
    assert settings.chunk_overlap == 200


def test_deterministic_embedder_uses_configured_dimension():
    settings = Settings(_env_file=None, embedder_backend="deterministic", embedder_dim=32)
    embedder = build_embedder(settings)

    assert isinstance(embedder, DeterministicEmbedder)
    assert embedder.dim == 32
    assert embedder.encode(["hello"]).shape == (1, 32)
