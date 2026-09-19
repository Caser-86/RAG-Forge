from ragforge.evaluation import (
    citation_validity,
    refusal_confusion,
    retrieval_identifier,
)
from ragforge.models import Chunk, Evidence


def _evidence(chunk_id: str, doc_id: str) -> Evidence:
    return Evidence(chunk=Chunk(id=chunk_id, doc_id=doc_id, title=doc_id, text="evidence"))


def test_retrieval_identifier_deduplicates_documents():
    evidences = [_evidence("c1", "d1"), _evidence("c2", "d1"), _evidence("c3", "d2")]

    assert retrieval_identifier(evidences, by="document") == ["d1", "d2"]
    assert retrieval_identifier(evidences, by="chunk") == ["c1", "c2", "c3"]


def test_citation_validity_does_not_turn_zero_or_unrun_into_perfect_score():
    assert citation_validity(valid=0, total=0, ran=True) == 0.0
    assert citation_validity(valid=0, total=0, ran=False) is None
    assert citation_validity(valid=2, total=3, ran=True) == 2 / 3


def test_refusal_confusion_matrix_separates_answerable_and_unanswerable():
    # (answerable, predicted_refused)
    rows = [(True, False), (True, True), (False, True), (False, False)]

    assert refusal_confusion(rows) == {
        "true_positive": 1,
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
    }
