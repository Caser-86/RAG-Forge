from threading import Event, Thread
from time import monotonic
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from ragforge.api import main as api
from ragforge.config import Settings
from ragforge.models import Answer
from ragforge.ollama_client import OllamaTimeout, OllamaUnavailable
from ragforge.retriever.rerank import RerankerUnavailable


class FakeEngine:
    calls: ClassVar[list[tuple[str, str | None]]] = []
    mode_calls: ClassVar[list[tuple[str | None, int | None]]] = []
    rewrite_calls: ClassVar[list[tuple[bool | None, list[dict[str, str]] | None]]] = []
    trace_record: ClassVar[dict[str, object]] = {
        "trace_id": "trace-api",
        "original_query": "question",
        "timings": {"total": 1.0},
    }

    def __init__(self):
        self.store = []

    def ask(
        self,
        query: str,
        model: str | None = None,
        retrieval_mode: str | None = None,
        top_k: int | None = None,
        history: list[dict[str, str]] | None = None,
        rewrite: bool | None = None,
    ) -> Answer:
        self.calls.append((query, model))
        self.mode_calls.append((retrieval_mode, top_k))
        self.rewrite_calls.append((rewrite, history))
        return Answer(answer=f"answer from {model}", model=model or "gemma3:4b", trace_id="trace-api")

    def get_trace(self, trace_id: str):
        return self.trace_record if trace_id == "trace-api" else None


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "generation_backend": "ollama",
        "default_generation_model": "gemma3:4b",
        "allowed_generation_models": ["gemma3:4b", "gemma4:e4b"],
        "ollama_base_url": "http://ollama.test",
        "api_key": "",
        "rate_limit_per_minute": 1000,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def api_client(monkeypatch):
    settings = _settings()
    fake_models = ["gemma3:4b", "gemma4:e4b", "bge-m3:latest", "qwen3:0.6b"]

    class FakeOllamaClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_models(self):
            return fake_models

        def close(self):
            pass

    FakeEngine.calls = []
    FakeEngine.mode_calls = []
    FakeEngine.rewrite_calls = []
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "OllamaClient", FakeOllamaClient)
    monkeypatch.setattr(api, "RAGForge", FakeEngine)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        yield client


def test_models_endpoint_returns_installed_allowed_model_intersection(api_client):
    response = api_client.get("/api/models")

    assert response.status_code == 200
    body = response.json()
    assert body["generation"] == ["gemma3:4b", "gemma4:e4b"]
    assert body["embedding"] == ["bge-m3"]
    assert body["utility"] == ["qwen3:0.6b"]
    assert body["missing_models"] == []
    assert body["reranker_available"] is False


def test_api_backend_uses_llm_model_as_default_and_keeps_allowlist():
    settings = _settings(
        generation_backend="api",
        llm_model="deepseek-chat",
        allowed_generation_models=["gemma3:4b", "deepseek-chat", "deepseek-reasoner"],
        default_generation_model="gemma3:4b",
    )

    catalog = api._model_catalog(settings, [])

    assert catalog["generation"] == ["gemma3:4b", "deepseek-chat", "deepseek-reasoner"]
    assert api._select_generation_model(settings, None, []) == "deepseek-chat"
    assert api._select_generation_model(settings, "deepseek-reasoner", []) == "deepseek-reasoner"


def test_slow_generation_does_not_hold_global_lock_over_health(monkeypatch):
    settings = _settings(generation_backend="offline")
    entered = Event()
    release = Event()

    class SlowEngine(FakeEngine):
        def ask(self, *args, **kwargs):
            entered.set()
            assert release.wait(timeout=2)
            return Answer(answer="done", model="offline", trace_id="trace-slow")

    previous_engine = api.engine
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "engine", SlowEngine())
    try:
        worker = Thread(
            target=api.chat,
            args=(api.ChatRequest(query="slow"),),
            daemon=True,
        )
        worker.start()
        assert entered.wait(timeout=2)

        started = monotonic()
        health = api.health()
        elapsed = monotonic() - started

        assert health["status"] == "ok"
        assert elapsed < 0.5
    finally:
        release.set()
        worker.join(timeout=2)
        monkeypatch.setattr(api, "engine", previous_engine)


def test_chat_returns_requested_and_actual_model_and_keeps_calls_isolated(api_client):
    first = api_client.post("/api/chat", json={"query": "one", "generation_model": "gemma3:4b"})
    second = api_client.post("/api/chat", json={"query": "two", "generation_model": "gemma4:e4b"})

    assert first.status_code == 200
    assert first.json()["requested_model"] == "gemma3:4b"
    assert first.json()["model"] == "gemma3:4b"
    assert second.status_code == 200
    assert second.json()["requested_model"] == "gemma4:e4b"
    assert second.json()["model"] == "gemma4:e4b"
    assert FakeEngine.calls == [("one", "gemma3:4b"), ("two", "gemma4:e4b")]


