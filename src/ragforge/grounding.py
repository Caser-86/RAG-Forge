"""证据上下文、引用解析与保守的回答落地校验。"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .models import Citation, Evidence


@dataclass(frozen=True)
class ContextBundle:
    """最终发送给模型的上下文及其一一对应的引用目录。"""

    context: str
    evidences: list[Evidence]
    citations: list[Citation]
    sent_texts: list[str]


@dataclass(frozen=True)
class CitationResolution:
    citations: list[Citation]
    citation_invalid: bool


@dataclass(frozen=True)
class GroundingResult:
    citations: list[Citation]
    citation_invalid: bool
    refused: bool
    refusal_reason: str | None
    citation_support_status: str
    grounded: bool


def _escaped(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def build_context_bundle(
    evidences: list[Evidence],
    *,
    max_chars: int = 12000,
) -> ContextBundle:
    """按顺序裁剪证据并在裁剪后编号，避免引用指向未发给模型的 chunk。"""
    limit = max(1, int(max_chars))
    selected: list[Evidence] = []
    blocks: list[str] = []
    sent_texts: list[str] = []
    used_chars = 0

    for evidence in evidences:
        chunk = evidence.chunk
        metadata = (
            f"source={_escaped(chunk.source)} "
            f"title={_escaped(chunk.title)} "
            f"url={_escaped(chunk.source_url)}"
        )
        prefix = f"[{len(selected) + 1}] {metadata}\n"
        text = _escaped(chunk.text)
        full = prefix + text
        separator = "\n\n" if blocks else ""
        remaining = limit - used_chars - len(separator)
        if remaining <= 0:
            break
        if len(full) > remaining:
            # 首个证据即使很长也保留可辨认的前缀，后续 chunk 不再挤占预算。
            if not selected:
                clipped = (prefix + text)[:remaining]
                selected.append(evidence)
                blocks.append(clipped)
                sent_encoded = clipped[len(prefix):] if len(clipped) > len(prefix) else ""
                sent_texts.append(html.unescape(sent_encoded))
            break
        selected.append(evidence)
        blocks.append(full)
        sent_texts.append(chunk.text)
        used_chars += len(full) + len(separator)

    citations = [
        Citation(
            index=index,
            document_id=evidence.chunk.doc_id,
            chunk_id=evidence.chunk.id,
            title=evidence.chunk.title,
            url=evidence.chunk.source_url,
            snippet=sent_texts[index - 1][:240],
        )
        for index, evidence in enumerate(selected, start=1)
    ]
    return ContextBundle(
        context="\n\n".join(blocks),
        evidences=selected,
        citations=citations,
        sent_texts=sent_texts,
    )


def extract_citation_indices(text: str) -> list[int]:
    """提取正文引用编号；代码块和 inline code 中的类似文本不算引用。"""
    without_fences = re.sub(r"```[\s\S]*?```", "", text or "")
    without_inline = re.sub(r"`[^`\n]*`", "", without_fences)
    return [int(value) for value in re.findall(r"\[(\d+)\]", without_inline)]


def resolve_citations(text: str, bundle: ContextBundle) -> CitationResolution:
    indices = extract_citation_indices(text)
    invalid = any(index < 1 or index > len(bundle.citations) for index in indices)
    resolved: list[Citation] = []
    seen: set[int] = set()
    for index in indices:
        if index < 1 or index > len(bundle.citations) or index in seen:
            continue
        seen.add(index)
        resolved.append(bundle.citations[index - 1])
    return CitationResolution(citations=resolved, citation_invalid=invalid)


def model_declares_insufficient(text: str) -> bool:
    lowered = (text or "").lower()
    markers = (
        "信息不足",
        "无法回答",
        "无法确定",
        "资料不足",
        "insufficient information",
        "not enough information",
        "cannot answer",
        "can't answer",
    )
    return any(marker in lowered for marker in markers)


def insufficient_support_reason(query: str, bundle: ContextBundle) -> str | None:
    """检查必须被证据覆盖的错误码、实体限定符和数值约束。

    普通词不做字面重叠要求，因此中文问题仍可由英文证据支持；仅对高风险、
    可明确识别的约束做保守检查。
    """
    query_text = query or ""
    evidence_text = "\n".join(bundle.sent_texts)
    critical = re.findall(
        r"\b[A-Z]{1,8}[-_]\d{2,}\b|\b[A-Z]{1,8}\d{2,}\b|\b\d+(?:[.,]\d+)?\b",
        query_text,
        flags=re.IGNORECASE,
    )
    critical.extend(re.findall(r"[\"'「『]([^\"'」』]+)[\"'」』]", query_text))
    missing = [token for token in critical if token.casefold() not in evidence_text.casefold()]
    return "insufficient_support" if missing else None


def ground_answer(
    text: str,
    bundle: ContextBundle,
    *,
    query: str = "",
) -> GroundingResult:
    """执行 v1 保守门禁；编号有效不等于句子已被事实验证。"""
    if not bundle.evidences:
        return GroundingResult([], False, True, "no_evidence", "unverified", False)
    resolution = resolve_citations(text, bundle)
    support_reason = insufficient_support_reason(query, bundle)
    if support_reason is not None:
        reason = support_reason
        refused = True
    elif model_declares_insufficient(text):
        reason = "model_declared_insufficient"
        refused = True
    elif resolution.citation_invalid:
        reason = "invalid_citation"
        refused = True
    elif not resolution.citations:
        reason = "no_valid_citation"
        refused = True
    else:
        reason = None
        refused = False
    return GroundingResult(
        citations=resolution.citations,
        citation_invalid=resolution.citation_invalid,
        refused=refused,
        refusal_reason=reason,
        citation_support_status="unverified",
        grounded=not refused,
    )


def normalized_rerank_score(evidence: Evidence) -> float | None:
    """只接受显式声明为 0..1 的分数，避免把 raw logit 当概率。"""
    score = evidence.rerank_score
    kind = evidence.score_kind.get("rerank", "")
    if score is None or kind not in {"normalized", "probability", "sigmoid_calibrated"}:
        return None
    if 0.0 <= score <= 1.0:
        return float(score)
    return None


def score_calibration_status(evidence: Evidence) -> dict[str, str]:
    """返回各检索分数的语义，不把排名或 raw 分数伪装成概率。"""
    status: dict[str, str] = {}
    if evidence.dense_score is not None:
        status["dense"] = "dense_cosine_uncalibrated"
    if evidence.sparse_score is not None:
        status["sparse"] = "bm25_raw_not_confidence"
    if evidence.fused_score is not None:
        status["fused"] = "rrf_rank_not_confidence"
    if evidence.rerank_score is not None:
        if normalized_rerank_score(evidence) is not None:
            status["rerank"] = "rerank_normalized_thresholdable"
        else:
            status["rerank"] = "rerank_raw_uncalibrated"
    return status
