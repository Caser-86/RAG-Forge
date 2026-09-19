import json

import httpx
import pytest

from ragforge.ollama_client import (
    OllamaClient,
    OllamaModelNotFound,
    OllamaProtocolError,
    OllamaTimeout,
    OllamaUnavailable,
)


def _client(handler):
    return OllamaClient(
        "http://ollama.test",
        connect_timeout=0.1,
        generate_timeout=0.2,
        transport=httpx.MockTransport(handler),
    )


def test_list_models_parses_ollama_tags_response_and_health():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "gemma3:4b"}, {"name": "bge-m3:latest"}]},
        )

    client = _client(handler)
    assert client.list_models() == ["gemma3:4b", "bge-m3:latest"]
    assert client.health() is True
    client.close()


def test_model_digest_reads_provider_revision_and_supports_latest_alias():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "bge-m3:latest", "digest": "sha256:abc"}]},
        )

    client = _client(handler)
    assert client.model_digest("bge-m3") == "sha256:abc"
    client.close()


def test_generate_uses_non_streaming_chat_protocol_and_returns_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/chat"
        assert json.loads(request.content) == {
            "model": "gemma3:4b",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "world"}, "done": True},
        )

    client = _client(handler)
    assert client.generate("gemma3:4b", [{"role": "user", "content": "hello"}]) == "world"
    with pytest.raises(ValueError, match="streaming"):
        client.generate("gemma3:4b", [], stream=True)
    client.close()


def test_generate_includes_explicit_generation_options_when_requested():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {
            "model": "gemma3:4b",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 512, "seed": 42},
        }
        return httpx.Response(200, json={"message": {"content": "world"}})

    client = _client(handler)
    assert client.generate(
        "gemma3:4b",
        [{"role": "user", "content": "hello"}],
        options={"temperature": 0.2, "num_predict": 512, "seed": 42},
    ) == "world"
    client.close()


def test_embed_uses_batch_input_and_parses_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/embed"
        assert json.loads(request.content) == {
            "model": "bge-m3",
            "input": ["first", "second"],
        }
        return httpx.Response(200, json={"model": "bge-m3", "embeddings": [[1.0, 0.0], [0.0, 1.0]]})

    client = _client(handler)
    assert client.embed("bge-m3", ["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]
    client.close()


def test_generate_classifies_model_not_found_and_server_errors():
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    with pytest.raises(OllamaModelNotFound):
        _client(not_found).generate("missing", [])

    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "overloaded"})

    with pytest.raises(OllamaUnavailable):
        _client(server_error).generate("gemma3:4b", [])


def test_generate_rejects_timeout_connection_failure_and_bad_or_empty_payload():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(OllamaTimeout):
        _client(timeout).generate("gemma3:4b", [])

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(OllamaUnavailable):
        _client(unavailable).generate("gemma3:4b", [])

    for payload in ({}, {"message": {}}, {"message": {"content": ""}}):
        with pytest.raises(OllamaProtocolError):
            _client(lambda request, payload=payload: httpx.Response(200, json=payload)).generate(
                "gemma3:4b", []
            )


def test_health_is_false_for_protocol_and_network_failures():
    def bad_tags(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    assert _client(bad_tags).health() is False

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    assert _client(timeout).health() is False
