import json

import pytest

from scripts.review_benchmark import (
    export_reviewed,
    freeze_split,
    load_progress,
    main,
    review_content_sha256,
    source_previews,
    validate_source_refs,
)


def _row(case_id="a", status="candidate"):
    return {
        "id": case_id,
        "question": "What is documented?",
        "expected_doc_ids": ["d1"],
        "expected_answer": "A documented answer.",
        "answerable": True,
        "category": "basic",
        "review_status": status,
        "reviewer": "human" if status == "reviewed" else None,
        "reviewed_at": "2026-09-12T00:00:00Z" if status == "reviewed" else None,
        "corpus_identity": {"sha256": "corpus"},
        "index_identity": {"chunk_size": 2200},
        "source_refs": ["data/processed/web/doc.md"],
    }


def test_source_refs_must_stay_inside_corpus_root(tmp_path):
    corpus = tmp_path / "data" / "processed" / "web"
    corpus.mkdir(parents=True)
    (corpus / "doc.md").write_text("source", encoding="utf-8")
    row = _row()

    validate_source_refs(row, repo_root=tmp_path, corpus_root=corpus)

    row["source_refs"] = ["../secret.txt"]
    with pytest.raises(ValueError, match="outside corpus"):
        validate_source_refs(row, repo_root=tmp_path, corpus_root=corpus)


def test_progress_uses_latest_decision_and_export_never_exports_unreviewed(tmp_path):
    progress = tmp_path / "progress.jsonl"
    progress.write_text(
        "\n".join(
            json.dumps(item)
            for item in [
                {"id": "a", "action": "defer"},
                {"id": "a", "action": "accept", "reviewer": "alice", "reviewed_at": "2026-09-12T00:00:00Z", "content_sha256": review_content_sha256(_row("a"))},
                {"id": "b", "action": "reject", "reviewer": "alice", "reviewed_at": "2026-09-12T00:00:01Z"},
            ]
        ),
        encoding="utf-8",
    )
    decisions = load_progress(progress)
    assert decisions["a"]["action"] == "accept"

    output = tmp_path / "golden.jsonl"
    rows = export_reviewed([_row("a"), _row("b")], decisions, output)

    assert [row["id"] for row in rows] == ["a"]
    assert json.loads(output.read_text(encoding="utf-8"))["review_status"] == "reviewed"


def test_freeze_split_is_deterministic_and_has_no_duplicate_questions():
    rows = []
    for index in range(4):
        row = _row(str(index), status="reviewed")
        row["question"] = f"Question {index}"
        rows.append(row)

    split = freeze_split(rows, calibration_count=2)

    assert split["calibration_ids"] == ["0", "1"]
    assert split["test_ids"] == ["2", "3"]
    assert len(split["split_sha256"]) == 64


def test_freeze_split_round_robins_categories_for_calibration_coverage():
    rows = []
    for category in ("basic", "definition", "keyword"):
        for index in range(2):
            row = _row(f"{category}-{index}", status="reviewed")
            row["category"] = category
            row["question"] = f"{category} question {index}"
            rows.append(row)

    split = freeze_split(rows, calibration_count=3)

    assert {case_id.split("-")[0] for case_id in split["calibration_ids"]} == {
        "basic", "definition", "keyword"
    }
    assert split["category_counts"] == {"basic": 2, "definition": 2, "keyword": 2}


def test_freeze_split_rejects_unreviewed_rows():
    with pytest.raises(ValueError, match="reviewed"):
        freeze_split([_row("candidate")], calibration_count=1)


