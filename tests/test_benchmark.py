import json

import pytest

from ragforge.evaluation.benchmark import (
    BenchmarkCase,
    aggregate_retrieval,
    assess_quality_eligibility,
    benchmark_content_sha256,
    benchmark_dataset_content_sha256,
    latency_summary,
    load_cases,
    select_cases,
    validate_cases,
)
from scripts.run_benchmark import (
    _settings,
    checkpoint_identity,
    load_checkpoint,
    load_frozen_split,
    model_identity,
)
from ragforge.config import Settings
from ragforge.models import Chunk, Evidence


def _case(case_id: str, question: str, *, answerable: bool = True, docs=None):
    return {
        "id": case_id,
        "question": question,
        "expected_doc_ids": docs if docs is not None else ["d1"],
        "expected_answer": "answer" if answerable else "",
        "answerable": answerable,
        "category": "basic",
        "review_status": "reviewed",
        "reviewer": "tester",
        "reviewed_at": "2026-09-12T00:00:00Z",
        "corpus_identity": {"name": "test"},
        "index_identity": {"chunk_size": 100},
    }


def test_load_cases_validates_ids_questions_and_review_status(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [_case("a", "same"), _case("b", "other", answerable=False, docs=[])]),
        encoding="utf-8",
    )

    cases = load_cases(path, corpus_doc_ids={"d1"}, require_reviewed=True)

    assert [case.id for case in cases] == ["a", "b"]
    assert cases[1].expected_doc_ids == []

    duplicate_path = tmp_path / "duplicate.jsonl"
    duplicate_path.write_text(
        "\n".join(json.dumps(row) for row in [_case("a", "same"), _case("a", "other")]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate case id"):
        load_cases(duplicate_path)


def test_candidate_dataset_is_not_accepted_as_golden_without_review():
    row = _case("candidate", "q")
    row["review_status"] = "candidate"

    with pytest.raises(ValueError, match="reviewed"):
        validate_cases([BenchmarkCase.from_mapping(row)], require_reviewed=True)


def test_reviewed_case_requires_nonempty_string_reviewer_and_timestamp():
    row = _case("reviewed", "reviewer type")
    row["reviewer"] = 123
    with pytest.raises(ValueError, match="reviewer and reviewed_at"):
        validate_cases([BenchmarkCase.from_mapping(row)])

    row = _case("reviewed-time", "reviewed time")
    row["reviewed_at"] = []
    with pytest.raises(ValueError, match="reviewer and reviewed_at"):
        validate_cases([BenchmarkCase.from_mapping(row)])


def test_aggregate_retrieval_uses_answerable_denominator_and_document_ids():
    rows = [
        {
            "case_id": "a",
            "answerable": True,
            "expected_doc_ids": ["d1", "d2"],
            "evidences": [
                Evidence(chunk=Chunk(id="c1", doc_id="d1", title="", text="")),
                Evidence(chunk=Chunk(id="c2", doc_id="d1", title="", text="")),
                Evidence(chunk=Chunk(id="c3", doc_id="d2", title="", text="")),
            ],
            "requested_top_k": 5,
            "timings": {},
        },
        {
            "case_id": "u",
            "answerable": False,
            "expected_doc_ids": [],
            "evidences": [],
            "requested_top_k": 5,
            "timings": {},
        },
    ]

    summary = aggregate_retrieval(rows, ks=(1, 5))

    assert summary["answerable_count"] == 1
    assert summary["unanswerable_count"] == 1
    assert summary["metrics"]["1"]["Recall"] == 0.5
    assert summary["metrics"]["5"]["Recall"] == 1.0
    assert summary["metrics"]["5"]["Hit"] == 1.0


def test_latency_summary_separates_cold_start_and_warm_percentiles():
    summary = latency_summary(cold_ms=100.0, warm_ms=[10.0, 20.0, 30.0, 40.0])

    assert summary["cold_start_ms"] == 100.0
    assert summary["warm_count"] == 4
    assert summary["warm_p50_ms"] == 20.0
    assert summary["warm_p95_ms"] == 40.0


def test_select_cases_samples_across_dataset_without_duplicates():
    cases = [BenchmarkCase.from_mapping(_case(str(index), f"q-{index}")) for index in range(10)]

    selected = select_cases(cases, 4)

    assert len(selected) == 4
    assert len({case.id for case in selected}) == 4
    assert selected[0].id == "0"
    assert selected[-1].id == "9"


def test_quality_gate_rejects_diagnostic_deterministic_offline_profile():
    settings = Settings(_env_file=None, embedder_backend="deterministic", generation_backend="offline")
    case = BenchmarkCase.from_mapping(_case("a", "same"))

    result = assess_quality_eligibility(
        {"profile": "diagnostic"},
        settings,
        [case],
        {"sha256": "corpus", "file_count": 1},
        experiment="generation",
    )

    assert result["eligible"] is False
    assert "diagnostic_profile" in result["reasons"]
    assert "deterministic_embedder" in result["reasons"]
    assert "offline_generator" in result["reasons"]


def test_quality_gate_accepts_only_reviewed_real_release_profile():
    settings = Settings(
        _env_file=None,
        embedder_backend="ollama",
        embedder_model="bge-m3",
        embedder_digest="sha256:real-revision",
        generation_backend="ollama",
        use_rerank=True,
    )
    case = BenchmarkCase.from_mapping(_case("a", "same"))

    result = assess_quality_eligibility(
        {"profile": "release"},
        settings,
        [case],
        {"sha256": "corpus", "file_count": 1},
        experiment="generation",
    )

    assert result == {"eligible": True, "profile": "release", "reasons": []}


def test_benchmark_checkpoint_rejects_changed_identity(tmp_path):
    settings = Settings(
        _env_file=None,
        embedder_backend="ollama",
        embedder_model="bge-m3",
        embedder_digest="sha256:real-revision",
        generation_backend="ollama",
        generation_temperature=0.2,
        generation_num_predict=512,
        generation_seed=42,
        ollama_generate_timeout=180,
        use_rerank=True,
    )
    corpus = {"sha256": "corpus", "file_count": 1, "document_ids": ["d1"]}
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text("dataset\n", encoding="utf-8")
    identity = checkpoint_identity(
        experiment="generation",
        dataset=dataset,
        case_ids=["a"],
        corpus=corpus,
        settings=settings,
        model_identity=model_identity(settings, ["gemma3:4b"]),
    )
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"identity": identity, "models": {}, "evidence_cache": {} }), encoding="utf-8")

    assert load_checkpoint(checkpoint, identity)["models"] == {}
    changed = {**identity, "model_identity": {**identity["model_identity"], "generation_seed": 43}}
    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        load_checkpoint(checkpoint, changed)
    changed_cases = {**identity, "case_ids": ["a", "new-case"]}
    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        load_checkpoint(checkpoint, changed_cases)


