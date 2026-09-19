import numpy as np
import pytest

from ragforge.config import Settings
from ragforge.embeddings import OllamaEmbedder
from ragforge.models import Chunk
from ragforge.ollama_client import OllamaClient
from ragforge.pipeline import RAGForge

TEXTS = [
    "RAG combines retrieval with language model generation",
    "Retrieval augmented generation combines search and a language model",
    "Bananas grow in warm tropical climates",
]


def test_live_ollama_embedding_and_minimal_recall(request):
    if not request.config.getoption("--run-ollama"):
        pytest.skip("pass --run-ollama to run local Ollama integration tests")

    settings = Settings(
        _env_file=None,
        embedder_backend="ollama",
        embedder_model="bge-m3",
        embedder_dim=1024,
        embedder_batch_size=16,
        generation_backend="offline",
        vector_store="in_memory",
        use_rerank=False,
    )
    client = OllamaClient(settings.ollama_base_url, generate_timeout=120)
    embedder = OllamaEmbedder(settings, client=client)
    try:
        vectors = embedder.encode(TEXTS)
        assert vectors.shape == (3, 1024)
        assert vectors.dtype == np.float32
        assert np.isfinite(vectors).all()
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)

        similarities = vectors @ vectors.T
        assert float(similarities[0, 1]) > float(similarities[0, 2])

        engine = RAGForge(settings)
        engine.embedder = embedder
        engine.ingest_chunks(
            [Chunk(id=f"c{i}", doc_id=f"d{i}", title=f"doc-{i}", text=text) for i, text in enumerate(TEXTS)]
        )
        hits = engine.retrieve_only("What does RAG combine?")
        assert hits
        assert {hit.chunk.doc_id for hit in hits[:2]} & {"d0", "d1"}
    finally:
        client.close()
