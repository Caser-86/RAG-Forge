"""Ollama HTTP client: keep protocol details and failure classification in one place."""
from __future__ import annotations

from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Base class for errors raised by the local Ollama service."""


class OllamaUnavailable(OllamaError):
    """The service cannot be reached or returned a server-side failure."""


class OllamaTimeout(OllamaError):
    """The service did not respond within the configured timeout."""


class OllamaModelNotFound(OllamaError):
    """The requested model is not installed in Ollama."""


class OllamaProtocolError(OllamaError):
    """Ollama returned an invalid or incomplete response."""


class OllamaClient:
    """Small synchronous client for the non-streaming Ollama REST protocol."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        *,
        connect_timeout: float = 5.0,
        generate_timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        timeout = httpx.Timeout(generate_timeout, connect=connect_timeout)
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)
        self._closed = False

    def health(self) -> bool:
        try:
            self.list_models()
        except OllamaError:
            return False
        return True

    def list_models(self) -> list[str]:
        payload = self._request_json("GET", "/api/tags")
        models = payload.get("models")
        if not isinstance(models, list):
            raise OllamaProtocolError("Ollama /api/tags response has no models list")

        names: list[str] = []
        for item in models:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise OllamaProtocolError("Ollama model entry has no name")
            name = item["name"].strip()
            if not name:
                raise OllamaProtocolError("Ollama returned an empty model name")
            if name not in names:
                names.append(name)
        return names

    def model_digest(self, model: str) -> str:
        """Return the provider revision for a model, including ``:latest`` aliases."""
        if not model.strip():
            raise OllamaProtocolError("Ollama model name cannot be empty")
        payload = self._request_json("GET", "/api/tags")
        models = payload.get("models")
        if not isinstance(models, list):
            raise OllamaProtocolError("Ollama /api/tags response has no models list")

        requested = model.strip()
        aliases = {requested}
        if ":" not in requested:
            aliases.add(f"{requested}:latest")
        for item in models:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise OllamaProtocolError("Ollama model entry has no name")
            if item["name"].strip() not in aliases:
                continue
            digest = item.get("digest")
            if not isinstance(digest, str) or not digest.strip():
                raise OllamaProtocolError(f"Ollama model {requested!r} has no digest")
            return digest.strip()
        raise OllamaModelNotFound(f"Ollama model not found: {requested}")

    def generate(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str:
        if stream:
            raise ValueError("Ollama streaming is not implemented")
        if not model.strip():
            raise OllamaProtocolError("Ollama model name cannot be empty")

        request_payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if options:
            request_payload["options"] = dict(options)
        payload = self._request_json(
            "POST",
            "/api/chat",
            json=request_payload,
        )
        message = payload.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaProtocolError("Ollama /api/chat response has no message.content")
        content = message["content"]
        if not content.strip():
            raise OllamaProtocolError("Ollama returned an empty answer")
        return content

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """Return raw embeddings from Ollama; normalization belongs to the embedder."""
        if not model.strip():
            raise OllamaProtocolError("Ollama model name cannot be empty")
        if not texts:
            return []

        payload = self._request_json(
            "POST",
            "/api/embed",
            json={"model": model, "input": texts},
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise OllamaProtocolError("Ollama /api/embed response has no embeddings list")
        rows: list[list[float]] = []
        for row in embeddings:
            if not isinstance(row, list):
                raise OllamaProtocolError("Ollama embedding row must be a list")
            rows.append(row)
        return rows

    def close(self) -> None:
        if self._closed:
            return
        self._client.close()
        self._closed = True

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.TimeoutException as exc:
            raise OllamaTimeout(f"Ollama request timed out: {path}") from exc
        except httpx.RequestError as exc:
            raise OllamaUnavailable(f"Ollama request failed: {path}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code == 404:
                raise OllamaModelNotFound(f"Ollama model or endpoint not found: {path}") from exc
            if response.status_code >= 500:
                raise OllamaUnavailable(f"Ollama server error: HTTP {response.status_code}") from exc
            raise OllamaProtocolError(f"Ollama rejected request: HTTP {response.status_code}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaProtocolError("Ollama response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise OllamaProtocolError("Ollama response must be a JSON object")
        return payload
