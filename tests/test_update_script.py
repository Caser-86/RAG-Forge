from types import SimpleNamespace

from ragforge.config import Settings
from scripts.update_knowledge import _settings_from_cli


def test_update_cli_does_not_inherit_reranker_from_env_by_default():
    base = Settings(_env_file=None, use_rerank=True)
    args = SimpleNamespace(
        vector_store=None,
        qdrant_url=None,
        qdrant_collection=None,
        index_manifest_path=None,
        knowledge_manifest_path=None,
        embedder_backend="ollama",
        embedder_model="bge-m3",
        use_rerank=False,
    )

    settings = _settings_from_cli(args, base)

    assert settings.use_rerank is False
