"""评测：检索层(Hit@K/Recall@K/MRR) 与 生成层(忠实度/引用支撑) 量化。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..models import Evidence

# ---------- 检索层指标 ----------

def retrieval_identifier(
    evidences: list[Evidence], *, by: Literal["chunk", "document"] = "chunk"
) -> list[str]:
    """返回按排名去重的 chunk/document 标识，保留首次出现的排序。"""
    if by not in {"chunk", "document"}:
        raise ValueError("by must be chunk or document")
    ids: list[str] = []
    seen: set[str] = set()
    for evidence in evidences:
        identifier = evidence.chunk.id if by == "chunk" else evidence.chunk.doc_id
        if identifier not in seen:
            ids.append(identifier)
            seen.add(identifier)
    return ids


def hit_at_k(
    evidences: list[Evidence], gold_ids: set[str], k: int | None = None,
    *, by: Literal["chunk", "document"] = "chunk",
) -> bool:
    hits = evidences if k is None else evidences[:k]
    return bool(set(retrieval_identifier(hits, by=by)) & gold_ids)


def recall_at_k(
    evidences: list[Evidence], gold_ids: set[str], k: int | None = None,
    *, by: Literal["chunk", "document"] = "chunk",
) -> float:
    if not gold_ids:
        return 0.0
    hits = evidences if k is None else evidences[:k]
    hit_ids = set(retrieval_identifier(hits, by=by))
    return len(hit_ids & gold_ids) / len(gold_ids)


def mrr(
    evidences: list[Evidence], gold_ids: set[str],
    *, by: Literal["chunk", "document"] = "chunk",
) -> float:
    for rank, identifier in enumerate(retrieval_identifier(evidences, by=by), start=1):
        if identifier in gold_ids:
            return 1.0 / rank
    return 0.0


def citation_validity(valid: int, total: int, *, ran: bool) -> float | None:
    """合法引用率；未运行返回 None，零引用运行返回 0 而非伪造 100%。"""
    if not ran:
        return None
    if total <= 0:
        return 0.0
    return max(0, valid) / total


def refusal_confusion(rows: list[tuple[bool, bool]]) -> dict[str, int]:
    """按 (answerable, predicted_refused) 统计拒答混淆矩阵。"""
    matrix = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    for answerable, refused in rows:
        if not answerable and refused:
            matrix["true_positive"] += 1
        elif answerable and not refused:
            matrix["true_negative"] += 1
        elif answerable and refused:
            matrix["false_positive"] += 1
        else:
            matrix["false_negative"] += 1
    return matrix


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
