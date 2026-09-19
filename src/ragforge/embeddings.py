"""嵌入抽象：本地开源模型(bge, 省钱/离线) 或 OpenAI 兼容 API。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from .config import Settings
from .observability import get_logger
from .ollama_client import OllamaClient

logger = get_logger()


class BaseEmbedder(ABC):
    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:  # (n, dim)
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        ...

    @property
    def identity_digest(self) -> str:
        """Provider revision when it is available without guessing."""
        return ""


class LocalEmbedder(BaseEmbedder):
    """基于 sentence-transformers 的本地嵌入（如 BAAI/bge-m3），离线运行。"""

    def __init__(self, model_name: str, dim: int):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dim = dim
        logger.info("Local embedder loaded: %s", model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self._model.encode(texts, normalize_embeddings=True)

    @property
    def dim(self) -> int:
        return self._dim


class ApiEmbedder(BaseEmbedder):
    """OpenAI 兼容嵌入 API。"""

    def __init__(self, base_url: str, api_key: str, model: str, dim: int):
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key or "none")
        self._model = model
        self._dim = dim
        self._closed = False

    def encode(self, texts: list[str]) -> np.ndarray:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        rows = [d.embedding for d in resp.data]
        return np.asarray(rows, dtype="float32")

    @property
    def dim(self) -> int:
        return self._dim

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._client.close()
        self._closed = True


class OllamaEmbedder(BaseEmbedder):
    """Ollama bge-m3 embedder with stable batching and strict vector validation."""

    def __init__(self, settings: Settings, client: OllamaClient | None = None):
        self._model = settings.embedder_model
        self._dim = settings.embedder_dim
        self._batch_size = settings.embedder_batch_size
        self._client = client or OllamaClient(
            settings.ollama_base_url,
            connect_timeout=settings.ollama_connect_timeout,
            generate_timeout=settings.ollama_generate_timeout,
        )
        self._dimension_verified = False
        self._identity_digest = settings.embedder_digest
        self._closed = False

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)

        rows: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            batch_rows = self._client.embed(self._model, batch)
            if len(batch_rows) != len(batch):
                raise ValueError(
                    f"Ollama returned {len(batch_rows)} vectors for {len(batch)} texts"
                )
            rows.extend(batch_rows)

        try:
            matrix = np.asarray(rows, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ollama embeddings must contain numeric values") from exc
        if matrix.ndim != 2 or matrix.shape[0] != len(texts):
            raise ValueError("Ollama embeddings have an invalid matrix shape")
        actual_dim = matrix.shape[1]
        if actual_dim != self._dim:
            raise ValueError(
                f"Ollama embedding dimension {actual_dim} conflicts with configured {self._dim}; "
                "reindex is required"
            )
        self._dimension_verified = True

        if not np.isfinite(matrix).all():
            raise ValueError("Ollama embeddings must contain only finite values")
        norms = np.linalg.norm(matrix, axis=1)
        if not np.isfinite(norms).all() or np.any(norms == 0):
            raise ValueError("Ollama embeddings cannot contain non-finite or zero vectors")
        matrix /= norms[:, None]
        return matrix.astype(np.float32, copy=False)

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def identity_digest(self) -> str:
        if self._identity_digest:
            return self._identity_digest
        try:
            digest = self._client.model_digest(self._model)
        except AttributeError:
            # Lightweight test doubles and custom clients may only implement
            # /api/embed; an explicit configured digest remains supported.
            return ""
        except Exception as exc:  # provider identity is diagnostic, not a guess
            logger.warning("Unable to resolve Ollama model digest: %s", type(exc).__name__)
            return ""
        self._identity_digest = digest
        return digest

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._client.close()
        self._closed = True


class DeterministicEmbedder(BaseEmbedder):
    """离线/无模型时的确定性退避（测试与 smoke 用，不计入真实指标）。"""

    def __init__(self, dim: int = 64):
        import hashlib

        self._hash = hashlib.sha1
        self._dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self._dim), dtype="float32")
        for i, t in enumerate(texts):
            d = self._hash(t.encode("utf-8")).digest()
            for j in range(self._dim):
                out[i, j] = (d[j % len(d)] / 255.0) - 0.5
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out

    @property
    def dim(self) -> int:
        return self._dim


def build_embedder(settings: Settings) -> BaseEmbedder:
    if settings.embedder_backend == "ollama":
        return OllamaEmbedder(settings)
    if settings.embedder_backend == "local":
        return LocalEmbedder(settings.embedder_model, settings.embedder_dim)
    if settings.embedder_backend == "api":
        return ApiEmbedder(
            settings.llm_base_url, settings.embedder_api_key,
            settings.embedder_model, settings.embedder_dim,
        )
    if settings.embedder_backend == "deterministic":
        return DeterministicEmbedder(settings.embedder_dim)
    raise ValueError(f"unsupported embedder backend: {settings.embedder_backend}")
