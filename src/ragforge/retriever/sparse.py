"""稀疏检索：BM25（精确命中专有名词/关键词，与稠密互补）。"""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from ..models import Chunk

_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.index = BM25Okapi([tokenize(c.text) for c in chunks]) if chunks else None

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if self.index is None:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self.index.get_scores(q_tokens)
        order = np.argsort(scores)[::-1][:top_k]
        return [(self.chunks[i], float(scores[i])) for i in order if scores[i] > 0]