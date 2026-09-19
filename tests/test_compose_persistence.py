from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_persists_api_identity_and_knowledge_state_separately():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "- api_state:/app/data" in compose
    assert "api_state:" in compose
    assert "RAG_INDEX_MANIFEST_PATH: /app/data/index_manifest.json" in compose
    assert "RAG_KNOWLEDGE_MANIFEST_PATH: /app/data/knowledge_manifest.sqlite3" in compose


def test_ollama_override_keeps_api_state_paths_explicit():
    override = (ROOT / "docker-compose.ollama.yml").read_text(encoding="utf-8")

    assert "RAG_INDEX_MANIFEST_PATH: /app/data/index_manifest.json" in override
    assert "RAG_KNOWLEDGE_MANIFEST_PATH: /app/data/knowledge_manifest.sqlite3" in override
