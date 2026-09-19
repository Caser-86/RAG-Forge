"""重排：CrossEncoder（bge-reranker）对融合候选精排。"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from ..models import Chunk


class RerankerUnavailable(RuntimeError):
    """Requested reranking but the optional local model is not ready."""


class Reranker:
    def __init__(self, model_name: str, enabled: bool = True):
        self.model_name = model_name
        self.enabled = enabled
        self.model = None
        self._availability: dict[str, object] | None = None

    def status(self) -> dict[str, object]:
        if not self.enabled:
            return {"available": False, "enabled": False, "reason": "disabled"}
        if self.model is not None:
            return {"available": True, "enabled": True, "reason": None}
        if self._availability is not None:
            return self._availability
        model_cached = self._model_is_cached()
        package_available = importlib.util.find_spec("sentence_transformers") is not None
        if not model_cached:
            reason = "reranker model cache is not available"
            if not package_available:
                reason += "; sentence_transformers package is not installed"
            self._availability = {
                "available": False,
                "enabled": True,
                "reason": reason,
            }
            return self._availability
        if not package_available:
            self._availability = {
                "available": False,
                "enabled": True,
                "reason": "sentence_transformers package is not installed",
            }
            return self._availability
        self._availability = {"available": True, "enabled": True, "reason": None}
        return self._availability

    def _model_is_cached(self) -> bool:
        model_path = Path(self.model_name).expanduser()
        if model_path.exists():
            return True
        if "/" not in self.model_name:
            return False
        repo = "models--" + self.model_name.replace("/", "--")
        roots = [
            Path(os.environ.get("SENTENCE_TRANSFORMERS_HOME", "")),
            Path(os.environ.get("HF_HOME", "")) / "hub",
            Path.home() / ".cache" / "huggingface" / "hub",
        ]
        return any((root / repo).exists() for root in roots if str(root) not in {"", "."})

    def _ensure_loaded(self):
        status = self.status()
        if not status["available"]:
            raise RerankerUnavailable(str(status["reason"]))
        if self.model is None:
            from sentence_transformers import CrossEncoder

            try:
                self.model = CrossEncoder(self.model_name)
            except Exception as exc:  # noqa: BLE001 - report optional model state
                self._availability = {
                    "available": False,
                    "enabled": True,
                    "reason": f"reranker model failed to load: {type(exc).__name__}",
                }
                raise RerankerUnavailable(str(self._availability["reason"])) from exc
        return self.model

    def rerank(self, query: str, candidates: list[tuple[Chunk, float]], top_k: int) -> list[tuple[Chunk, float]]:
        if not candidates or top_k <= 0:
            return candidates[:top_k]
        model = self._ensure_loaded()
        pairs = [(query, c.text) for c, _ in candidates]
        scores = model.predict(pairs, show_progress_bar=False)
        merged = sorted(zip(candidates, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [(c, float(s)) for (c, _), s in merged[:top_k]]

    def score(self, query: str, chunk: Chunk) -> float:
        model = self._ensure_loaded()
        return float(model.predict([(query, chunk.text)], show_progress_bar=False)[0])
