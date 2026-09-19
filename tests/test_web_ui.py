from pathlib import Path

from fastapi.testclient import TestClient

from ragforge.api import main as api
from ragforge.config import Settings


STATIC_DIR = Path(api.__file__).parent / "static"


def test_web_assets_are_packaged_as_a_small_no_build_ui():
    assert all((STATIC_DIR / name).is_file() for name in ("index.html", "app.css", "app.js", "favicon.svg"))
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="view-chat"' in html
    assert 'id="view-debug"' in html
    assert 'id="view-settings"' in html
    assert 'id="rewriteToggle"' in html
    assert "textContent" in javascript
    assert "retryButton" in javascript
    assert "resetRequestState" in javascript
    assert "compositionstart" in javascript
    assert "boundedHistory" in javascript
    assert "saveButton" in html
    assert "/api/export/" in javascript
    assert "事实支撑未人工审核" in javascript
    assert "localStorage" not in javascript
    assert "javascript:" in javascript


def test_root_and_static_paths_are_served(monkeypatch):
    settings = Settings(_env_file=None, api_key="", rate_limit_per_minute=1000)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        root = client.get("/")
        css = client.get("/static/app.css")
        javascript = client.get("/static/app.js")

    assert root.status_code == 200
    assert "RAG" in root.text
    assert css.status_code == 200
    assert javascript.status_code == 200


def test_web_ui_does_not_expose_api_key_in_markup_or_url():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "X-API-Key" not in html
    assert "?api_key" not in javascript
    assert "localStorage" not in javascript


def test_non_ollama_backends_still_expose_allowlisted_generation_models():
    settings = Settings(
        _env_file=None,
        generation_backend="offline",
        allowed_generation_models=["gemma3:4b"],
    )

    catalog = api._model_catalog(settings, [])

    assert catalog["generation"] == ["gemma3:4b"]


def test_web_root_remains_open_when_api_data_routes_require_a_key(monkeypatch):
    settings = Settings(_env_file=None, api_key="demo-key", rate_limit_per_minute=1000)
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    api.request_limiter = api.RateLimiter()
    with TestClient(api.app) as client:
        root = client.get("/")
        health_without_key = client.get("/api/health")

    assert root.status_code == 200
    assert health_without_key.status_code == 401
