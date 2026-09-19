import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ragforge.api import main as api
from ragforge.api.main import validate_api_key
from ragforge.config import Settings
from ragforge.api.security import RateLimiter


class _Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_configured_api_key_rejects_missing_or_wrong_key():
    with pytest.raises(HTTPException) as missing:
        validate_api_key(None, "expected")
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as wrong:
        validate_api_key("wrong", "expected")
    assert wrong.value.status_code == 401


def test_api_key_validation_is_optional_when_not_configured():
    validate_api_key(None, "")


def test_api_key_validation_handles_unicode_and_non_string_values():
    validate_api_key("密钥", "密钥")

    with pytest.raises(HTTPException) as invalid_type:
        validate_api_key(b"wrong", "expected")  # type: ignore[arg-type]
    assert invalid_type.value.status_code == 401


def test_rate_limiter_blocks_until_window_expires():
    clock = _Clock()
    limiter = RateLimiter(clock=clock)

    assert limiter.check("client", limit=2) == 0
    assert limiter.check("client", limit=2) == 0
    assert limiter.check("client", limit=2) > 0

    clock.value = 60.0
    assert limiter.check("client", limit=2) == 0


def test_http_body_limit_and_security_headers_are_enforced(monkeypatch):
    settings = Settings(
        _env_file=None,
        vector_store="in_memory",
        embedder_backend="deterministic",
        generation_backend="offline",
        max_request_body_bytes=128,
        api_key="",
        rate_limit_per_minute=1000,
    )
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.request_limiter = RateLimiter()
    with TestClient(api.app) as client:
        too_large = client.post("/ingest", content=b"x" * 129)
        headers = client.get("/")

    assert too_large.status_code == 413
    assert headers.headers["x-content-type-options"] == "nosniff"
    assert headers.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in headers.headers["content-security-policy"]


def test_untrusted_host_is_rejected(monkeypatch):
    settings = Settings(_env_file=None, api_key="", rate_limit_per_minute=1000)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.request_limiter = RateLimiter()
    with TestClient(api.app) as client:
        response = client.get("/", headers={"host": "evil.example"})

    assert response.status_code == 400
