import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-ollama",
        action="store_true",
        default=False,
        help="run integration tests against the local Ollama service",
    )


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """让测试不受根目录 .env 或调用环境影响，禁止意外访问外部服务。"""
    for key in tuple(os.environ):
        if key.startswith("RAG_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RAG_VECTOR_STORE", "in_memory")
    monkeypatch.setenv("RAG_EMBEDDER_BACKEND", "deterministic")
    monkeypatch.setenv("RAG_LLM_API_KEY", "")
    monkeypatch.setenv("RAG_USE_RERANK", "false")

    from ragforge.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