def test_source_previews_show_bounded_corpus_evidence(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "doc.md"
    source.write_text("# Heading\n\nEvidence text", encoding="utf-8")
    row = _row()
    row["source_refs"] = ["corpus/doc.md"]

    previews = source_previews(row, repo_root=tmp_path, corpus_root=corpus, max_chars=20)

    assert previews == [{"source_ref": "corpus/doc.md", "text": "# Heading\n\nEvidence "}]


def test_source_previews_focus_on_expected_answer_in_long_source(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "doc.md"
    expected = "The target evidence is near the end of this document."
    source.write_text("prefix " * 500 + expected + " suffix " * 500, encoding="utf-8")
    row = _row()
    row["expected_answer"] = expected
    row["source_refs"] = ["corpus/doc.md"]

    previews = source_previews(row, repo_root=tmp_path, corpus_root=corpus, max_chars=120)

    assert expected in previews[0]["text"]
    assert len(previews[0]["text"]) <= 120


def test_source_previews_focus_on_quoted_question_heading(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "doc.md"
    heading = "Body - Updates"
    source.write_text("prefix " * 500 + f"# {heading}[¶](#body-updates)\nEvidence" + " suffix" * 500, encoding="utf-8")
    row = _row()
    row["expected_answer"] = "A paraphrase that is not verbatim in the source."
    row["question"] = f"What is covered in the documentation section '{heading}¶ (chunk-hash)'?"
    row["source_refs"] = ["corpus/doc.md"]

    previews = source_previews(row, repo_root=tmp_path, corpus_root=corpus, max_chars=120)

    assert heading in previews[0]["text"]


def test_review_cli_accepts_absolute_windows_style_paths(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "doc.md"
    source.write_text("source", encoding="utf-8")
    row = _row()
    row["source_refs"] = ["corpus/doc.md"]
    candidate = tmp_path / "candidates.jsonl"
    candidate.write_text(json.dumps(row) + "\n", encoding="utf-8")
    progress = tmp_path / "progress.jsonl"
    progress.write_text(
        json.dumps({
            "id": "a",
            "action": "accept",
            "reviewer": "alice",
            "reviewed_at": "2026-09-12T00:00:00Z",
            "content_sha256": review_content_sha256(row),
        }) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "golden.jsonl"

    assert main([
        "--input", str(candidate),
        "--progress", str(progress),
        "--output", str(output),
        "--repo-root", str(tmp_path),
        "--corpus-root", str(corpus),
        "--export-only",
    ]) == 0
    assert output.is_file()


@pytest.mark.parametrize("field,value", [
    ("question", "Changed question"),
    ("expected_answer", "Changed answer"),
    ("source_refs", ["data/processed/web/other.md"]),
])
def test_changed_case_cannot_reuse_review(tmp_path, monkeypatch, field, value):
    from scripts.review_benchmark import review_interactively

    row = _row()
    row["source_refs"] = []
    progress = tmp_path / "progress.jsonl"
    monkeypatch.setattr("builtins.input", lambda _: "a")
    review_interactively([row], progress, "alice", repo_root=tmp_path, corpus_root=tmp_path)
    decisions = load_progress(progress)
    assert len(export_reviewed([row], decisions, tmp_path / "valid.jsonl")) == 1
    row[field] = value
    output = tmp_path / "protected.jsonl"
    output.write_text("existing result", encoding="utf-8")
    with pytest.raises(ValueError, match="review.*mismatch"):
        export_reviewed([row], decisions, output)
    assert output.read_text(encoding="utf-8") == "existing result"


def test_changed_case_is_prompted_again(tmp_path, monkeypatch):
    from scripts.review_benchmark import review_interactively

    row = _row()
    row["source_refs"] = []
    progress = tmp_path / "progress.jsonl"
    monkeypatch.setattr("builtins.input", lambda _: "a")
    review_interactively([row], progress, "alice", repo_root=tmp_path, corpus_root=tmp_path)
    row["question"] = "New question requiring review"
    monkeypatch.setattr("builtins.input", lambda _: "r")
    review_interactively([row], progress, "bob", repo_root=tmp_path, corpus_root=tmp_path)
    assert load_progress(progress)["a"]["action"] == "reject"


def test_legacy_review_without_content_binding_is_rejected(tmp_path):
    decision = {"a": {"action": "accept", "reviewer": "alice", "reviewed_at": "2026-09-12"}}
    with pytest.raises(ValueError, match="review.*mismatch"):
        export_reviewed([_row()], decision, tmp_path / "out.jsonl")
