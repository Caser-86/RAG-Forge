from ragforge.config import Settings
from ragforge.generator import OfflineGenerator, OllamaGenerator, build_generator
from ragforge.models import Chunk, Evidence


class RecordingOllama:
    def __init__(self):
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def generate(self, model, messages, *, stream=False):
        self.calls.append((model, messages))
        return f"answer from {model}"


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "generation_backend": "ollama",
        "default_generation_model": "gemma3:4b",
        "allowed_generation_models": ["gemma3:4b", "gemma4:e4b"],
        "embedder_backend": "deterministic",
        "embedder_dim": 8,
        "use_rerank": False,
    }
    values.update(overrides)
    return Settings(**values)


def _evidence() -> list[Evidence]:
    return [
        Evidence(
            chunk=Chunk(id="c1", doc_id="d1", title="doc", text="RAG combines search and generation."),
            fused_score=1.0,
        )
    ]


def test_ollama_generator_passes_model_per_request_without_mutating_shared_state():
    client = RecordingOllama()
    generator = OllamaGenerator(_settings(), client=client)

    first = generator.generate("what is rag?", _evidence(), "trace-1", model="gemma3:4b")
    second = generator.generate("what is rag?", _evidence(), "trace-2", model="gemma4:e4b")

    assert [model for model, _ in client.calls] == ["gemma3:4b", "gemma4:e4b"]
    assert first.model == "gemma3:4b"
    assert second.model == "gemma4:e4b"
    assert generator.default_model == "gemma3:4b"


def test_generation_backend_is_explicit_and_does_not_follow_legacy_api_key():
    offline = _settings(generation_backend="offline", llm_api_key="legacy-secret")
    assert isinstance(build_generator(offline), OfflineGenerator)

    ollama = _settings(generation_backend="ollama", llm_api_key="legacy-secret")
    assert isinstance(build_generator(ollama), OllamaGenerator)
