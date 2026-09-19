import numpy as np
import pytest

from ragforge.config import Settings
from ragforge.embeddings import OllamaEmbedder, build_embedder
from ragforge.ollama_client import OllamaModelNotFound, OllamaUnavailable


class RecordingEmbedClient:
    def __init__(self, rows_by_batch=None, error=None, digest=""):
        self.calls: list[tuple[str, list[str]]] = []
        self.rows_by_batch = list(rows_by_batch or [])
        self.error = error
        self.digest = digest

    def embed(self, model, texts):
        self.calls.append((model, texts))
        if self.error:
            raise self.error
        return self.rows_by_batch[len(self.calls) - 1]

    def model_digest(self, model):
        return self.digest


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "embedder_backend": "ollama",
        "embedder_model": "bge-m3",
        "embedder_dim": 3,
        "embedder_batch_size": 2,
        "generation_backend": "offline",
        "use_rerank": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_empty_input_returns_configured_shape_without_http():
    client = RecordingEmbedClient()
    embedder = OllamaEmbedder(_settings(), client=client)

    result = embedder.encode([])

    assert result.shape == (0, 3)
    assert result.dtype == np.float32
    assert client.calls == []


def test_embedding_is_batched_normalized_and_keeps_input_order():
    client = RecordingEmbedClient(
        rows_by_batch=[[[3.0, 0.0, 0.0], [0.0, 4.0, 0.0]], [[0.0, 0.0, 5.0]]]
    )
    embedder = OllamaEmbedder(_settings(), client=client)

    result = embedder.encode(["first", "second", "third"])

    assert client.calls == [("bge-m3", ["first", "second"]), ("bge-m3", ["third"])]
    assert result.tolist() == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert np.allclose(np.linalg.norm(result, axis=1), 1.0)


def test_ollama_embedder_exposes_provider_digest_for_index_identity():
    client = RecordingEmbedClient(digest="sha256:abc")
    embedder = OllamaEmbedder(_settings(), client=client)

    assert embedder.identity_digest == "sha256:abc"


@pytest.mark.parametrize(
    "rows, message",
    [
        ([[1.0, 0.0]], "returned 1 vectors"),
        ([[1.0, 0.0, 0.0, 0.0]], "dimension"),
        ([[float("nan"), 0.0, 0.0]], "finite"),
        ([[float("inf"), 0.0, 0.0]], "finite"),
        ([[0.0, 0.0, 0.0]], "zero"),
    ],
)
def test_embedding_rejects_invalid_batches(rows, message):
    client = RecordingEmbedClient(rows_by_batch=[rows])
    embedder = OllamaEmbedder(_settings(embedder_batch_size=16), client=client)

    with pytest.raises(ValueError, match=message):
        embedder.encode(["one", "two"] if len(rows) == 1 and len(rows[0]) == 2 else ["one"])


def test_dimension_conflict_mentions_reindex_and_does_not_pad_or_truncate():
    client = RecordingEmbedClient(rows_by_batch=[[[1.0, 0.0, 0.0, 0.0]]])
    embedder = OllamaEmbedder(_settings(embedder_dim=3), client=client)

    with pytest.raises(ValueError, match="reindex"):
        embedder.encode(["one"])


@pytest.mark.parametrize("error", [OllamaUnavailable("offline"), OllamaModelNotFound("missing")])
def test_embedding_propagates_ollama_errors(error):
    embedder = OllamaEmbedder(_settings(), client=RecordingEmbedClient(error=error))

    with pytest.raises(type(error)):
        embedder.encode(["one"])


def test_build_embedder_supports_ollama_and_keeps_local_alias():
    settings = _settings()
    assert isinstance(build_embedder(settings), OllamaEmbedder)

    local = _settings(embedder_backend="local", embedder_model="BAAI/bge-m3")
    assert local.embedder_backend == "local"


def test_api_embedder_close_is_idempotent():
    from ragforge.embeddings import ApiEmbedder

    class Client:
        def __init__(self):
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    client = Client()
    embedder = ApiEmbedder.__new__(ApiEmbedder)
    embedder._client = client

    embedder.close()
    embedder.close()

    assert client.close_calls == 1
