"""生成：仅依据检索证据作答；证据不足时拒答（反幻觉设计点）。"""
from __future__ import annotations

from .config import Settings
from .models import Answer, Evidence
from .observability import get_logger, new_trace_id, timer

logger = get_logger()

_REFUSE_MSG = "信息不足：当前语料未能提供足够可靠的证据回答该问题，建议调整提问或补充相关文档。"


class _BaseGenerator:
    def refuse_threshold(self, evidences: list[Evidence]) -> bool:
        # 没有任何证据 → 必须拒答
        if not evidences:
            return True
        # 重排可用时：以重排/置信度分判断证据是否充分（真实反幻觉路径）
        rerank_scores = [e.rerank_score for e in evidences if e.rerank_score]
        if rerank_scores:
            return max(rerank_scores) < self.threshold
        # 无重排（离线/确定性演示态）：不强行按分数拒答，交由检索是否命中决定
        return False

    def build_context(self, evidences: list[Evidence]) -> str:
        blocks = []
        for i, e in enumerate(evidences, start=1):
            blocks.append(f"[{i}] 来源：{e.chunk.source}\n{e.chunk.text}")
        return "\n\n".join(blocks)


class LLMGenerator(_BaseGenerator):
    """OpenAI 兼容 LLM 生成，带引用。"""

    def __init__(self, settings: Settings):
        from openai import OpenAI

        self.threshold = settings.refuse_threshold
        self.client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "none")
        self.model = settings.llm_model

    def generate(self, query: str, evidences: list[Evidence], trace_id: str) -> Answer:
        if self.refuse_threshold(evidences):
            return Answer(answer=_REFUSE_MSG, refused=True, trace_id=trace_id,
                          evidences=evidences)
        context = self.build_context(evidences)
        system = (
            "你是一个严格基于给定资料作答的问答助手。只允许使用资料中的信息；"
            "若资料不足以回答问题，必须明确回答'信息不足'，不得编造。"
            "回答末尾用 [1][2] 等标注资料来源编号。"
        )
        user = f"资料：\n{context}\n\n问题：{query}"
        with timer("llm.generate", logger):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                max_tokens=512,
            )
        text = resp.choices[0].message.content or ""
        return Answer(answer=text, citations=self._citations(text), trace_id=trace_id,
                      evidences=evidences)

    @staticmethod
    def _citations(text: str) -> list[str]:
        import re

        return re.findall(r"\[\d+\]", text)


class OfflineGenerator(_BaseGenerator):
    """离线兜底：无 API key / 演示用。提取证据段落作为答案，标注为离线回声，不计入真实评测。"""

    def __init__(self, settings: Settings):
        self.threshold = settings.refuse_threshold

    def generate(self, query: str, evidences: list[Evidence], trace_id: str) -> Answer:
        if self.refuse_threshold(evidences):
            return Answer(answer=_REFUSE_MSG, refused=True, trace_id=trace_id, evidences=evidences)
        best = sorted(evidences, key=lambda e: e.rerank_score or e.fused_score, reverse=True)
        snippet = best[0].chunk.text[:300]
        answer = f"[离线回声，仅供检索演示] 最相关证据（{best[0].chunk.source}）：{snippet}"
        return Answer(answer=answer, citations=["[1]"], trace_id=trace_id, evidences=evidences)


def build_generator(settings: Settings) -> _BaseGenerator:
    if settings.llm_api_key:
        return LLMGenerator(settings)
    logger.warning("未配置 RAG__LLM_API_KEY，使用离线回声生成器（仅演示检索，不走真实生成/评测）")
    return OfflineGenerator(settings)