@pytest.mark.parametrize("field,value", [
    ("dense_top_k", 21),
    ("sparse_top_k", 21),
    ("rerank_candidate_k", 41),
    ("rerank_top_k", 6),
    ("rerank_model", "other-reranker"),
    ("top_k", 6),
])
def test_checkpoint_rejects_changed_retrieval_contract(tmp_path, field, value):
    base = Settings(
        _env_file=None,
        embedder_backend="ollama",
        embedder_model="bge-m3",
        embedder_digest="sha256:real-revision",
        generation_backend="ollama",
        vector_store="in_memory",
        use_rerank=True,
        generation_num_predict=128,
    )
    dataset = tmp_path / "golden.jsonl"
    dataset.write_text("dataset\n", encoding="utf-8")
    corpus = {"sha256": "corpus", "file_count": 1}
    models = model_identity(base, ["gemma3:4b"])
    identity = checkpoint_identity(
        experiment="generation",
        dataset=dataset,
        case_ids=["a"],
        corpus=corpus,
        settings=base,
        model_identity=models,
    )
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"identity": identity, "models": {}, "evidence_cache": {}}), encoding="utf-8")

    changed = base.model_copy(update={field: value})
    changed_identity = checkpoint_identity(
        experiment="generation",
        dataset=dataset,
        case_ids=["a"],
        corpus=corpus,
        settings=changed,
        model_identity=model_identity(changed, ["gemma3:4b"]),
    )
    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        load_checkpoint(checkpoint, changed_identity)


def test_benchmark_settings_include_generation_top_k_in_identity():
    config = {
        "index": {"backend": "in_memory"},
        "retrieval": {"modes": ["hybrid"]},
        "generation": {"top_k": 9, "models": ["gemma3:4b"]},
    }

    assert _settings(config, experiment="generation").top_k == 9


def test_frozen_split_validates_hash_and_selects_requested_partition(tmp_path):
    cases = [BenchmarkCase.from_mapping(_case(str(index), f"q-{index}")) for index in range(2)]
    split = {
        "schema_version": 2,
        "calibration_ids": ["0"],
        "test_ids": ["1"],
        "dataset_content_sha256": benchmark_dataset_content_sha256([
            {**_case("0", "q-0"), "content_sha256": benchmark_content_sha256(_case("0", "q-0"))},
            {**_case("1", "q-1"), "content_sha256": benchmark_content_sha256(_case("1", "q-1"))},
        ]),
    }
    split["split_sha256"] = __import__("hashlib").sha256(
        json.dumps(split, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "split.json"
    path.write_text(json.dumps(split), encoding="utf-8")

    assert load_frozen_split(path, cases, partition="test") == ({"1"}, split)

    split["test_ids"] = ["0"]
    path.write_text(json.dumps(split), encoding="utf-8")
    with pytest.raises(ValueError, match="split hash"):
        load_frozen_split(path, cases, partition="test")


@pytest.mark.parametrize("field,value", [
    ("question", "changed question"),
    ("expected_answer", "changed answer"),
    ("source_refs", ["data/processed/web/changed.md"]),
    ("corpus_identity", {"name": "changed corpus"}),
])
def test_frozen_split_rejects_same_id_with_changed_case_content(tmp_path, field, value):
    rows = [_case("0", "q-0"), _case("1", "q-1")]
    split = {
        "schema_version": 2,
        "calibration_ids": ["0"],
        "test_ids": ["1"],
        "dataset_content_sha256": benchmark_dataset_content_sha256(rows),
    }
    split["split_sha256"] = __import__("hashlib").sha256(
        json.dumps(split, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "split.json"
    path.write_text(json.dumps(split), encoding="utf-8")

    changed = dict(rows[0])
    changed[field] = value
    cases = [BenchmarkCase.from_mapping(changed), BenchmarkCase.from_mapping(rows[1])]
    with pytest.raises(ValueError, match="dataset content"):
        load_frozen_split(path, cases, partition="test")
