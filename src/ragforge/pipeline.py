"""编排层：文档 → 索引 → 检索 → 生成，串联整条链路并产出 trace。"""
from __future__ import annotations

import time
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from threading import RLock

import numpy as np

from .config import Settings, get_settings
from .embeddings import build_embedder
from .generator import build_generator
from .grounding import score_calibration_status
from .index_manifest import (
    LegacyIndexError,
    build_index_manifest,
    ensure_compatible,
    load_manifest,
    write_manifest,
)
from .ingest import Chunker, load_documents
from .models import Answer, Chunk, Document, Evidence
from .observability import get_logger, new_trace_id, timer
from .query_rewriter import QueryRewriter
from .retriever import Retriever
from .retriever.rerank import Reranker
from .retriever.sparse import BM25Index
from .trace_store import TraceStore
from .vectorstore import build_store

logger = get_logger()


class RAGForge:
    def __init__(self, settings: Settings | None = None):
        self._closed = False
        with ExitStack() as stack:
            self.settings = settings or get_settings()
            self.embedder = build_embedder(self.settings)
            stack.callback(self._close_resource, self.embedder)
            self._active_collection = self._manifest_collection()
            self.store = build_store(
                self.settings,
                self.embedder.dim,
                collection=self._active_collection,
            )
            stack.callback(self._close_resource, self.store)
            self._validate_persistent_identity()
            self.bm25 = BM25Index([])
            self.chunker = Chunker(
                self.settings.chunk_size,
                self.settings.chunk_overlap,
                self.settings.chunk_strategy,
            )
            self.retriever: Retriever | None = None
            self.generator = build_generator(self.settings)
            stack.callback(self._close_resource, self.generator)
            self.query_rewriter = QueryRewriter(self.settings)
            stack.callback(self._close_resource, self.query_rewriter)
            self._all_chunks: list[Chunk] = []
            self._lock = RLock()
            self._rewrite_lock = RLock()
            self._generation_lock = RLock()
            self.trace_store = TraceStore(
                max_entries=self.settings.trace_max_entries,
                ttl_seconds=self.settings.trace_ttl_seconds,
                max_item_chars=self.settings.trace_max_item_chars,
            )
            stack.pop_all()

    # ---- 摄取 ----
    def ingest_files(self, paths: Sequence[str | Path]) -> int:
        docs = load_documents([Path(p) for p in paths])
        chunks: list[Chunk] = []
        for doc in docs:
            chunks.extend(self.chunker.chunk(doc))
        return self.ingest_chunks(chunks)

    def ingest_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        with self._lock:
            self._ensure_open()
            vectors = self.embedder.encode([c.text for c in chunks])
            vectors = np.asarray(vectors, dtype=np.float32)
            expected_shape = (len(chunks), self.embedder.dim)
            if vectors.shape != expected_shape:
                raise ValueError(
                    f"embedder returned shape {vectors.shape}, expected {expected_shape}"
                )
            if not np.isfinite(vectors).all():
                raise ValueError("embedder returned non-finite vectors")
            if np.any(np.linalg.norm(vectors, axis=1) == 0):
                raise ValueError("embedder returned zero vectors")
            self.store.add_many(chunks, vectors)

            if not self._all_chunks and len(self.store):
                self._all_chunks = self.store.list_chunks()
            known = {c.id: c for c in self._all_chunks}
            known.update({c.id: c for c in chunks})
            self._all_chunks = list(known.values())
            self.bm25 = BM25Index(self._all_chunks)
            self.retriever = Retriever(self.store, self.embedder, self.bm25, self.settings)
            self.retriever.index_scope()
            self._save_persistent_identity()
            return len(chunks)

    def ingest_document(self, document: Document) -> int:
        """以版本化 chunk 写入文档，确认新版本后才清理旧版本。"""
        raw_chunks = self.chunker.chunk(document)
        chunks = [
            chunk.model_copy(update={
                "meta": {**chunk.meta, "document_version": document.version, "active": True},
            })
            for chunk in raw_chunks
        ]
        if not chunks:
            return 0
        existing = {
            chunk.id: chunk
            for chunk in self.store.list_chunks()
            if chunk.doc_id == document.id
        }
        candidate_ids = {chunk.id for chunk in chunks}
        overlapping_ids = candidate_ids & existing.keys()
        if overlapping_ids:
            if len(overlapping_ids) == len(candidate_ids) and all(
                existing[chunk.id].model_dump() == chunk.model_dump()
                for chunk in chunks
            ):
                self._refresh_retriever()
                return len(chunks)
            raise ValueError(
                "document version already has partial or different chunks; "
                "use a new document version"
            )

        cleanup_started = False
        try:
            count = self.ingest_chunks(chunks)
            if not all(self.store.exists(chunk.id) for chunk in chunks):
                raise ValueError("new document version failed index verification")
            # From this point onward the candidate is valid. If old-version cleanup
            # fails, retain the candidate instead of deleting the only good version.
            cleanup_started = True
            self.store.delete_document_except_version(document.id, document.version)
            self._refresh_retriever()
            return count
        except Exception:
            # Before the commit point only remove chunks written by this attempt.
            # Never delete an existing same-version chunk as a rollback shortcut.
            if not cleanup_started:
                new_ids = list(candidate_ids - set(existing))
                try:
                    self.store.delete_chunks(new_ids)
                except Exception as cleanup_error:  # pragma: no cover - defensive path
                    logger.warning(
                        "候选版本清理失败，保留可恢复数据：%s",
                        type(cleanup_error).__name__,
                    )
            try:
                self._refresh_retriever()
            except Exception as refresh_error:  # pragma: no cover - defensive path
                logger.warning(
                    "失败后重建检索器失败：%s",
                    type(refresh_error).__name__,
                )
            raise

    def _refresh_retriever(self) -> None:
        self._all_chunks = self.store.list_chunks()
        self.bm25 = BM25Index(self._all_chunks)
        self.retriever = Retriever(self.store, self.embedder, self.bm25, self.settings)
        self.retriever.index_scope()

    def delete_document(self, doc_id: str) -> int:
        with self._lock:
            self._ensure_open()
            removed = self.store.delete_document(doc_id)
            if not removed:
                return 0
            self._all_chunks = self.store.list_chunks()
            self.bm25 = BM25Index(self._all_chunks)
            self.retriever = Retriever(self.store, self.embedder, self.bm25, self.settings)
            self.retriever.index_scope()
            return removed

    def set_document_active(self, doc_id: str, active: bool) -> int:
        with self._lock:
            self._ensure_open()
            changed = self.store.set_document_active(doc_id, active)
            if changed:
                self._all_chunks = self.store.list_chunks()
                self.bm25 = BM25Index(self._all_chunks)
                self.retriever = Retriever(self.store, self.embedder, self.bm25, self.settings)
                self.retriever.index_scope()
            return changed

    # ---- 检索器懒初始化 ----
    def _ensure_retriever(self) -> None:
        """确保 self.retriever 可用；Qdrant 持久化场景下， ingest 可能未调用过。"""
        with self._lock:
            self._ensure_open()
            if self.retriever is not None:
                return
            if not self.bm25.chunks:
                self._all_chunks = self.store.list_chunks()
                self.bm25 = BM25Index(self._all_chunks)
            bm25 = self.bm25
            self.retriever = Retriever(self.store, self.embedder, bm25, self.settings)
            self.retriever.index_scope()

    def reranker_status(self) -> dict[str, object]:
        if self.retriever is not None:
            return self.retriever.reranker_status()
        return Reranker(self.settings.rerank_model, self.settings.use_rerank).status()

    # ---- 问答 ----
    def ask(
        self,
        query: str,
        model: str | None = None,
        retrieval_mode: str | None = None,
        top_k: int | None = None,
        history: list[dict[str, str]] | None = None,
        rewrite: bool | None = None,
    ) -> Answer:
        self._ensure_retriever()
        retriever = self.retriever
        if retriever is None:  # pragma: no cover - guarded by _ensure_retriever
            raise RuntimeError("retriever not ready")
        trace_id = new_trace_id()
        total_start = time.monotonic()
        requested_mode = retrieval_mode or self.settings.retrieval_mode
        rewrite_requested = self.settings.rewrite_enabled if rewrite is None else rewrite
        trace: dict[str, object] = {
            "trace_id": trace_id,
            "original_query": query,
            "rewritten_query": query,
            "rewrite": bool(rewrite_requested),
            "rewrite_status": "disabled",
            "rewrite_reason": "disabled",
            "rewrite_timing_ms": 0.0,
            "model": None,
            "requested_model": model or self.settings.default_generation_model,
            "retrieval_mode": requested_mode,
            "effective_mode": None,
            "candidates": [],
            "final_context": "",
            "timings": {
                "embedding": None,
                "dense": None,
                "sparse": None,
                "fusion": None,
                "rerank": None,
                "generation": None,
                "total": None,
            },
            "refused": False,
            "refusal_reason": None,
            "citations": [],
            "citation_invalid": False,
            "confidence_mode": "uncalibrated",
            "index_identity": self._expected_manifest(),
        }
        evidences: list[Evidence] = []
        stage = "prepare"
        try:
            rewritten_query = query
            if rewrite_requested:
                stage = "rewrite"
                with self._rewrite_lock:
                    rewritten_query = self.query_rewriter.rewrite(
                        query,
                        history or [],
                        enabled=True,
                    )
                rewrite_result = self.query_rewriter.last_result
                trace["rewrite_status"] = "fallback" if rewrite_result.fallback else "applied"
                trace["rewrite_reason"] = rewrite_result.reason
                trace["rewrite_timing_ms"] = rewrite_result.elapsed_ms
            trace["rewritten_query"] = rewritten_query
            stage = "retrieve"
            with self._lock, timer("retrieve", logger):
                evidences = retriever.retrieve(
                    rewritten_query,
                    mode=retrieval_mode,
                    top_k=top_k,
                )
            trace["effective_mode"] = getattr(
                retriever, "last_effective_mode", requested_mode
            )
            timings = trace["timings"]
            if isinstance(timings, dict):
                timings.update(getattr(retriever, "last_timings", {}))
            trace["candidates"] = [self._trace_evidence(evidence) for evidence in evidences]
            generation_start = time.monotonic()
            stage = "generate"
            with self._generation_lock, timer("generate", logger):
                answer = self.generator.generate(query, evidences, trace_id, model=model)
            generation_ms = (time.monotonic() - generation_start) * 1000
            if isinstance(timings, dict):
                timings["generation"] = generation_ms
                timings["total"] = (time.monotonic() - total_start) * 1000
            bundle = getattr(self.generator, "last_context_bundle", None)
            trace["final_context"] = getattr(bundle, "context", "")
            trace["raw_output"] = getattr(self.generator, "last_raw_output", None)
            trace["answer"] = answer.answer
            trace["model"] = answer.model
            trace["refused"] = answer.refused
            trace["refusal_reason"] = answer.refusal_reason
            trace["citations"] = [citation.model_dump() for citation in answer.citation_details]
            trace["citation_invalid"] = answer.citation_invalid
            self.trace_store.put(trace_id, trace)
            best_scores = [
                score for evidence in evidences
                for score in (evidence.rerank_score, evidence.fused_score, evidence.dense_score)
                if score is not None
            ]
            logger.info("[trace %s] hits=%d best=%.4f refused=%s",
                        trace_id, len(evidences), max(best_scores, default=0.0), answer.refused)
            return answer
        except Exception as exc:
            timings = trace["timings"]
            if isinstance(timings, dict):
                timings["total"] = (time.monotonic() - total_start) * 1000
            trace["error"] = {"type": type(exc).__name__}
            self.trace_store.put(trace_id, trace)
            logger.error(
                "[trace %s] stage=%s error_type=%s",
                trace_id,
                stage,
                type(exc).__name__,
            )
            raise

    @staticmethod
    def _trace_evidence(evidence: Evidence) -> dict[str, object]:
        return {
            "document_id": evidence.chunk.doc_id,
            "chunk_id": evidence.chunk.id,
            "title": evidence.chunk.title,
            "source": evidence.chunk.source,
            "dense_score": evidence.dense_score,
            "sparse_score": evidence.sparse_score,
            "fused_score": evidence.fused_score,
            "rerank_score": evidence.rerank_score,
            "score_kind": evidence.score_kind,
            "calibration": score_calibration_status(evidence),
        }

    def get_trace(self, trace_id: str) -> dict[str, object] | None:
        return self.trace_store.get(trace_id)

    def retrieve_only(
        self,
        query: str,
        retrieval_mode: str | None = None,
        top_k: int | None = None,
    ) -> list[Evidence]:
        self._ensure_retriever()
        retriever = self.retriever
        if retriever is None:  # pragma: no cover - guarded by _ensure_retriever
            raise RuntimeError("retriever not ready")
        with self._lock, timer("retrieve", logger):
            return retriever.retrieve(query, mode=retrieval_mode, top_k=top_k)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            resources = (self.generator, self.query_rewriter, self.embedder, self.store)
            first_error: Exception | None = None
            for resource in resources:
                close = getattr(resource, "close", None)
                if not close:
                    continue
                try:
                    close()
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "[lifecycle] cleanup_failed resource=%s error_type=%s",
                        type(resource).__name__,
                        type(exc).__name__,
                    )
                    first_error = first_error or exc
            if first_error:
                raise first_error

    @staticmethod
    def _close_resource(resource: object) -> None:
        close = getattr(resource, "close", None)
        if not close:
            return
        try:
            close()
        except Exception as exc:  # preserve the construction failure
            logger.warning(
                "[lifecycle] initialization_cleanup_failed resource=%s error_type=%s",
                type(resource).__name__,
                type(exc).__name__,
            )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("RAGForge engine is already closed")

    def _uses_persistent_store(self) -> bool:
        return self.settings.vector_store in {"qdrant", "qdrant_local", "qdrant_server"}

    def _expected_manifest(self) -> dict:
        backend = {
            "qdrant": "qdrant_server",
            "qdrant_local": "qdrant_local",
            "qdrant_server": "qdrant_server",
        }.get(self.settings.vector_store, "in_memory")
        return build_index_manifest(
            self.settings,
            dimension=self.embedder.dim,
            backend=backend,
            active_collection=self._active_collection,
            embedding_digest=self._embedder_digest(),
        )

    def _embedder_digest(self) -> str:
        return (
            getattr(self.embedder, "identity_digest", "")
            or self.settings.embedder_digest
        )

    def _manifest_collection(self) -> str:
        if not self._uses_persistent_store():
            return self.settings.qdrant_collection
        manifest = load_manifest(self.settings.index_manifest_path)
        if manifest is None:
            return self.settings.qdrant_collection
        expected = build_index_manifest(
            self.settings,
            dimension=self.embedder.dim,
            backend={
                "qdrant": "qdrant_server",
                "qdrant_local": "qdrant_local",
                "qdrant_server": "qdrant_server",
            }.get(self.settings.vector_store, self.settings.vector_store),
            active_collection=manifest.get("active_collection", self.settings.qdrant_collection),
        )
        ensure_compatible(manifest, expected)
        active_collection = manifest.get("active_collection")
        if not isinstance(active_collection, str) or not active_collection.strip():
            raise ValueError("index manifest active_collection is invalid")
        return active_collection

    def _validate_persistent_identity(self) -> None:
        if not self._uses_persistent_store():
            return
        manifest = load_manifest(self.settings.index_manifest_path)
        if self.store.count() and manifest is None:
            self.store.close()
            close = getattr(self.embedder, "close", None)
            if close:
                close()
            raise LegacyIndexError(
                "existing persistent index has no manifest; reindex is required before reuse"
            )
        if manifest is not None:
            try:
                ensure_compatible(manifest, self._expected_manifest())
            except ValueError:
                self.store.close()
                close = getattr(self.embedder, "close", None)
                if close:
                    close()
                raise

    def _save_persistent_identity(self) -> None:
        if self._uses_persistent_store():
            write_manifest(self.settings.index_manifest_path, self._expected_manifest())
