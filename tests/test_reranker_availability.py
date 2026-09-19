from ragforge.retriever.rerank import Reranker


def test_disabled_reranker_reports_reason_without_loading_model():
    reranker = Reranker("missing-model", enabled=False)

    assert reranker.status() == {"available": False, "enabled": False, "reason": "disabled"}
    assert reranker.model is None


def test_missing_local_reranker_reports_unavailable_without_download(tmp_path):
    reranker = Reranker(str(tmp_path / "not-installed"), enabled=True)

    status = reranker.status()

    assert status["available"] is False
    assert status["enabled"] is True
    assert "cache" in status["reason"]
    assert reranker.model is None


def test_missing_reranker_package_and_cache_reports_both_reasons(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ragforge.retriever.rerank.importlib.util.find_spec",
        lambda _name: None,
    )
    reranker = Reranker(str(tmp_path / "not-installed"), enabled=True)

    status = reranker.status()

    assert status["available"] is False
    assert "cache" in status["reason"]
    assert "package" in status["reason"]
