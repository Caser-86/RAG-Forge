"""Build and verify a candidate Qdrant collection before switching the manifest."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import get_settings
from ragforge.embeddings import build_embedder
from ragforge.index_manifest import build_index_manifest, write_manifest
from ragforge.ingest import Chunker, load_documents
from ragforge.observability import setup_logging
from ragforge.vectorstore import build_store

setup_logging()


def _document_paths(root: Path) -> list[Path]:
    extensions = {".md", ".txt", ".pdf", ".html", ".htm"}
    if root.is_file():
        return [root] if root.suffix.lower() in extensions else []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions)


def _assert_collection_absent(settings, collection: str) -> None:
    """确认重建目标是空集合，避免把候选写入 active 或旧集合。"""
    from qdrant_client import QdrantClient

    if settings.vector_store in {"qdrant", "qdrant_server"}:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    else:
        client = QdrantClient(path=str(settings.qdrant_path))
    try:
        if client.collection_exists(collection):
            raise ValueError(
                f"candidate collection {collection!r} must be a new collection"
            )
    finally:
        client.close()


def reindex(doc_root: Path, collection: str | None = None) -> dict[str, object]:
    settings = get_settings()
    if settings.vector_store not in {"qdrant", "qdrant_local", "qdrant_server"}:
        raise ValueError("reindex requires vector_store=qdrant_local or qdrant_server")

    paths = _document_paths(doc_root)
    if not paths:
        raise ValueError(f"no supported documents found under {doc_root}")

    candidate = collection or (
        "rag_forge_rebuild_"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        + "_"
        + uuid4().hex[:8]
    )
    _assert_collection_absent(settings, candidate)
    embedder = build_embedder(settings)
    store = build_store(settings, embedder.dim, collection=candidate)
    try:
        documents = load_documents(paths)
        chunker = Chunker(settings.chunk_size, settings.chunk_overlap, settings.chunk_strategy)
        chunks = [chunk for document in documents for chunk in chunker.chunk(document)]
        if not chunks:
            raise ValueError("documents produced no non-empty chunks")

        batch_size = settings.embedder_batch_size
        first_vector: np.ndarray | None = None
        batches = 0
        for start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[start : start + batch_size]
            vectors = np.asarray(embedder.encode([chunk.text for chunk in batch_chunks]), dtype=np.float32)
            expected_shape = (len(batch_chunks), embedder.dim)
            if vectors.shape != expected_shape:
                raise ValueError(f"embedder returned shape {vectors.shape}, expected {expected_shape}")
            if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
                raise ValueError("embedder returned non-finite or zero vectors")

            store.add_many(batch_chunks, vectors)
            if first_vector is None:
                first_vector = vectors[0]
            batches += 1
        if store.count() != len(chunks):
            raise ValueError(f"candidate count {store.count()} != chunk count {len(chunks)}")
        if first_vector is None or not any(hit.id == chunks[0].id for hit, _ in store.search(first_vector, 1)):
            raise ValueError("candidate query verification failed")

        backend = "qdrant_server" if settings.vector_store == "qdrant" else settings.vector_store
        write_manifest(
            settings.index_manifest_path,
            build_index_manifest(
                settings,
                dimension=embedder.dim,
                backend=backend,
                active_collection=candidate,
                embedding_digest=(
                    getattr(embedder, "identity_digest", "")
                    or settings.embedder_digest
                ),
            ),
        )
        return {
            "candidate_collection": candidate,
            "indexed_chunks": len(chunks),
            "batches": batches,
            "batch_size": batch_size,
            "verified": True,
        }
    finally:
        store.close()
        close = getattr(embedder, "close", None)
        if close:
            close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild a candidate Qdrant collection safely")
    parser.add_argument("docs", nargs="?", default="data/raw/docs", help="document directory or file")
    parser.add_argument("--collection", help="candidate collection name")
    args = parser.parse_args()
    print(json.dumps(reindex(Path(args.docs), args.collection), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
