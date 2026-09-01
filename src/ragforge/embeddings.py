"""嵌入抽象：本地开源模型(bge, 省钱/离线) 或 OpenAI 兼容 API。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from .config import Settings
from .observability import get_logger

logger = get_logger()


class BaseEmbedder(ABC):
    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:  # (n, dim)
        ...

    @property
    @abstractmethod
    def dim(self) -> int:
        ...


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

    def encode(self, texts: list[str]) -> np.ndarray:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        rows = [d.embedding for d in resp.data]
        return np.asarray(rows, dtype="float32")

    @property
    def dim(self) -> int:
        return self._dim


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
    if settings.embedder_backend == "local":
        return LocalEmbedder(settings.embedder_model, settings.embedder_dim)
    if settings.embedder_backend == "api":
        return ApiEmbedder(
            settings.llm_base_url, settings.embedder_api_key,
            settings.embedder_model, settings.embedder_dim,
        )
    # 兼容默认/测试环境
    return DeterministicEmbedder()