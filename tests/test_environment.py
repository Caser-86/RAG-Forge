import importlib
from pathlib import Path

import pytest

from ragforge.config import get_settings
from scripts import check_environment as environment
from scripts.check_environment import REQUIRED_MODELS, check_environment


def _healthy_transport(_: str, __: float) -> dict:
    return {
        "models": [
            {"name": "bge-m3:latest"},
            {"name": "gemma3:4b"},
            {"name": "gemma4:e4b"},
            {"name": "qwen3:0.6b"},
        ]
    }


def test_environment_report_is_stable_when_all_requirements_are_available(tmp_path: Path):
    report = check_environment(
        "http://127.0.0.1:11434",
        tmp_path / "data",
        fetch_json=_healthy_transport,
    )

    assert report["schema_version"] == 1
    assert report["ok"] is True
    assert report["ollama"]["ok"] is True
    assert report["missing_models"] == []
    assert report["data"]["ok"] is True
    assert Path(report["data"]["path"]).is_dir()


def test_environment_report_describes_runtime_profile_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_VECTOR_STORE", "in_memory")
    monkeypatch.setenv("RAG_EMBEDDER_BACKEND", "deterministic")
    monkeypatch.setenv("RAG_GENERATION_BACKEND", "offline")
    monkeypatch.setenv("RAG_INDEX_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    monkeypatch.setenv("RAG_QDRANT_COLLECTION", "doctor-test")
    monkeypatch.setenv("RAG_API_KEY", "not-for-output")

    report = check_environment(
        required_models=(),
        data_dir=tmp_path / "data",
        fetch_json=lambda _url, _timeout: {"models": []},
    )

    runtime = report["runtime"]
    assert runtime["vector_store"] == "in_memory"
    assert runtime["embedder_backend"] == "deterministic"
    assert runtime["generation_backend"] == "offline"
    assert runtime["qdrant_collection"] == "doctor-test"
    assert runtime["indexed_chunks"] == 0
    assert runtime["knowledge_state"] == "empty"
    assert "not-for-output" not in str(report)


def test_environment_report_lists_all_models_when_ollama_is_offline(tmp_path: Path):
    def offline_transport(_: str, __: float) -> dict:
        raise ConnectionError("offline")

    report = check_environment(
        "http://127.0.0.1:11434",
        tmp_path / "data",
        fetch_json=offline_transport,
    )

    assert report["ok"] is False
    assert report["ollama"]["ok"] is False
    assert report["missing_models"] == list(REQUIRED_MODELS)
    assert report["ollama"]["error"]["code"] == "connection_error"


def test_environment_report_handles_timeout_and_invalid_payload(tmp_path: Path):
    def timeout_transport(_: str, __: float) -> dict:
        raise TimeoutError("timeout")

    timeout = check_environment(
        "http://127.0.0.1:11434",
        tmp_path / "timeout",
        fetch_json=timeout_transport,
    )
    assert timeout["ollama"]["error"]["code"] == "timeout"

    invalid = check_environment(
        "http://127.0.0.1:11434",
        tmp_path / "invalid",
        fetch_json=lambda _url, _timeout: {"models": "not-a-list"},
    )
    assert invalid["ollama"]["error"]["code"] == "invalid_response"


def test_environment_fetch_rejects_non_http_urls():
    with pytest.raises(ValueError, match="http or https"):
        environment._fetch_json("file:///tmp/ragforge-secret.json", 1.0)


def test_environment_report_marks_missing_models(tmp_path: Path):
    report = check_environment(
        "http://127.0.0.1:11434",
        tmp_path / "data",
        fetch_json=lambda _url, _timeout: {"models": [{"name": "gemma3:4b"}]},
    )

    assert report["ok"] is False
    assert report["missing_models"] == [
        "bge-m3",
        "gemma4:e4b",
        "qwen3:0.6b",
    ]


def test_package_import_failure_is_reported_without_crashing(monkeypatch):
    def broken_import(_: str):
        raise RuntimeError("broken package")

    monkeypatch.setattr(importlib, "import_module", broken_import)

    report = environment._check_package()

    assert report["ok"] is False
    assert report["error"]["code"] == "import_error"


def test_environment_report_marks_data_path_that_is_not_a_directory(tmp_path: Path):
    data_path = tmp_path / "data-file"
    data_path.write_text("not a directory", encoding="utf-8")

    report = check_environment(
        required_models=(),
        data_dir=data_path,
        fetch_json=lambda _url, _timeout: {"models": []},
    )

    assert report["ok"] is False
    assert report["data"]["error"]["code"] == "not_writable"


def test_json_cli_returns_zero_for_a_healthy_report(monkeypatch, capsys, tmp_path: Path):
    healthy = {
        "schema_version": 1,
        "python": {"ok": True, "version": "3.14.6", "executable": "python"},
        "package": {"ok": True, "error": None},
        "ollama": {"ok": True, "url": "http://127.0.0.1:11434", "models": [], "error": None},
        "required_models": [],
        "missing_models": [],
        "data": {"ok": True, "path": str(tmp_path), "error": None},
        "ok": True,
    }
    monkeypatch.setattr(environment, "check_environment", lambda *_args: healthy)

    exit_code = environment.main(["--json", "--data-dir", str(tmp_path)])

    assert exit_code == 0
    assert '"schema_version": 1' in capsys.readouterr().out


def test_pytest_settings_cannot_select_external_services():
    settings = get_settings()

    assert settings.vector_store == "in_memory"
    assert settings.embedder_backend == "deterministic"
    assert settings.llm_api_key == ""
    assert settings.use_rerank is False
