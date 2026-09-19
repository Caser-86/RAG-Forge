import pytest

from ragforge.generator import build_llm_messages
from ragforge.ollama_client import OllamaClient


@pytest.mark.integration
def test_live_ollama_generates_with_both_allowed_models(request):
    if not request.config.getoption("--run-ollama"):
        pytest.skip("pass --run-ollama to run local Ollama integration tests")

    client = OllamaClient("http://127.0.0.1:11434", generate_timeout=180)
    try:
        installed = client.list_models()
        for model in ("gemma3:4b", "gemma4:e4b"):
            assert model in installed
            answer = client.generate(
                model,
                build_llm_messages("What does RAG combine?", "RAG combines retrieval with generation."),
            )
            assert answer.strip()
    finally:
        client.close()