def test_chat_rejects_unknown_or_uninstalled_model_before_engine_call(api_client, monkeypatch):
    response = api_client.post("/api/chat", json={"query": "one", "generation_model": "qwen3:0.6b"})
    assert response.status_code == 422
    assert FakeEngine.calls == []

    class OnlyDefaultClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_models(self):
            return ["gemma3:4b"]

        def close(self):
            pass

    monkeypatch.setattr(api, "OllamaClient", OnlyDefaultClient)
    response = api_client.post("/api/chat", json={"query": "one", "generation_model": "gemma4:e4b"})
    assert response.status_code == 422
    assert FakeEngine.calls == []


def test_chat_passes_retrieval_mode_and_top_k_to_engine(api_client):
    response = api_client.post(
        "/api/chat",
        json={"query": "one", "retrieval_mode": "dense", "top_k": 2},
    )

    assert response.status_code == 200
    assert FakeEngine.mode_calls == [("dense", 2)]


def test_chat_rejects_unknown_retrieval_mode(api_client):
    response = api_client.post(
        "/api/chat",
        json={"query": "one", "retrieval_mode": "not-a-mode"},
    )

    assert response.status_code == 422


def test_chat_passes_bounded_history_and_rewrite_flag(api_client):
    response = api_client.post(
        "/api/chat",
        json={
            "query": "follow up",
            "rewrite": True,
            "history": [{"role": "user", "content": "previous"}],
        },
    )

    assert response.status_code == 200
    assert FakeEngine.rewrite_calls == [(True, [{"role": "user", "content": "previous"}])]


def test_chat_rejects_history_over_limit(api_client):
    response = api_client.post(
        "/api/chat",
        json={
            "query": "follow up",
            "history": [{"role": "user", "content": str(index)} for index in range(21)],
        },
    )

    assert response.status_code == 422


def test_chat_returns_503_for_unavailable_reranker(api_client, monkeypatch):
    class UnavailableRerankEngine(FakeEngine):
        def ask(self, *args, **kwargs):
            raise RerankerUnavailable("reranker model cache is not available")

    monkeypatch.setattr(api, "RAGForge", UnavailableRerankEngine)
    with TestClient(api.app) as client:
        response = client.post(
            "/api/chat",
            json={"query": "one", "retrieval_mode": "hybrid_rerank"},
        )

    assert response.status_code == 503


def test_models_and_health_report_missing_reranker_cache(tmp_path, monkeypatch):
    settings = _settings(use_rerank=True, rerank_model=str(tmp_path / "not-installed"))
    fake_models = ["gemma3:4b", "gemma4:e4b", "bge-m3:latest", "qwen3:0.6b"]

    class FakeOllamaClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_models(self):
            return fake_models

        def close(self):
            pass

    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "OllamaClient", FakeOllamaClient)
    monkeypatch.setattr(api, "RAGForge", FakeEngine)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        models_response = client.get("/api/models")
        health_response = client.get("/api/health")

    assert models_response.status_code == 200
    assert models_response.json()["reranker_available"] is False
    assert "cache" in models_response.json()["reranker_reason"]
    assert health_response.json()["reranker_available"] is False
    assert "cache" in health_response.json()["reranker_reason"]


def test_api_maps_ollama_unavailable_and_timeout(api_client, monkeypatch):
    class UnavailableClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_models(self):
            raise OllamaUnavailable("offline")

        def close(self):
            pass

    monkeypatch.setattr(api, "OllamaClient", UnavailableClient)
    assert api_client.get("/api/models").status_code == 503
    assert api_client.post("/api/chat", json={"query": "one"}).status_code == 503

    class TimeoutClient(UnavailableClient):
        def list_models(self):
            raise OllamaTimeout("slow")

    monkeypatch.setattr(api, "OllamaClient", TimeoutClient)
    assert api_client.get("/api/models").status_code == 504
    assert api_client.post("/api/chat", json={"query": "one"}).status_code == 504


def test_trace_endpoint_returns_structured_record(api_client):
    response = api_client.get("/api/traces/trace-api")

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-api"
    assert "timings" in response.json()
    assert api_client.get("/api/traces/missing").status_code == 404


def test_trace_endpoint_uses_same_api_key_policy(monkeypatch):
    settings = _settings(api_key="密钥")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "RAGForge", FakeEngine)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        response = client.get("/api/traces/trace-api")

    assert response.status_code == 401


def test_api_key_is_checked_by_real_http_route(monkeypatch):
    settings = _settings(api_key="密钥")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        response = client.get("/api/models")
    assert response.status_code == 401
