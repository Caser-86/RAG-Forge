"""Golden/candidate 数据集校验、检索指标聚合与实验身份工具。"""
from __future__ import annotations

import hashlib
import json
from math import ceil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import Evidence
from .metrics import hit_at_k, mrr, recall_at_k, retrieval_identifier

ALLOWED_CATEGORIES = {
    "basic", "definition", "keyword", "rewrite", "cross-language",
    "cross-document", "unanswerable",
}


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    question: str
    expected_doc_ids: list[str]
    expected_answer: str
    answerable: bool
    category: str
    review_status: str
    reviewer: str | None
    reviewed_at: str | None
    corpus_identity: dict[str, Any]
    index_identity: dict[str, Any]
    content_sha256: str

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> BenchmarkCase:
        expected_doc_ids = row.get("expected_doc_ids", [])
        if not isinstance(expected_doc_ids, list) or not all(isinstance(x, str) and x for x in expected_doc_ids):
            raise ValueError("expected_doc_ids must be a list of non-empty strings")
        expected_answer = row.get("expected_answer", "")
        if expected_answer is None:
            expected_answer = ""
        if not isinstance(expected_answer, str):
            raise ValueError("expected_answer must be a string or null")
        return cls(
            id=_required_string(row, "id"),
            question=_required_string(row, "question"),
            expected_doc_ids=list(dict.fromkeys(expected_doc_ids)),
            expected_answer=expected_answer,
            answerable=_required_bool(row, "answerable"),
            category=_required_string(row, "category"),
            review_status=_required_string(row, "review_status"),
            reviewer=row.get("reviewer"),
            reviewed_at=row.get("reviewed_at"),
            corpus_identity=_required_mapping(row, "corpus_identity"),
            index_identity=_required_mapping(row, "index_identity"),
            content_sha256=benchmark_content_sha256(row),
        )


