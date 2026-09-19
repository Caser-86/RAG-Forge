"""可选 Query Rewrite：只生成检索查询，失败时安全回退原问题。"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass

from .config import Settings
from .ollama_client import (
    OllamaClient,
    OllamaModelNotFound,
    OllamaProtocolError,
    OllamaTimeout,
    OllamaUnavailable,
)


@dataclass(frozen=True)
class RewriteResult:
    query: str
    fallback: bool
    reason: str | None
    elapsed_ms: float


class QueryRewriter:
    _SYSTEM_PROMPT = (
        "你是检索查询改写器。只输出一行、单条检索查询，不回答问题，不解释过程，"
        "必须保留原问题中的产品名、错误码、版本号和数字约束，不得添加原文没有的新事实。"
    )

    def __init__(self, settings: Settings, client: OllamaClient | None = None):
        self.settings = settings
        self.enabled = settings.rewrite_enabled
        self.model = settings.rewrite_model
        self.max_chars = settings.rewrite_max_chars
        self.max_history_messages = settings.rewrite_history_max_messages
        self.client = client or OllamaClient(
            settings.ollama_base_url,
            connect_timeout=settings.ollama_connect_timeout,
            generate_timeout=settings.ollama_generate_timeout,
        )
        self.last_result = RewriteResult("", True, "disabled", 0.0)

    def rewrite(
        self,
        query: str,
        history: list[dict[str, str]] | None,
        *,
        enabled: bool | None = None,
    ) -> str:
        should_run = self.enabled if enabled is None else enabled
        if not should_run:
            self.last_result = RewriteResult(query, True, "disabled", 0.0)
            return query

        start = time.monotonic()
        try:
            response = self.client.generate(
                self.model,
                self._messages(query, history or []),
                stream=False,
            )
        except OllamaTimeout:
            return self._fallback(query, "utility_timeout", start)
        except (OllamaUnavailable, OllamaModelNotFound):
            return self._fallback(query, "utility_unavailable", start)
        except OllamaProtocolError:
            return self._fallback(query, "utility_protocol_error", start)
        except Exception:  # noqa: BLE001 - utility failure must not break retrieval
            return self._fallback(query, "utility_error", start)

        candidate = str(response or "").strip()
        if not candidate:
            return self._fallback(query, "empty_output", start)
        if len(candidate) > self.max_chars:
            return self._fallback(query, "too_long", start)
        if "<think" in candidate.casefold() or "</think>" in candidate.casefold():
            return self._fallback(query, "think_output", start)
        if "<" in candidate or ">" in candidate or candidate.startswith(("{", "[")):
            return self._fallback(query, "structured_output", start)
        if "\n" in candidate or "\r" in candidate:
            return self._fallback(query, "multi_line_output", start)
        prompt_leak_markers = (
            "原问题中",
            "关键限定",
            "无法确认",
            "请提供",
            "信息不足",
            "不确定",
        )
        if any(marker in candidate for marker in prompt_leak_markers):
            return self._fallback(query, "prompt_leak", start)
        original_numbers = self._numeric_tokens(query)
        if self._numeric_tokens(candidate) - original_numbers:
            return self._fallback(query, "new_numeric_fact", start)
        if self._critical_tokens(query) - self._casefold_tokens(candidate):
            return self._fallback(query, "critical_token_dropped", start)
        self.last_result = RewriteResult(
            candidate,
            False,
            None,
            (time.monotonic() - start) * 1000,
        )
        return candidate

    def _messages(self, query: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
        bounded = history[-self.max_history_messages :]
        history_lines: list[str] = []
        for item in bounded:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", ""))
            content = str(item.get("content", ""))[: self.max_chars]
            if role not in {"user", "assistant"} or not content:
                continue
            history_lines.append(f"{role}: {html.escape(content, quote=True)}")
        history_text = "\n".join(history_lines) or "（无历史）"
        safe_query = html.escape(query or "", quote=True)
        user = f"<history>\n{history_text}\n</history>\n<query>\n{safe_query}\n</query>"
        return [
            {"role": "system", "content": self._SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    def _fallback(self, query: str, reason: str, start: float) -> str:
        self.last_result = RewriteResult(
            query,
            True,
            reason,
            (time.monotonic() - start) * 1000,
        )
        return query

    @staticmethod
    def _casefold_tokens(text: str) -> set[str]:
        return {token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", text)}

    @staticmethod
    def _numeric_tokens(text: str) -> set[str]:
        return {
            token.casefold()
            for token in re.findall(r"\d+(?:[.,]\d+)?", text)
        }

    @classmethod
    def _critical_tokens(cls, query: str) -> set[str]:
        patterns = (
            r"\b[A-Za-z]{1,12}[-_]\d{2,}\b",  # E9001 / HTTP_429
            r"\b[A-Za-z]{1,12}\d{2,}\b",  # BGE-M3 / E9001 variants
            r"\bv\d+(?:\.\d+)*\b",  # v1 / v2.1
            r"\b[A-Za-z][A-Za-z0-9.-]*:[A-Za-z0-9._-]+\b",  # gemma3:4b
            r"\b[A-Za-z]{2,}-[A-Za-z0-9]{2,}\b",  # product names
            r"\b\d+(?:[.,]\d+)?\b",  # explicit numeric constraints
        )
        tokens: set[str] = set()
        for pattern in patterns:
            tokens.update(cls._casefold_tokens(" ".join(re.findall(pattern, query))))
        return tokens

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()
