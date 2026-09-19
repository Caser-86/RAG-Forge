"""向量存储抽象：qdrant_local、qdrant_server 与 in_memory。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from .models import Chunk

# Qdrant 的 point id 只接受无符号整数或 UUID，不接受任意字符串。
# 用固定 namespace 把 chunk 的字符串 id 派生成稳定的 UUID，保证幂等且检索后能还原。
_QDRANT_ID_NS = NAMESPACE_URL


def _point_id(chunk_id: str) -> str:
    return str(uuid5(_QDRANT_ID_NS, chunk_id))


def _collection_vector_size(collection_info) -> int | None:
    params = getattr(getattr(collection_info, "config", None), "params", None)
    vectors = getattr(params, "vectors", None)
    if vectors is None:
        return None
    if isinstance(vectors, dict):
        sizes = {getattr(value, "size", None) for value in vectors.values()}
        if len(sizes) == 1:
            return sizes.pop()
        return None
    return getattr(vectors, "size", None)


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunk: Chunk, vector: np.ndarray) -> None: ...

    def add(self, chunk: Chunk, vector: np.ndarray) -> None:
        self.upsert(chunk, vector)

    def add_many(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        """Write a batch while keeping the single-item API as a safe fallback."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        for chunk, vector in zip(chunks, vectors, strict=True):
            self.add(chunk, vector)

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        """返回 (chunk, cosine_similarity) 降序。"""

    @abstractmethod
    def list_chunks(self) -> list[Chunk]:
        """返回当前存储的全部 chunk 元数据，用于重建稀疏索引。"""

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def exists(self, chunk_id: str) -> bool: ...

    @abstractmethod
    def delete_document(self, doc_id: str, version: int | None = None) -> int: ...

    @abstractmethod
    def delete_chunks(self, chunk_ids: list[str]) -> int: ...

    @abstractmethod
    def set_document_active(self, doc_id: str, active: bool) -> int: ...

    @abstractmethod
    def delete_document_except_version(self, doc_id: str, keep_version: int) -> int: ...

    @abstractmethod
    def close(self) -> None: ...

    def __len__(self) -> int:
        return self.count()


class VectorStoreError(RuntimeError):
    """Base exception for vector store lifecycle failures."""


class VectorStoreOpenError(VectorStoreError):
    """A local vector store path is already open or cannot be opened safely."""


def _chunk_to_payload(chunk: Chunk) -> dict:
    """Encode current and future metadata in one payload format."""
    return {
        "payload_schema_version": 1,
        "id": chunk.id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "text": chunk.text,
        "source": chunk.source,
        "source_url": chunk.source_url,
        "heading_path": list(chunk.heading_path),
        "chunk_index": chunk.chunk_index,
        "meta": dict(chunk.meta),
    }


def _chunk_from_payload(payload: dict | None, fallback_id: str = "") -> Chunk:
    """Decode old payloads too; missing M3 fields use model defaults."""
    payload = payload or {}
    heading_path = payload.get("heading_path", [])
    if not isinstance(heading_path, list) or not all(isinstance(item, str) for item in heading_path):
        heading_path = []
    meta = payload.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    chunk_index = payload.get("chunk_index", 0)
    if not isinstance(chunk_index, int) or isinstance(chunk_index, bool):
        chunk_index = 0
    return Chunk(
        id=payload.get("id") or fallback_id,
        doc_id=payload.get("doc_id", ""),
        title=payload.get("title", ""),
        text=payload.get("text", ""),
        source=payload.get("source", ""),
        source_url=payload.get("source_url"),
        heading_path=heading_path,
        chunk_index=chunk_index,
        meta=meta,
    )


def _cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b))) if denom else 0.0


