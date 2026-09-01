"""重排：CrossEncoder（bge-reranker）对融合候选精排。"""
from __future__ import annotations

from ..models import Chunk


class Reranker:
    def __init__(self, model_name: str, enabled: bool = True):
        self.enabled = enabled
        self.model = None
        if enabled:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[tuple[Chunk, float]], top_k: int) -> list[tuple[Chunk, float]]:
        if not self.enabled or not self.model or not candidates:
            return candidates[:top_k]
        pairs = [(query, c.text) for c, _ in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False)
        merged = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [(c, float(s)) for (c, _), s in merged[:top_k]]

    def score(self, query: str, chunk: Chunk) -> float:
        if not self.model:
            return 0.0
        return float(self.model.predict([(query, chunk.text)], show_progress_bar=False)[0])