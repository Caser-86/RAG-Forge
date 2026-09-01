"""评测：检索层(Hit@K/Recall@K/MRR) 与 生成层(忠实度/引用支撑) 量化。"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Evidence


# ---------- 检索层指标 ----------

def hit_at_k(evidences: list[Evidence], gold_ids: set[str], k: int | None = None) -> bool:
    hits = evidences if k is None else evidences[:k]
    return any(e.chunk.id in gold_ids for e in hits)


def recall_at_k(evidences: list[Evidence], gold_ids: set[str], k: int | None = None) -> float:
    if not gold_ids:
        return 0.0
    hits = evidences if k is None else evidences[:k]
    hit_ids = {e.chunk.id for e in hits}
    return len(hit_ids & gold_ids) / len(gold_ids)


def mrr(evidences: list[Evidence], gold_ids: set[str]) -> float:
    for rank, e in enumerate(evidences, start=1):
        if e.chunk.id in gold_ids:
            return 1.0 / rank
    return 0.0


# ---------- 生成层指标 ----------

def _token_set(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", text.lower() or ""))


def faithfulness_proxy(answer: str, evidence_texts: list[str]) -> float:
    """忠实度代理：答案 tokens 中能被证据覆盖的比例（0~1）。token 免分词近似。

    说明：这是确定性代理指标，便于离线 CI；需标注为『参考值』，权威评测用 RAGAS。
    """
    a_toks = _token_set(answer)
    if not a_toks:
        return 0.0
    e_toks: set[str] = set()
    for t in evidence_texts:
        e_toks |= _token_set(t)
    covered = len(a_toks & e_toks)
    return covered / len(a_toks) if len(a_toks) else 0.0


def citation_support(answer: str, evidence_texts: list[str]) -> float:
    """引用支撑：答案文本中实质引用了证据内容的占比（同样为确定性代理）。"""
    return faithfulness_proxy(answer, evidence_texts)


# ---------- 聚合 ----------

@dataclass
class RetrievalReport:
    hit_at_k: list[bool] = field(default_factory=list)
    recall_at_k: list[float] = field(default_factory=list)
    mrr_list: list[float] = field(default_factory=list)

    def summarize(self, k: int = 10) -> dict[str, float]:
        n = max(len(self.hit_at_k), 1)
        return {
            f"Hit@{k}": sum(self.hit_at_k) / n,
            f"Recall@{k}": sum(self.recall_at_k) / n,
            "MRR": sum(self.mrr_list) / n,
        }


@dataclass
class GenerationReport:
    faithfulness: list[float] = field(default_factory=list)
    citation_support: list[float] = field(default_factory=list)
    refused: int = 0
    total: int = 0

    def summarize(self) -> dict[str, float]:
        n = max(self.total, 1)
        return {
            "faithfulness(proxy)": sum(self.faithfulness) / n,
            "citation_support(proxy)": sum(self.citation_support) / n,
            "refusal_rate": self.refused / n,
        }