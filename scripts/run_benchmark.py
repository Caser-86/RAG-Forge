"""运行隔离的检索、生成或 chunk 实验，并保存逐题 JSON 证据。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings
from ragforge.evaluation.benchmark import (
    BenchmarkCase,
    aggregate_retrieval,
    assess_quality_eligibility,
    benchmark_dataset_content_sha256,
    corpus_identity,
    evidence_fingerprint,
    latency_summary,
    load_cases,
    select_cases,
    stable_document_id,
)
from ragforge.evaluation.metrics import (
    citation_validity,
    refusal_confusion,
)
from ragforge.grounding import extract_citation_indices
from ragforge.ingest import load_documents
from ragforge.ingest.chunker import CHUNK_ALGORITHM_VERSION
from ragforge.models import Chunk, Evidence
from ragforge.ollama_client import OllamaClient
from ragforge.pipeline import RAGForge


def _read_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("experiments.yaml must be JSON-compatible unless PyYAML is installed") from exc
        value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError("experiment config must be an object")
    return value


def _rooted(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _runtime() -> dict[str, Any]:
    try:
        import psutil  # type: ignore
        memory_total = psutil.virtual_memory().total
    except (ImportError, AttributeError, OSError):
        memory_total = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "memory_total_bytes": memory_total,
        "gpu": "not queried; no GPU-specific dependency in benchmark runner",
    }


def _files(root: Path) -> list[Path]:
    return [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    ]


def _load_corpus(root: Path) -> tuple[list[tuple[Path, Any]], set[str], dict[str, Any]]:
    files = _files(root)
    if not files:
        raise ValueError(f"no markdown/text corpus files found under {root}")
    docs: list[tuple[Path, Any]] = []
    for path in files:
        loaded = load_documents([path])
        if not loaded:
            continue
        doc = loaded[0].model_copy(update={"id": stable_document_id(path), "title": path.stem})
        docs.append((path, doc))
    identity = corpus_identity(root)
    identity["root"] = root.relative_to(ROOT).as_posix() if root.is_relative_to(ROOT) else str(root)
    return docs, set(identity["document_ids"]), identity


def _settings(
    config: dict[str, Any],
    *,
    experiment: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    storage: dict[str, str] | None = None,
) -> Settings:
    index = dict(config.get("index") or {})
    retrieval = dict(config.get("retrieval") or {})
    generation = dict(config.get("generation") or {})
    allowed_models = list(generation.get("models") or ["gemma3:4b", "gemma4:e4b"])
    default_model = allowed_models[0]
    storage = storage or {}
    values: dict[str, Any] = {
        "_env_file": None,
        "vector_store": index.get("backend", "in_memory"),
        "qdrant_path": storage.get("qdrant_path", index.get("qdrant_path", "data/benchmark-qdrant")),
        "qdrant_collection": storage.get(
            "qdrant_collection", index.get("qdrant_collection", "rag_forge_benchmark")
        ),
        "index_manifest_path": storage.get(
            "index_manifest_path",
            index.get("index_manifest_path", "data/benchmark-index-manifest.json"),
        ),
        "embedder_backend": index.get("embedder_backend", "deterministic"),
        "embedder_model": index.get("embedder_model", "deterministic"),
        "embedder_dim": index.get("embedder_dim", 64),
        "embedder_digest": index.get("embedder_digest", ""),
        "chunk_strategy": index.get("chunk_strategy", "heading_chars"),
        "chunk_size": chunk_size if chunk_size is not None else index.get("chunk_size", 2200),
        "chunk_overlap": (
            chunk_overlap if chunk_overlap is not None else index.get("chunk_overlap", 200)
        ),
        "retrieval_mode": retrieval.get("modes", ["hybrid"])[0],
        "top_k": generation.get("top_k", retrieval.get("top_k", 5)),
        "dense_top_k": retrieval.get("dense_top_k", 20),
        "sparse_top_k": retrieval.get("sparse_top_k", 20),
        "rerank_candidate_k": retrieval.get("rerank_candidate_k", 40),
        "rerank_top_k": retrieval.get("rerank_top_k", 5),
        "rerank_model": retrieval.get("rerank_model", "BAAI/bge-reranker-base"),
        "use_rerank": bool(retrieval.get("use_rerank", False)),
        "generation_backend": generation.get("backend", "offline"),
        "default_generation_model": default_model,
        "allowed_generation_models": allowed_models,
        "llm_model": default_model,
        "ollama_generate_timeout": generation.get("timeout_seconds", 180),
        "generation_temperature": generation.get("temperature"),
        "generation_num_predict": generation.get("num_predict"),
        "generation_seed": generation.get("seed"),
        "rewrite_enabled": False,
    }
    if experiment == "generation":
        values["retrieval_mode"] = generation.get("retrieval_mode", "hybrid")
    return Settings(**values)


def _chunks(engine: RAGForge, docs: list[tuple[Path, Any]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for _path, doc in docs:
        chunks.extend(engine.chunker.chunk(doc))
    return chunks


def _chunking_variants(config: dict[str, Any]) -> list[dict[str, int]]:
    """Return validated chunking variants without silently changing overlap."""
    index = dict(config.get("index") or {})
    configured = (config.get("chunking") or {}).get("variants")
    if configured is None:
        configured = [
            {"chunk_size": size, "chunk_overlap": int(index.get("chunk_overlap", 200))}
            for size in (1200, 1800, int(index.get("chunk_size", 2200)), 3000)
        ]
    if not isinstance(configured, list) or not configured:
        raise ValueError("chunking.variants must be a non-empty list")
    variants: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in configured:
        if not isinstance(item, dict):
            raise ValueError("chunking variant must be an object")
        size = item.get("chunk_size")
        overlap = item.get("chunk_overlap")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or size <= 0
            or isinstance(overlap, bool)
            or not isinstance(overlap, int)
            or overlap < 0
            or overlap >= size
        ):
            raise ValueError("chunking variant requires chunk_size > chunk_overlap >= 0")
        key = (size, overlap)
        if key in seen:
            raise ValueError(f"duplicate chunking variant: {size}/{overlap}")
        seen.add(key)
        variants.append({"chunk_size": size, "chunk_overlap": overlap})
    return variants


def _chunking_storage(
    config: dict[str, Any], variant: dict[str, int], corpus: dict[str, Any]
) -> dict[str, str]:
    """Derive isolated persistent identities for one chunking experiment."""
    index = dict(config.get("index") or {})
    size = variant["chunk_size"]
    overlap = variant["chunk_overlap"]
    corpus_token = str(corpus.get("sha256", "unknown"))[:12]
    slug = f"chunk-{size}-{overlap}-{corpus_token}"

    def suffixed(value: str, *, extension: str | None = None) -> str:
        path = Path(value)
        if extension is None:
            return str(path.with_name(f"{path.name}-{slug}"))
        return str(path.with_name(f"{path.stem}-{slug}{extension}"))

    base_path = str(index.get("qdrant_path", "data/benchmark-qdrant"))
    base_collection = str(index.get("qdrant_collection", "rag_forge_benchmark"))
    base_manifest = Path(str(index.get("index_manifest_path", "data/benchmark-index-manifest.json")))
    return {
        "qdrant_path": suffixed(base_path),
        "qdrant_collection": f"{base_collection}_{slug}",
        "index_manifest_path": suffixed(str(base_manifest), extension=base_manifest.suffix or ".json"),
    }


def _evidence_json(evidence: Evidence) -> dict[str, Any]:
    return {
        "document_id": evidence.chunk.doc_id,
        "chunk_id": evidence.chunk.id,
        "title": evidence.chunk.title,
        "source": evidence.chunk.source,
        "text_sha256": hashlib.sha256(evidence.chunk.text.encode("utf-8")).hexdigest(),
        "text_preview": evidence.chunk.text[:500],
        "dense_score": evidence.dense_score,
        "sparse_score": evidence.sparse_score,
        "fused_score": evidence.fused_score,
        "rerank_score": evidence.rerank_score,
        "score_kind": evidence.score_kind,
    }


def _identity(_config: dict[str, Any], settings: Settings, corpus: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": settings.vector_store,
        "embedder_backend": settings.embedder_backend,
        "embedder_model": settings.embedder_model,
        "embedder_dim": settings.embedder_dim,
        "chunk_strategy": settings.chunk_strategy,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "chunk_algorithm_version": CHUNK_ALGORITHM_VERSION,
        "embedding_digest": settings.embedder_digest,
        "retrieval_mode": settings.retrieval_mode,
        "use_rerank": settings.use_rerank,
        "dense_top_k": settings.dense_top_k,
        "sparse_top_k": settings.sparse_top_k,
        "rerank_candidate_k": settings.rerank_candidate_k,
        "rerank_top_k": settings.rerank_top_k,
        "rerank_model": settings.rerank_model,
        "top_k": settings.top_k,
        "qdrant_path": str(settings.qdrant_path),
        "qdrant_collection": settings.qdrant_collection,
        "index_manifest_path": str(settings.index_manifest_path),
        "corpus_sha256": corpus["sha256"],
    }


def model_identity(
    settings: Settings,
    models: list[str],
    *,
    generation_model_digests: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Return the model and generation-contract identity stored in reports/checkpoints."""
    generation = {
        "temperature": settings.generation_temperature,
        "num_predict": settings.generation_num_predict,
        "seed": settings.generation_seed,
        "timeout_seconds": settings.ollama_generate_timeout,
    }
    return {
        "embedder_backend": settings.embedder_backend,
        "embedder_model": settings.embedder_model,
        "embedder_digest": settings.embedder_digest,
        "generation_backend": settings.generation_backend,
        "generation_models": list(models),
        "generation_model_digests": generation_model_digests or {},
        "generation_parameters": generation,
        "retrieval_mode": settings.retrieval_mode,
        "use_rerank": settings.use_rerank,
    }


