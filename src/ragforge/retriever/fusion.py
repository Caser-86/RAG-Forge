"""多路召回融合：Reciprocal Rank Fusion（RRF）取稠密/稀疏之长。"""
from __future__ import annotations

from ..models import Chunk


def rrf_fuse(
    *ranked_lists: list[tuple[Chunk, float]],
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    """对多路排序的 chunk 列表做 RRF 融合，返回按融合分降序的列表。

    RRF 分数 = Σ 1/(k + rank)。好处：不依赖各路分数量纲/置信度可比性。
    """
    scores: dict[str, tuple[Chunk, float]] = {}
    for ranked in ranked_lists:
        for rank, (chunk, _score) in enumerate(ranked, start=1):
            cid = chunk.id
            if cid in scores:
                scores[cid] = (chunk, scores[cid][1] + 1.0 / (k + rank))
            else:
                scores[cid] = (chunk, 1.0 / (k + rank))
    return sorted(scores.values(), key=lambda x: x[1], reverse=True)