class InMemoryStore(VectorStore):
    def __init__(self):
        self._chunks: list[Chunk] = []
        self._vecs: list[np.ndarray] = []

    def upsert(self, chunk: Chunk, vector: np.ndarray) -> None:
        for i, existing in enumerate(self._chunks):
            if existing.id == chunk.id:
                self._chunks[i] = chunk
                self._vecs[i] = vector
                return
        self._chunks.append(chunk)
        self._vecs.append(vector)

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        scored = [
            (chunk, _cos_sim(query_vector, v))
            for chunk, v in zip(self._chunks, self._vecs, strict=True)
            if _chunk_is_active(chunk)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def __len__(self) -> int:
        return len(self._chunks)

    def count(self) -> int:
        return len(self.list_chunks())

    def exists(self, chunk_id: str) -> bool:
        return any(chunk.id == chunk_id and _chunk_is_active(chunk) for chunk in self._chunks)

    def delete_document(self, doc_id: str, version: int | None = None) -> int:
        kept = [
            (chunk, vector)
            for chunk, vector in zip(self._chunks, self._vecs, strict=True)
            if chunk.doc_id != doc_id or (
                version is not None and chunk.meta.get("document_version") != version
            )
        ]
        removed = len(self._chunks) - len(kept)
        self._chunks = [chunk for chunk, _ in kept]
        self._vecs = [vector for _, vector in kept]
        return removed

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        ids = set(chunk_ids)
        if not ids:
            return 0
        kept = [
            (chunk, vector)
            for chunk, vector in zip(self._chunks, self._vecs, strict=True)
            if chunk.id not in ids
        ]
        removed = len(self._chunks) - len(kept)
        self._chunks = [chunk for chunk, _ in kept]
        self._vecs = [vector for _, vector in kept]
        return removed

    def close(self) -> None:
        # In-memory storage owns no external resource; retain data for idempotent shutdown.
        return None

    def list_chunks(self) -> list[Chunk]:
        return [chunk for chunk in self._chunks if _chunk_is_active(chunk)]

    def set_document_active(self, doc_id: str, active: bool) -> int:
        changed = 0
        for chunk in self._chunks:
            if chunk.doc_id == doc_id and chunk.meta.get("active", True) != active:
                chunk.meta["active"] = active
                changed += 1
        return changed

    def delete_document_except_version(self, doc_id: str, keep_version: int) -> int:
        kept = [
            (chunk, vector)
            for chunk, vector in zip(self._chunks, self._vecs, strict=True)
            if chunk.doc_id != doc_id or chunk.meta.get("document_version") == keep_version
        ]
        removed = len(self._chunks) - len(kept)
        self._chunks = [chunk for chunk, _ in kept]
        self._vecs = [vector for _, vector in kept]
        return removed


class QdrantStore(VectorStore):
    def __init__(
        self,
        url: str | None = None,
        collection: str = "rag_forge",
        dim: int = 1024,
        api_key: str = "",
        *,
        path: str | Path | None = None,
    ):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as r

        self._collection = collection
        self._closed = False
        self._local_path = Path(path) if path is not None else None
        try:
            if self._local_path is not None:
                self._client = QdrantClient(path=str(self._local_path))
            else:
                if not url:
                    raise ValueError("Qdrant server URL is required when path is not set")
                self._client = QdrantClient(url=url, api_key=api_key or None)
        except Exception as exc:
            if self._local_path is not None and _looks_like_local_lock(exc):
                raise VectorStoreOpenError(
                    f"Qdrant local path is already open: {self._local_path}; close the other client first"
                ) from exc
            raise

        # collection_exists works for both Local and Server and avoids guessing from HTTP 404.
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=r.VectorParams(size=dim, distance=r.Distance.COSINE),
            )
        else:
            stored_dim = _collection_vector_size(self._client.get_collection(self._collection))
            if stored_dim is not None and stored_dim != dim:
                self.close()
                raise ValueError(
                    f"Qdrant collection {collection!r} expects dimension {stored_dim}, "
                    f"but the configured embedder has dimension {dim}"
                )

    def _ensure_open(self) -> None:
        if self._closed:
            raise VectorStoreError("Qdrant store is already closed")

    def upsert(self, chunk: Chunk, vector: np.ndarray) -> None:
        from qdrant_client.http import models as r

        self._ensure_open()
        self._client.upsert(
            collection_name=self._collection,
            points=[r.PointStruct(
                id=_point_id(chunk.id),
                vector=vector.tolist(),
                payload=_chunk_to_payload(chunk),
            )],
        )

    def add_many(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        from qdrant_client.http import models as r

        self._ensure_open()
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return
        points = [
            r.PointStruct(
                id=_point_id(chunk.id),
                vector=vector.tolist(),
                payload=_chunk_to_payload(chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,
        )

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[Chunk, float]]:
        self._ensure_open()
        from qdrant_client.http import models as r

        # qdrant-client >=1.7 用 query_points 取代 search；返回 records 各含 .id/.payload/.score
        resp = self._client.query_points(
            collection_name=self._collection,
            query=query_vector.tolist(),
            limit=top_k,
            query_filter=r.Filter(
                must_not=[r.FieldCondition(key="meta.active", match=r.MatchValue(value=False))]
            ),
        )
        return [
            (_chunk_from_payload(point.payload, fallback_id=str(point.id)), point.score)
            for point in resp.points
            if _chunk_is_active(_chunk_from_payload(point.payload, fallback_id=str(point.id)))
        ]

    def list_chunks(self) -> list[Chunk]:
        self._ensure_open()
        points = self._scroll_points()
        return [
            _chunk_from_payload(point.payload, fallback_id=str(point.id))
            for point in points
            if _chunk_is_active(_chunk_from_payload(point.payload, fallback_id=str(point.id)))
        ]

    def count(self) -> int:
        self._ensure_open()
        from qdrant_client.http import models as r

        result = self._client.count(
            collection_name=self._collection,
            count_filter=r.Filter(
                must_not=[r.FieldCondition(key="meta.active", match=r.MatchValue(value=False))]
            ),
            exact=True,
        )
        return int(result.count)

    def exists(self, chunk_id: str) -> bool:
        self._ensure_open()
        return bool(self._client.retrieve(self._collection, ids=[_point_id(chunk_id)]))

    def delete_document(self, doc_id: str, version: int | None = None) -> int:
        from qdrant_client.http import models as r

        self._ensure_open()
        conditions = [r.FieldCondition(key="doc_id", match=r.MatchValue(value=doc_id))]
        if version is not None:
            conditions.append(
                r.FieldCondition(key="meta.document_version", match=r.MatchValue(value=version))
            )
        document_filter = r.Filter(must=cast(Any, conditions))
        points = self._scroll_points(document_filter)
        if not points:
            return 0
        self._client.delete(
            collection_name=self._collection,
            points_selector=r.PointIdsList(points=[point.id for point in points]),
            wait=True,
        )
        return len(points)

    def delete_chunks(self, chunk_ids: list[str]) -> int:
        self._ensure_open()
        if not chunk_ids:
            return 0
        point_ids = [_point_id(chunk_id) for chunk_id in dict.fromkeys(chunk_ids)]
        points = self._client.retrieve(self._collection, ids=point_ids)
        if not points:
            return 0
        from qdrant_client.http import models as r

        self._client.delete(
            collection_name=self._collection,
            points_selector=r.PointIdsList(points=[point.id for point in points]),
            wait=True,
        )
        return len(points)

    def set_document_active(self, doc_id: str, active: bool) -> int:
        from qdrant_client.http import models as r

        self._ensure_open()
        points = self._scroll_points(
            r.Filter(must=[r.FieldCondition(key="doc_id", match=r.MatchValue(value=doc_id))])
        )
        changed = 0
        for point in points:
            payload = dict(point.payload or {})
            meta = dict(payload.get("meta") or {})
            if meta.get("active", True) == active:
                continue
            meta["active"] = active
            self._client.set_payload(
                collection_name=self._collection,
                payload={"meta": meta},
                points=[point.id],
                wait=True,
            )
            changed += 1
        return changed

    def delete_document_except_version(self, doc_id: str, keep_version: int) -> int:
        from qdrant_client.http import models as r

        self._ensure_open()
        points = self._scroll_points(
            r.Filter(must=[r.FieldCondition(key="doc_id", match=r.MatchValue(value=doc_id))])
        )
        remove_ids = [
            point.id for point in points
            if (point.payload or {}).get("meta", {}).get("document_version") != keep_version
        ]
        if remove_ids:
            self._client.delete(
                collection_name=self._collection,
                points_selector=r.PointIdsList(points=remove_ids),
                wait=True,
            )
        return len(remove_ids)

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    def _scroll_points(self, scroll_filter=None) -> list:
        points = []
        offset = None
        while True:
            batch, offset = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=scroll_filter,
                limit=256,
                offset=offset,
                with_payload=True,
            )
            points.extend(batch)
            if offset is None:
                return points


def _looks_like_local_lock(exc: Exception) -> bool:
    message = str(exc).lower()
    return "already accessed" in message or "already open" in message or "lock" in message


def _chunk_is_active(chunk: Chunk) -> bool:
    return chunk.meta.get("active", True) is not False


def build_store(settings, dim: int, collection: str | None = None) -> VectorStore:
    collection_name = collection or settings.qdrant_collection
    if settings.vector_store in {"qdrant", "qdrant_server"}:
        return QdrantStore(
            settings.qdrant_url,
            collection_name,
            dim,
            settings.qdrant_api_key,
        )
    if settings.vector_store == "qdrant_local":
        return QdrantStore(
            collection=collection_name,
            dim=dim,
            path=settings.qdrant_path,
        )
    if settings.vector_store == "in_memory":
        return InMemoryStore()
    raise ValueError(f"unsupported vector store: {settings.vector_store}")
