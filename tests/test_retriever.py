"""RRF 融合 与 检索层指标 的离线单元测试。"""
from ragforge.evaluation import hit_at_k, mrr, recall_at_k
from ragforge.models import Chunk, Evidence
from ragforge.retriever import rrf_fuse


def _chunk(i):
    return Chunk(id=f"c{i}", doc_id=f"d{i}", title=f"t{i}", text=f"text {i}", source=f"src{i}")


def _ev(chunks_scores):
    return [Evidence(chunk=c, fused_score=s) for c, s in chunks_scores]


def test_rrf_prefers_top_rank_present_in_both():
    a = [(_chunk(1), 1.0), (_chunk(2), 0.9), (_chunk(3), 0.8)]
    b = [(_chunk(2), 1.0), (_chunk(1), 0.9), (_chunk(4), 0.7)]
    fused = rrf_fuse(a, b, k=60)
    # c1 在两路都是 rank1 → 融合分最高；c2 仅 rank2+rank1，次之
    assert [c.id for c, _ in fused][:2] == ["c1", "c2"]


def test_hit_recall_mrr():
    gold = {"c1"}
    evs = _ev([(_chunk(2), 0.9), (_chunk(1), 0.5)])
    assert hit_at_k(evs, gold, k=2) is True
    assert round(recall_at_k(evs, gold, k=2), 3) == 1.0
    assert round(mrr(evs, gold), 3) == 0.5  # 命中的在 rank2


def test_recall_no_gold_is_zero():
    assert recall_at_k(_ev([(_chunk(1), 0.9)]), set(), k=2) == 0.0