def _required_string(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _required_bool(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _required_mapping(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return dict(value)


def benchmark_content_sha256(row: dict[str, Any]) -> str:
    """Hash case content while excluding review bookkeeping and the hash itself."""
    content = {
        key: value
        for key, value in row.items()
        if key not in {"review_status", "reviewer", "reviewed_at", "content_sha256"}
    }
    return hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def benchmark_dataset_content_sha256(rows: list[dict[str, Any]]) -> str:
    """Hash the complete reviewed dataset independent of JSONL row order."""
    entries = [
        {
            "id": str(row["id"]),
            "content_sha256": str(row.get("content_sha256") or benchmark_content_sha256(row)),
        }
        for row in rows
    ]
    entries.sort(key=lambda entry: entry["id"])
    return hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def validate_cases(
    cases: list[BenchmarkCase],
    *,
    corpus_doc_ids: set[str] | None = None,
    require_reviewed: bool = False,
) -> None:
    ids: set[str] = set()
    questions: set[str] = set()
    for case in cases:
        if case.id in ids:
            raise ValueError(f"duplicate case id: {case.id}")
        ids.add(case.id)
        question_key = " ".join(case.question.casefold().split())
        if question_key in questions:
            raise ValueError(f"duplicate question: {case.id}")
        questions.add(question_key)
        if case.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"unsupported category: {case.category}")
        if require_reviewed and case.review_status != "reviewed":
            raise ValueError(f"case {case.id} is not reviewed")
        if (
            case.review_status == "reviewed"
            and (
                not isinstance(case.reviewer, str)
                or not case.reviewer.strip()
                or not isinstance(case.reviewed_at, str)
                or not case.reviewed_at.strip()
            )
        ):
            raise ValueError(f"reviewed case {case.id} needs reviewer and reviewed_at")
        if case.answerable and not case.expected_doc_ids:
            raise ValueError(f"answerable case {case.id} needs expected_doc_ids")
        if not case.answerable and case.expected_doc_ids:
            raise ValueError(f"unanswerable case {case.id} must have empty expected_doc_ids")
        if case.category == "unanswerable" and case.answerable:
            raise ValueError(f"unanswerable category must be answerable=false: {case.id}")
        if corpus_doc_ids is not None:
            missing = set(case.expected_doc_ids) - corpus_doc_ids
            if missing:
                raise ValueError(f"case {case.id} references missing document ids: {sorted(missing)}")


def assess_quality_eligibility(
    config: dict[str, Any],
    settings: Any,
    cases: list[BenchmarkCase],
    corpus: dict[str, Any],
    *,
    experiment: str,
) -> dict[str, Any]:
    """Return explicit reasons why a run may not be published as a quality score."""
    profile = str(config.get("profile", "diagnostic"))
    reasons: list[str] = []
    if profile != "release":
        reasons.append("diagnostic_profile")
    if not cases:
        reasons.append("empty_dataset")
    if any(case.review_status != "reviewed" for case in cases):
        reasons.append("unreviewed_cases")
    if settings.embedder_backend == "deterministic":
        reasons.append("deterministic_embedder")
    if experiment == "generation" and settings.generation_backend == "offline":
        reasons.append("offline_generator")
    if not str(getattr(settings, "embedder_digest", "")).strip():
        reasons.append("missing_embedder_digest")
    if not isinstance(corpus.get("sha256"), str) or not corpus["sha256"].strip():
        reasons.append("missing_corpus_snapshot")
    if int(corpus.get("file_count", 0) or 0) <= 0:
        reasons.append("empty_corpus")
    if not settings.use_rerank:
        reasons.append("rerank_disabled")
    return {"eligible": not reasons, "profile": profile, "reasons": reasons}


def load_cases(
    path: str | Path,
    *,
    corpus_doc_ids: set[str] | None = None,
    require_reviewed: bool = False,
) -> list[BenchmarkCase]:
    rows: list[BenchmarkCase] = []
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    for line_number, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {file_path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"case at {file_path}:{line_number} must be an object")
        rows.append(BenchmarkCase.from_mapping(row))
    validate_cases(rows, corpus_doc_ids=corpus_doc_ids, require_reviewed=require_reviewed)
    return rows


def select_cases(cases: list[BenchmarkCase], limit: int | None) -> list[BenchmarkCase]:
    """按均匀位置采样，保留首尾并避免只取文件开头的单一类别。"""
    if limit is None or limit >= len(cases):
        return list(cases)
    if limit <= 0:
        raise ValueError("limit must be positive")
    if limit == 1:
        return [cases[0]]
    indices = [round(index * (len(cases) - 1) / (limit - 1)) for index in range(limit)]
    return [cases[index] for index in indices]


def stable_document_id(path: str | Path) -> str:
    data = Path(path).read_bytes()
    return f"doc:{hashlib.sha256(data).hexdigest()[:16]}"


def corpus_identity(root: str | Path) -> dict[str, Any]:
    base = Path(root)
    files = [p for p in sorted(base.rglob("*")) if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    digest = hashlib.sha256()
    ids: list[str] = []
    for path in files:
        relative = path.relative_to(base).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        ids.append(stable_document_id(path))
    return {
        "root": str(base),
        "file_count": len(files),
        "document_ids": ids,
        "sha256": digest.hexdigest(),
    }


def evidence_fingerprint(evidences: list[Evidence]) -> str:
    payload = [
        {"chunk_id": e.chunk.id, "document_id": e.chunk.doc_id, "text": e.chunk.text}
        for e in evidences
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def latency_summary(cold_ms: float | None, warm_ms: list[float]) -> dict[str, Any]:
    """区分冷启动与后续请求，避免首个慢请求污染预热后的 p50/p95。"""
    return {
        "cold_start_ms": cold_ms,
        "warm_count": len(warm_ms),
        "warm_p50_ms": _percentile(warm_ms, 0.50),
        "warm_p95_ms": _percentile(warm_ms, 0.95),
    }


def aggregate_retrieval(rows: list[dict[str, Any]], *, ks: tuple[int, ...] = (5, 10)) -> dict[str, Any]:
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    metrics: dict[str, dict[str, Any]] = {}
    for k in ks:
        values = [
            {
                "hit": hit_at_k(row["evidences"], set(row["expected_doc_ids"]), k, by="document"),
                "recall": recall_at_k(row["evidences"], set(row["expected_doc_ids"]), k, by="document"),
                "mrr": mrr(row["evidences"], set(row["expected_doc_ids"]), by="document"),
            }
            for row in answerable
        ]
        denominator = len(values)
        metrics[str(k)] = {
            "Hit": (sum(item["hit"] for item in values) / denominator) if denominator else None,
            "Recall": (sum(item["recall"] for item in values) / denominator) if denominator else None,
            "MRR": (sum(item["mrr"] for item in values) / denominator) if denominator else None,
            "answerable_denominator": denominator,
        }
    return {
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "metrics": metrics,
        "unanswerable_with_hits": sum(
            bool(set(retrieval_identifier(row["evidences"], by="document")))
            for row in unanswerable
        ),
        "top_k_observability": {
            "requested": sorted({row.get("requested_top_k") for row in rows if row.get("requested_top_k") is not None}),
            "returned_counts": [len(row["evidences"]) for row in rows],
            "short_returns": sum(
                1 for row in rows
                if row.get("requested_top_k") is not None and len(row["evidences"]) < row["requested_top_k"]
            ),
        },
    }
