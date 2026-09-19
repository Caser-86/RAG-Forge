"""稀疏检索：BM25（精确命中专有名词/关键词，与稠密互补）。"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from ..models import Chunk

TOKENIZER_VERSION = "cjk-char-bigram-v1"
_CJK_RANGES = (("\u3400", "\u4dbf"), ("\u4e00", "\u9fff"), ("\uf900", "\ufaff"))
_WORD_CHARS = re.compile(r"[a-zA-Z0-9_]")


def _is_cjk(char: str) -> bool:
    return any(start <= char <= end for start, end in _CJK_RANGES)


def tokenize(text: str) -> list[str]:
    """英文/数字按词，CJK 同时生成单字和相邻双字 token。"""
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if _is_cjk(char):
            end = index + 1
            while end < len(text) and _is_cjk(text[end]):
                end += 1
            run = text[index:end]
            tokens.extend(run)
            tokens.extend(run[offset:offset + 2] for offset in range(len(run) - 1))
            index = end
            continue
        if _WORD_CHARS.fullmatch(char):
            end = index + 1
            while end < len(text) and _WORD_CHARS.fullmatch(text[end]):
                end += 1
            tokens.append(text[index:end].lower())
            index = end
            continue
        index += 1
    return tokens


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        indexed = [(chunk, tokenize(chunk.text)) for chunk in chunks]
        self._indexed_chunks = [chunk for chunk, tokens in indexed if tokens]
        self._token_sets = [set(tokens) for _chunk, tokens in indexed if tokens]
        self.index = BM25Okapi(
            [[*tokens] for _chunk, tokens in indexed if tokens]
        ) if self._indexed_chunks else None

    def search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if top_k <= 0 or self.index is None:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self.index.get_scores(q_tokens)
        order = sorted(range(len(self._indexed_chunks)), key=lambda i: (-float(scores[i]), i))[:top_k]
        query_tokens = set(q_tokens)
        return [
            (self._indexed_chunks[i], float(scores[i]))
            for i in order
            if query_tokens.intersection(self._token_sets[i])
        ]
