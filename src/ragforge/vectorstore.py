"""向量存储抽象：in_memory（默认/测试/本地演示）与 qdrant。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from .models import Chunk

# Qdrant 的 point id 只接受无符号整数或 UUID，不接受任意字符串。
# 用固定 namespace 把 chunk 的字符串 id 派生成稳定的 UUID，保证幂等且检索后能还原。
_QDRANT_ID_NS = NAMESPACE_URL


def _point_id(chunk_id: str) -> str:
    return str(uuid5(_QDRANT_ID_NS, chunk_id))


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunk: Chunk, vector: np.ndarray) -> None: ...

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        """返回 (chunk, cosine_similarity) 降序。"""

    @abstractmethod
    def __len__(self) -> int: ...


def _cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b))) if denom else 0.0


class InMemoryStore(VectorStore):
    def __init__(self):
        self._chunks: list[Chunk] = []
        self._vecs: list[np.ndarray] = []

    def add(self, chunk: Chunk, vector: np.ndarray) -> None:
        self._chunks.append(chunk)
        self._vecs.append(vector)

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        scored = [
            (chunk, _cos_sim(query_vector, v))
            for chunk, v in zip(self._chunks, self._vecs)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self._chunks)


class QdrantStore(VectorStore):
    def __init__(self, url: str, collection: str, dim: int):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as r

        self._client = QdrantClient(url=url)
        self._collection = collection
        self._client.recreate_collection(
            collection_name=collection,
            vectors_config=r.VectorParams(size=dim, distance=r.Distance.COSINE),
        )

    def add(self, chunk: Chunk, vector: np.ndarray) -> None:
        from qdrant_client.http import models as r

        self._client.upsert(
            collection_name=self._collection,
            points=[r.PointStruct(id=_point_id(chunk.id), vector=vector.tolist(), payload={
                "id": chunk.id, "doc_id": chunk.doc_id, "title": chunk.title,
                "text": chunk.text, "source": chunk.source, "meta": chunk.meta,
            })],
        )

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        # qdrant-client >=1.7 用 query_points 取代 search；返回 records 各含 .id/.payload/.score
        resp = self._client.query_points(
            collection_name=self._collection,
            query=query_vector.tolist(),
            limit=top_k,
        )
        out = []
        for h in resp.points:
            p = h.payload
            out.append((Chunk(
                id=p.get("id", str(h.id)),
                doc_id=p.get("doc_id", ""),
                title=p.get("title", ""),
                text=p.get("text", ""),
                source=p.get("source", ""),
                meta=p.get("meta", {}),
            ), h.score))
        return out

    def __len__(self) -> int:
        return self._client.count(self._collection).count


def build_store(settings, dim: int) -> VectorStore:
    if settings.vector_store == "qdrant":
        return QdrantStore(settings.qdrant_url, "rag_forge", dim)
    return InMemoryStore()