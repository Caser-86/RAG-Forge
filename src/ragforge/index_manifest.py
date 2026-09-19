"""Index identity manifest and atomic compatibility checks."""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from .config import Settings
from .ingest.chunker import CHUNK_ALGORITHM_VERSION
from .retriever.sparse import TOKENIZER_VERSION


class IndexManifestError(ValueError):
    """The index manifest is missing, corrupt, or structurally invalid."""


class LegacyIndexError(IndexManifestError):
    """An existing index has no identity manifest and cannot be guessed safely."""


class IndexIdentityMismatch(IndexManifestError):
    """The configured index identity differs from the stored identity."""


_REQUIRED_FIELDS = {
    "schema_version",
    "backend",
    "embedder_backend",
    "embedding_model",
    "embedding_digest",
    "dimension",
    "normalization",
    "chunk_strategy",
    "chunk_algorithm_version",
    "tokenizer_version",
    "chunk_size",
    "chunk_overlap",
    "active_collection",
}
INDEX_MANIFEST_SCHEMA_VERSION = 2
_IDENTITY_FIELDS = _REQUIRED_FIELDS - {"active_collection"}
_REPLACE_RETRIES = 4


def build_index_manifest(
    settings: Settings,
    *,
    dimension: int | None = None,
    backend: str | None = None,
    active_collection: str | None = None,
    embedding_digest: str | None = None,
) -> dict[str, Any]:
    """Build the stable identity used to decide whether an index is reusable."""
    resolved_backend = backend or {
        "qdrant": "qdrant_server",
        "qdrant_local": "qdrant_local",
        "qdrant_server": "qdrant_server",
        "in_memory": "in_memory",
    }.get(settings.vector_store, settings.vector_store)
    return {
        "schema_version": INDEX_MANIFEST_SCHEMA_VERSION,
        "backend": resolved_backend,
        "embedder_backend": settings.embedder_backend,
        "embedding_model": settings.embedder_model,
        "embedding_digest": (
            embedding_digest if embedding_digest is not None else settings.embedder_digest
        ),
        "dimension": dimension or settings.embedder_dim,
        "normalization": "l2",
        "chunk_strategy": getattr(settings, "chunk_strategy", "char"),
        "chunk_algorithm_version": CHUNK_ALGORITHM_VERSION,
        "tokenizer_version": TOKENIZER_VERSION,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "active_collection": active_collection or getattr(settings, "qdrant_collection", ""),
    }


def load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexManifestError(f"invalid index manifest: {path}") from exc
    if not isinstance(payload, dict) or not _REQUIRED_FIELDS.issubset(payload):
        raise IndexManifestError(f"invalid index manifest fields: {path}")
    if payload["schema_version"] != INDEX_MANIFEST_SCHEMA_VERSION:
        raise IndexManifestError(
            f"unsupported index manifest schema {payload['schema_version']!r}: {path}"
        )
    return payload


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    missing = _REQUIRED_FIELDS - manifest.keys()
    if missing:
        raise IndexManifestError(f"manifest missing fields: {sorted(missing)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = handle.name
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(_REPLACE_RETRIES):
            try:
                os.replace(temporary_path, path)
                break
            except PermissionError:
                if attempt == _REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05 * (2**attempt))
        temporary_path = None
    finally:
        if temporary_path:
            with suppress(FileNotFoundError):
                os.unlink(temporary_path)


def ensure_compatible(
    actual: dict[str, Any] | None,
    expected: dict[str, Any],
) -> None:
    if actual is None:
        raise LegacyIndexError("index has no manifest; reindex is required before reuse")
    differences = {
        field: (actual.get(field), expected.get(field))
        for field in _IDENTITY_FIELDS
        if actual.get(field) != expected.get(field)
    }
    if differences:
        details = ", ".join(
            f"{field}={old!r}->{new!r}" for field, (old, new) in differences.items()
        )
        raise IndexIdentityMismatch(f"index identity mismatch; reindex is required ({details})")