def checkpoint_identity(
    *,
    experiment: str,
    dataset: Path,
    case_ids: list[str],
    corpus: dict[str, Any],
    settings: Settings,
    model_identity: dict[str, Any],
    split_hash: str | None = None,
) -> dict[str, Any]:
    """Identify every input that can change a generation benchmark result."""
    return {
        "schema_version": 1,
        "experiment": experiment,
        "dataset": str(dataset.resolve()),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "case_ids": list(case_ids),
        "split_sha256": split_hash,
        "corpus_identity": corpus,
        "index_identity": _identity({}, settings, corpus),
        "model_identity": model_identity,
    }


def load_checkpoint(path: Path, expected_identity: dict[str, Any]) -> dict[str, Any]:
    """Load a checkpoint only when its dataset/model/index identity is exact."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid benchmark checkpoint: {path}") from exc
    if not isinstance(payload, dict) or payload.get("identity") != expected_identity:
        raise ValueError("checkpoint identity mismatch; use a new checkpoint path")
    if not isinstance(payload.get("models"), dict):
        raise ValueError("benchmark checkpoint models must be an object")
    if not isinstance(payload.get("evidence_cache"), dict):
        raise ValueError("benchmark checkpoint evidence_cache must be an object")
    return payload


def load_frozen_split(
    path: Path,
    cases: list[BenchmarkCase],
    *,
    partition: str = "test",
) -> tuple[set[str], dict[str, Any]]:
    """Validate a review-produced split before selecting calibration or test cases."""
    if partition not in {"calibration", "test"}:
        raise ValueError("split partition must be calibration or test")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid frozen split: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("frozen split must be an object")
    if payload.get("schema_version") != 2:
        raise ValueError("unsupported frozen split schema; regenerate the split")
    stored_hash = payload.get("split_sha256")
    body = {key: value for key, value in payload.items() if key != "split_sha256"}
    actual_hash = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if not isinstance(stored_hash, str) or stored_hash != actual_hash:
        raise ValueError("frozen split hash does not match content")
    stored_dataset_hash = payload.get("dataset_content_sha256")
    case_content = [
        {"id": case.id, "content_sha256": case.content_sha256}
        for case in cases
    ]
    expected_dataset_hash = benchmark_dataset_content_sha256(case_content)
    if stored_dataset_hash != expected_dataset_hash:
        raise ValueError("frozen split dataset content hash does not match the reviewed dataset")
    calibration = payload.get("calibration_ids")
    test = payload.get("test_ids")
    if not isinstance(calibration, list) or not isinstance(test, list):
        raise ValueError("frozen split must contain calibration_ids and test_ids")
    calibration_ids = [str(item) for item in calibration]
    test_ids = [str(item) for item in test]
    all_ids = {case.id for case in cases}
    if len(set(calibration_ids)) != len(calibration_ids) or len(set(test_ids)) != len(test_ids):
        raise ValueError("frozen split contains duplicate case ids")
    if set(calibration_ids) & set(test_ids):
        raise ValueError("frozen split calibration and test partitions overlap")
    if set(calibration_ids) | set(test_ids) != all_ids:
        raise ValueError("frozen split ids do not match the reviewed dataset")
    return (set(calibration_ids) if partition == "calibration" else set(test_ids)), payload


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _checkpoint_rows(
    checkpoint: dict[str, Any], model: str, case_ids: set[str]
) -> dict[str, dict[str, Any]]:
    entry = checkpoint["models"].get(model, {})
    if not isinstance(entry, dict):
        raise ValueError(f"benchmark checkpoint model entry is invalid: {model}")
    rows = entry.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError(f"benchmark checkpoint rows are invalid: {model}")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise ValueError(f"benchmark checkpoint row is invalid: {model}")
        case_id = row["case_id"]
        if case_id not in case_ids or case_id in by_id:
            raise ValueError(f"benchmark checkpoint contains unexpected or duplicate case: {case_id}")
        by_id[case_id] = row
    return by_id


def _resolve_provider_identity(settings: Settings, models: list[str]) -> dict[str, str | None]:
    """Resolve mutable Ollama tags once so reports never imply a guessed revision."""
    if settings.embedder_backend != "ollama" and settings.generation_backend != "ollama":
        return {}
    client = OllamaClient(
        settings.ollama_base_url,
        connect_timeout=settings.ollama_connect_timeout,
        generate_timeout=settings.ollama_generate_timeout,
    )
    generation_digests: dict[str, str | None] = {}
    try:
        if settings.embedder_backend == "ollama" and not settings.embedder_digest:
            settings.embedder_digest = client.model_digest(settings.embedder_model)
        if settings.generation_backend == "ollama":
            for model in models:
                try:
                    generation_digests[model] = client.model_digest(model)
                except Exception as exc:  # provider status remains explicit in the report
                    generation_digests[model] = None
                    logger_warning = f"{type(exc).__name__}"
                    print(
                        json.dumps(
                            {"warning": "generation_model_digest_unavailable", "model": model, "error_type": logger_warning},
                            ensure_ascii=False,
                        ),
                        file=sys.stderr,
                    )
    finally:
        client.close()
    return generation_digests


def _base_output(
    *, experiment: str, dataset: Path, cases: list[BenchmarkCase], corpus: dict[str, Any],
    settings: Settings, provisional: bool, quality_eligibility: dict[str, Any],
    runtime_model_identity: dict[str, Any],
    frozen_split: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "experiment": experiment,
        "dataset": str(dataset.relative_to(ROOT) if dataset.is_relative_to(ROOT) else dataset),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "dataset_review_status": sorted({case.review_status for case in cases}),
        "provisional": provisional,
        "case_count": len(cases),
        "runtime": _runtime(),
        "repetitions": 1,
        "model_identity": runtime_model_identity,
        "corpus_identity": corpus,
        "index_identity": _identity({}, settings, corpus),
        "quality_eligibility": quality_eligibility,
        "frozen_split": frozen_split,
        "results": {},
    }


def _run_retrieval(
    config: dict[str, Any], cases: list[BenchmarkCase], docs: list[tuple[Path, Any]],
    _corpus: dict[str, Any], ks: tuple[int, ...], modes: list[str],
) -> dict[str, Any]:
    retrieval_config = dict(config.get("retrieval") or {})
    output: dict[str, Any] = {"modes": {}, "requested_ks": list(ks)}
    requested_top_k = max(ks)
    for mode in modes:
        settings = _settings(config, experiment="retrieval")
        settings.retrieval_mode = mode
        engine = RAGForge(settings)
        rows: list[dict[str, Any]] = []
        ingest_start = time.perf_counter()
        try:
            chunks = _chunks(engine, docs)
            engine.ingest_chunks(chunks)
            ingest_ms = (time.perf_counter() - ingest_start) * 1000
            for case in cases:
                started = time.perf_counter()
                evidences: list[Evidence] = []
                status = "ok"
                error: dict[str, str] | None = None
                try:
                    evidences = engine.retrieve_only(case.question, retrieval_mode=mode, top_k=requested_top_k)
                except Exception as exc:
                    status = "error"
                    error = {"type": type(exc).__name__, "message": str(exc)[:500]}
                elapsed_ms = (time.perf_counter() - started) * 1000
                rows.append({
                    "case_id": case.id,
                    "answerable": case.answerable,
                    "expected_doc_ids": case.expected_doc_ids,
                    "evidences": evidences,
                    "evidence": [_evidence_json(evidence) for evidence in evidences],
                    "requested_top_k": requested_top_k,
                    "returned_count": len(evidences),
                    "status": status,
                    "error": error,
                    "elapsed_ms": elapsed_ms,
                    "timings": dict(getattr(engine.retriever, "last_timings", {})) if engine.retriever else {},
                })
            summary = aggregate_retrieval(rows, ks=ks)
            summary["status_counts"] = {
                status: sum(row["status"] == status for row in rows)
                for status in sorted({row["status"] for row in rows})
            }
            summary["ingest_ms"] = ingest_ms
            summary["retrieval_latency_ms"] = latency_summary(
                rows[0]["elapsed_ms"] if rows else None,
                [row["elapsed_ms"] for row in rows[1:]],
            )
            output["modes"][mode] = {"summary": summary, "rows": _json_rows(rows)}
        finally:
            engine.close()
    output["settings"] = {
        "dense_top_k": retrieval_config.get("dense_top_k", 20),
        "sparse_top_k": retrieval_config.get("sparse_top_k", 20),
        "rerank_candidate_k": retrieval_config.get("rerank_candidate_k", 40),
        "rerank_top_k": retrieval_config.get("rerank_top_k", 5),
    }
    return output


def _json_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key != "evidences"}
        for row in rows
    ]


def _run_generation(
    config: dict[str, Any], cases: list[BenchmarkCase], docs: list[tuple[Path, Any]], _corpus: dict[str, Any],
    *, settings: Settings, checkpoint_path: Path | None, checkpoint_id: dict[str, Any],
) -> dict[str, Any]:
    generation = dict(config.get("generation") or {})
    models = list(generation.get("models") or ["gemma3:4b", "gemma4:e4b"])
    case_ids = {case.id for case in cases}
    if checkpoint_path is not None and checkpoint_path.exists():
        checkpoint = load_checkpoint(checkpoint_path, checkpoint_id)
    else:
        checkpoint = {"identity": checkpoint_id, "evidence_cache": {}, "models": {}}
    engine = RAGForge(settings)
    evidence_cache: dict[str, list[Evidence]] = {}
    cache_meta: dict[str, dict[str, Any]] = {}
    started = time.perf_counter()
    try:
        engine.ingest_chunks(_chunks(engine, docs))
        ingest_ms = (time.perf_counter() - started) * 1000
        for case in cases:
            retrieval_started = time.perf_counter()
            evidence_cache[case.id] = engine.retrieve_only(
                case.question,
                retrieval_mode=generation.get("retrieval_mode", "hybrid"),
                top_k=int(generation.get("top_k", 5)),
            )
            cache_meta[case.id] = {
                "evidence_hash": evidence_fingerprint(evidence_cache[case.id]),
                "retrieval_ms": (time.perf_counter() - retrieval_started) * 1000,
                "evidence": [_evidence_json(evidence) for evidence in evidence_cache[case.id]],
            }
        previous_cache = checkpoint.get("evidence_cache", {})
        if previous_cache:
            for case_id, previous in previous_cache.items():
                current = cache_meta.get(case_id)
                if not isinstance(previous, dict) or current is None or previous.get("evidence_hash") != current["evidence_hash"]:
                    raise ValueError(
                        "benchmark checkpoint evidence mismatch; use a new checkpoint path"
                    )
        checkpoint["evidence_cache"] = cache_meta
        if checkpoint_path is not None:
            _write_json_atomically(checkpoint_path, checkpoint)
        output: dict[str, Any] = {
            "backend": settings.generation_backend,
            "models": {},
            "ingest_ms": ingest_ms,
            "evidence_cache": cache_meta,
            "retrieval_runs": len(evidence_cache),
            "resumed_counts": {},
        }
        for model in models:
            rows_by_id = _checkpoint_rows(checkpoint, model, case_ids)
            output["resumed_counts"][model] = len(rows_by_id)
            for case in cases:
                if case.id in rows_by_id:
                    continue
                evidences = evidence_cache[case.id]
                started = time.perf_counter()
                error: dict[str, str] | None = None
                answer = None
                try:
                    answer = engine.generator.generate(
                        case.question, evidences, f"benchmark-{case.id}", model=model,
                    )
                except Exception as exc:
                    error = {"type": type(exc).__name__, "message": str(exc)[:500]}
                elapsed_ms = (time.perf_counter() - started) * 1000
                if answer is None:
                    raw = ""
                    refused = False
                    invalid = False
                    citation_indices: list[int] = []
                    valid_count = 0
                    status = "error"
                    actual_model = None
                else:
                    raw = answer.answer[:4000]
                    refused = answer.refused
                    invalid = answer.citation_invalid
                    citation_indices = extract_citation_indices(raw)
                    valid_count = sum(1 <= index <= len(evidences) for index in citation_indices)
                    status = "ok"
                    actual_model = answer.model
                row = {
                    "case_id": case.id,
                    "answerable": case.answerable,
                    "requested_model": model,
                    "actual_model": actual_model,
                    "status": status,
                    "answer": raw,
                    "refused": refused,
                    "citation_indices": citation_indices,
                    "valid_citations": valid_count,
                    "citation_count": len(citation_indices),
                    "citation_validity": citation_validity(valid_count, len(citation_indices), ran=answer is not None),
                    "citation_invalid": invalid,
                    "elapsed_ms": elapsed_ms,
                    "error": error,
                    "evidence_hash": cache_meta[case.id]["evidence_hash"],
                }
                rows_by_id[case.id] = row
                checkpoint["models"][model] = {
                    "completed_count": len(rows_by_id),
                    "rows": [rows_by_id[case_item.id] for case_item in cases if case_item.id in rows_by_id],
                }
                if checkpoint_path is not None:
                    _write_json_atomically(checkpoint_path, checkpoint)
            rows = [rows_by_id[case.id] for case in cases]
            confusion = refusal_confusion([(row["answerable"], row["refused"]) for row in rows])
            ran_rows = [row for row in rows if row["status"] == "ok"]
            validity_values = [row["citation_validity"] for row in ran_rows if row["citation_validity"] is not None]
            answerable_ran = [row for row in ran_rows if row["answerable"]]
            output["models"][model] = {
                "summary": {
                    "case_count": len(rows),
                    "status_counts": {status: sum(row["status"] == status for row in rows) for status in sorted({row["status"] for row in rows})},
                    "refusal_confusion": confusion,
                    "citation_validity_mean": statistics.fmean(validity_values) if validity_values else None,
                    "citation_validity_ran_count": len(validity_values),
                    "citation_coverage_answerable": (
                        sum(bool(row["citation_indices"]) for row in answerable_ran) / len(answerable_ran)
                        if answerable_ran else None
                    ),
                    "generation_latency_ms": {
                        **latency_summary(
                            rows[0]["elapsed_ms"] if rows else None,
                            [row["elapsed_ms"] for row in rows[1:]],
                        ),
                    },
                },
                "rows": rows,
            }
        checkpoint["status"] = "complete"
        if checkpoint_path is not None:
            _write_json_atomically(checkpoint_path, checkpoint)
        return output
    finally:
        engine.close()


def _run_chunking(
    config: dict[str, Any], cases: list[BenchmarkCase], docs: list[tuple[Path, Any]], corpus: dict[str, Any]
) -> dict[str, Any]:
    variants = _chunking_variants(config)
    results: dict[str, Any] = {}
    for variant in variants:
        size = variant["chunk_size"]
        overlap = variant["chunk_overlap"]
        storage = _chunking_storage(config, variant, corpus)
        settings = _settings(
            config,
            experiment="retrieval",
            chunk_size=size,
            chunk_overlap=overlap,
            storage=storage,
        )
        engine = RAGForge(settings)
        rows: list[dict[str, Any]] = []
        ingest_started = time.perf_counter()
        try:
            chunks = _chunks(engine, docs)
            engine.ingest_chunks(chunks)
            ingest_ms = (time.perf_counter() - ingest_started) * 1000
            for case in cases:
                started = time.perf_counter()
                status = "ok"
                error = None
                try:
                    evidences = engine.retrieve_only(case.question, retrieval_mode="hybrid", top_k=10)
                except Exception as exc:
                    evidences = []
                    status = "error"
                    error = {"type": type(exc).__name__, "message": str(exc)[:500]}
                rows.append({
                    "case_id": case.id,
                    "answerable": case.answerable,
                    "expected_doc_ids": case.expected_doc_ids,
                    "evidences": evidences,
                    "evidence": [_evidence_json(evidence) for evidence in evidences],
                    "requested_top_k": 10,
                    "status": status,
                    "error": error,
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                    "timings": dict(getattr(engine.retriever, "last_timings", {})) if engine.retriever else {},
                })
            summary = aggregate_retrieval(rows, ks=(5, 10))
            summary["chunk_count"] = len(chunks)
            summary["ingest_ms"] = ingest_ms
            summary["retrieval_latency_ms"] = latency_summary(
                rows[0]["elapsed_ms"] if rows else None,
                [row["elapsed_ms"] for row in rows[1:]],
            )
            results[f"{size}/{overlap}"] = {
                "index_identity": _identity(config, settings, corpus),
                "summary": summary,
                "rows": _json_rows(rows),
            }
        finally:
            engine.close()
    return {"variants": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="benchmarks/golden.jsonl")
    parser.add_argument("--config", default="configs/experiments.yaml")
    parser.add_argument("--experiment", choices=["retrieval", "generation", "chunking"], default="retrieval")
    parser.add_argument("--output", default=None)
    parser.add_argument("--allow-candidate", action="store_true", help="仅允许 provisional 管线试运行")
    parser.add_argument("--limit", type=int, default=None, help="仅均匀采样指定数量，适合昂贵的本地模型试跑")
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="生成实验逐题 checkpoint；重启时必须保持语料、索引、模型和参数身份一致",
    )
    parser.add_argument(
        "--split",
        default=None,
        help="review_benchmark 生成的冻结 split JSON；release profile 必须提供",
    )
    parser.add_argument(
        "--split-partition",
        choices=["calibration", "test"],
        default="test",
        help="使用冻结 split 的 calibration 或 test 分区",
    )
    args = parser.parse_args()

    config_path = _rooted(args.config)
    config = _read_config(config_path)
    corpus_root = _rooted((config.get("corpus") or {}).get("path", "data/processed/web"))
    docs, corpus_doc_ids, corpus = _load_corpus(corpus_root)
    dataset = _rooted(args.dataset)
    cases = load_cases(
        dataset,
        corpus_doc_ids=corpus_doc_ids,
        require_reviewed=not args.allow_candidate,
    )
    if not cases:
        raise ValueError("dataset contains no reviewed cases; review candidates before running a Golden Set benchmark")
    cases = select_cases(cases, args.limit)
    if any(case.review_status != "reviewed" for case in cases) and not args.allow_candidate:
        raise ValueError("candidate cases require --allow-candidate and remain provisional")
    frozen_split = None
    if args.split:
        split_ids, frozen_split = load_frozen_split(
            _rooted(args.split),
            cases,
            partition=args.split_partition,
        )
        cases = [case for case in cases if case.id in split_ids]
        if not cases:
            raise ValueError("selected frozen split partition is empty")
    settings = _settings(config, experiment=args.experiment)
    generation = dict(config.get("generation") or {})
    generation_models = list(generation.get("models") or settings.allowed_generation_models)
    generation_model_digests = _resolve_provider_identity(
        settings,
        generation_models if args.experiment == "generation" else [],
    )
    runtime_model_identity = model_identity(
        settings,
        generation_models,
        generation_model_digests=generation_model_digests,
    )
    quality_eligibility = assess_quality_eligibility(
        config,
        settings,
        cases,
        corpus,
        experiment=args.experiment,
    )
    if config.get("profile", "diagnostic") == "release" and args.limit is not None:
        quality_eligibility = {
            **quality_eligibility,
            "eligible": False,
            "reasons": [*quality_eligibility["reasons"], "release_limit_sampling"],
        }
    if config.get("profile", "diagnostic") == "release" and not args.split:
        quality_eligibility = {
            **quality_eligibility,
            "eligible": False,
            "reasons": [*quality_eligibility["reasons"], "missing_frozen_split"],
        }
    if (
        config.get("profile", "diagnostic") == "release"
        and args.experiment == "generation"
        and settings.generation_backend == "ollama"
        and any(generation_model_digests.get(model) is None for model in generation_models)
    ):
        quality_eligibility = {
            **quality_eligibility,
            "eligible": False,
            "reasons": [*quality_eligibility["reasons"], "missing_generation_model_digest"],
        }
    if config.get("profile", "diagnostic") == "release" and not quality_eligibility["eligible"]:
        raise ValueError(
            "release benchmark is not quality eligible: "
            + ", ".join(quality_eligibility["reasons"])
        )
    provisional = (
        args.allow_candidate
        or any(case.review_status != "reviewed" for case in cases)
        or not quality_eligibility["eligible"]
    )
    output = _base_output(
        experiment=args.experiment, dataset=dataset, cases=cases,
        corpus=corpus, settings=settings, provisional=provisional,
        quality_eligibility=quality_eligibility,
        runtime_model_identity=runtime_model_identity,
        frozen_split=frozen_split,
    )
    if args.experiment == "retrieval":
        retrieval = dict(config.get("retrieval") or {})
        modes = list(retrieval.get("modes") or ["dense", "hybrid", "hybrid_rerank"])
        ks = tuple(int(k) for k in retrieval.get("ks", [5, 10]))
        output["results"] = _run_retrieval(config, cases, docs, corpus, ks, modes)
    elif args.experiment == "generation":
        checkpoint_path = _rooted(args.checkpoint) if args.checkpoint else None
        checkpoint_id = checkpoint_identity(
            experiment=args.experiment,
            dataset=dataset,
            case_ids=[case.id for case in cases],
            corpus=corpus,
            settings=settings,
            model_identity=runtime_model_identity,
            split_hash=frozen_split.get("split_sha256") if frozen_split else None,
        )
        output["results"] = _run_generation(
            config,
            cases,
            docs,
            corpus,
            settings=settings,
            checkpoint_path=checkpoint_path,
            checkpoint_id=checkpoint_id,
        )
    else:
        output["results"] = _run_chunking(config, cases, docs, corpus)
    output_path = _rooted(args.output or f"data/reports/m9-{args.experiment}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "experiment": args.experiment,
        "cases": len(cases),
        "provisional": provisional,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
