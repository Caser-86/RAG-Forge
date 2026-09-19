import hashlib
import json
from pathlib import Path

from scripts.release_gate import REQUIRED_FILES, evaluate_release
from ragforge.evaluation.benchmark import benchmark_dataset_content_sha256


def _write_repo_skeleton(repo_root):
    for relative in REQUIRED_FILES:
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")
    corpus = repo_root / "data" / "processed" / "web"
    corpus.mkdir(parents=True, exist_ok=True)
    (corpus / "doc.md").write_text("evidence\n", encoding="utf-8")
    (repo_root / "benchmarks").mkdir(parents=True, exist_ok=True)
    (repo_root / "benchmarks" / "golden.jsonl").write_text("", encoding="utf-8")


def _write_reviewed_golden(repo_root, count=100):
    rows = []
    for index in range(count):
        rows.append(
            {
                "id": f"case-{index:03d}",
                "question": f"Question {index}",
                "expected_doc_ids": ["d1"],
                "expected_answer": "answer",
                "answerable": True,
                "category": "basic",
                "review_status": "reviewed",
                "reviewer": "alice",
                "reviewed_at": "2026-09-12T00:00:00Z",
                "corpus_identity": {},
                "index_identity": {},
                "source_refs": ["data/processed/web/doc.md"],
            }
        )
    golden = repo_root / "benchmarks" / "golden.jsonl"
    golden.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return rows


def _write_split(repo_root, rows):
    split = {
        "schema_version": 2,
        "calibration_ids": [row["id"] for row in rows[:20]],
        "test_ids": [row["id"] for row in rows[20:]],
        "dataset_content_sha256": benchmark_dataset_content_sha256(rows),
    }
    split["split_sha256"] = hashlib.sha256(
        json.dumps(split, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    path = repo_root / "benchmarks" / "golden-split.json"
    path.write_text(json.dumps(split, ensure_ascii=False), encoding="utf-8")


def test_release_gate_blocks_empty_golden_and_missing_license(tmp_path):
    _write_repo_skeleton(tmp_path)

    report = evaluate_release(tmp_path)

    assert report["ready"] is False
    assert report["status"] == "BLOCKED"
    assert "license_missing" in report["blockers"]
    assert "golden_empty" in report["blockers"]
    assert "split_missing" in report["blockers"]


def test_release_gate_accepts_reviewed_golden_and_valid_split(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    _write_split(tmp_path, rows)

    report = evaluate_release(tmp_path)

    assert report["ready"] is True
    assert report["status"] == "READY"
    assert report["blockers"] == []


def test_release_gate_rejects_tampered_split(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    _write_split(tmp_path, rows)
    split_path = tmp_path / "benchmarks" / "golden-split.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split["test_ids"] = split["test_ids"][1:]
    split_path.write_text(json.dumps(split), encoding="utf-8")

    report = evaluate_release(tmp_path)

    assert report["ready"] is False
    assert "split_hash_mismatch" in report["blockers"]


def test_release_gate_rejects_split_when_case_content_changes(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    _write_split(tmp_path, rows)
    rows[0]["question"] = "Changed question with the same case id"
    (tmp_path / "benchmarks" / "golden.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )

    report = evaluate_release(tmp_path)

    assert report["ready"] is False
    assert "split_dataset_content_mismatch" in report["blockers"]


def test_release_gate_resolves_custom_paths_from_repo_root(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    _write_split(tmp_path, rows)

    report = evaluate_release(
        tmp_path,
        golden_path=Path("benchmarks/golden.jsonl"),
        split_path=Path("benchmarks/golden-split.json"),
    )

    assert report["ready"] is True


def test_release_gate_rejects_incomplete_reviewed_case(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    rows[0].pop("question")
    (tmp_path / "benchmarks" / "golden.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    _write_split(tmp_path, rows)

    report = evaluate_release(tmp_path)

    assert report["ready"] is False
    assert "golden_invalid_schema" in report["blockers"]


def test_release_gate_blocks_missing_release_companion(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "docker-compose.ollama.yml").unlink()

    report = evaluate_release(tmp_path)

    assert report["ready"] is False
    required = next(check for check in report["checks"] if check["name"] == "required_files")
    assert "docker-compose.ollama.yml" in required["missing"]
    assert "required_files_missing" in report["blockers"]


def test_release_gate_allows_empty_sources_for_reviewed_unanswerable_case(tmp_path):
    _write_repo_skeleton(tmp_path)
    (tmp_path / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    rows = _write_reviewed_golden(tmp_path)
    rows[0].update(
        {
            "expected_doc_ids": [],
            "expected_answer": "",
            "answerable": False,
            "category": "unanswerable",
            "source_refs": [],
        }
    )
    (tmp_path / "benchmarks" / "golden.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    _write_split(tmp_path, rows)

    report = evaluate_release(tmp_path)

    assert report["ready"] is True
