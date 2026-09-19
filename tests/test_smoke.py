from scripts.smoke import offline_settings


def test_smoke_uses_explicit_offline_settings():
    settings = offline_settings()

    assert settings.vector_store == "in_memory"
    assert settings.embedder_backend == "deterministic"
    assert settings.llm_api_key == ""
    assert settings.use_rerank is False
