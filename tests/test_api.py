import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from ragforge.api import main as api
from ragforge.models import Chunk


def test_ingest_request_requires_at_least_one_path():
    with pytest.raises(ValidationError):
        api.IngestRequest(paths=[])


def test_query_requests_bound_query_length():
    with pytest.raises(ValidationError):
        api.AskRequest(query="x" * 4001)


def test_resolve_ingest_paths_accepts_files_inside_root(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    document = root / "note.txt"
    document.write_text("safe", encoding="utf-8")

    resolved = api._resolve_ingest_paths(["note.txt"], root)

    assert resolved == [document.resolve()]


def test_resolve_ingest_paths_rejects_outside_and_missing_paths(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")

    with pytest.raises(HTTPException) as outside:
        api._resolve_ingest_paths(["../secret.txt"], root)
    assert outside.value.status_code == 400

    with pytest.raises(HTTPException) as missing:
        api._resolve_ingest_paths(["missing.txt"], root)
    assert missing.value.status_code == 400


def test_resolve_ingest_paths_rejects_oversized_files(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    document = root / "large.txt"
    document.write_text("12345", encoding="utf-8")

    with pytest.raises(HTTPException) as oversized:
        api._resolve_ingest_paths(["large.txt"], root, max_bytes=4)
    assert oversized.value.status_code == 413


def test_resolve_ingest_paths_rejects_oversized_batch(tmp_path):
    root = tmp_path / "docs"
    root.mkdir()
    (root / "one.txt").write_text("12345", encoding="utf-8")
    (root / "two.txt").write_text("67890", encoding="utf-8")

    with pytest.raises(HTTPException) as oversized:
        api._resolve_ingest_paths(["one.txt", "two.txt"], root, max_total_bytes=9)
    assert oversized.value.status_code == 413


class _KnowledgeStore:
    def list_chunks(self):
        return [
            Chunk(
                id="chunk-1",
                doc_id="doc-1",
                title="知识文档",
                text="这是可定位的证据片段。",
                source="docs/guide.md",
                source_url="https://example.test/guide",
                heading_path=["Guide"],
                chunk_index=0,
            )
        ]


class _KnowledgeEngine:
    store = _KnowledgeStore()

    def get_trace(self, trace_id):
        if trace_id != "trace-export":
            return None
        return {
            "trace_id": trace_id,
            "original_query": "这个结论是什么？",
            "answer": "结论来自资料。[1]",
            "model": "offline",
            "refused": False,
            "refusal_reason": None,
            "citations": [{
                "index": 1,
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "title": "知识文档",
                "url": "https://example.test/guide",
                "snippet": "这是可定位的证据片段。",
            }],
            "final_context": "secret context that must not be exported",
            "raw_output": "secret raw output that must not be exported",
        }


def test_knowledge_and_source_endpoints_only_expose_stored_document_ids(monkeypatch):
    previous = api.engine
    monkeypatch.setattr(api, "engine", _KnowledgeEngine())
    try:
        knowledge = api.knowledge()
        assert knowledge["knowledge_state"] == "ready"
        assert knowledge["documents"][0]["document_id"] == "doc-1"

        source = api.source_preview(document_id="doc-1", limit=10)
        assert source["chunks"][0]["chunk_id"] == "chunk-1"
        assert source["chunks"][0]["snippet"] == "这是可定位的证据片段。"

        with pytest.raises(HTTPException) as missing:
            api.source_preview(document_id="C:/not-a-stored-path", limit=10)
        assert missing.value.status_code == 404
    finally:
        monkeypatch.setattr(api, "engine", previous)


def test_trace_export_excludes_raw_debug_context_and_secrets(monkeypatch):
    previous = api.engine
    monkeypatch.setattr(api, "engine", _KnowledgeEngine())
    try:
        exported_json = api.export_trace("trace-export", "json")
        assert exported_json.media_type == "application/json"
        assert "secret context" not in exported_json.body.decode("utf-8")
        assert "secret raw output" not in exported_json.body.decode("utf-8")
        assert "结论来自资料。[1]" in exported_json.body.decode("utf-8")

        exported_markdown = api.export_trace("trace-export", "markdown")
        assert exported_markdown.media_type == "text/markdown"
        assert "# RAG-Forge 问答结果" in exported_markdown.body.decode("utf-8")
        assert "secret raw output" not in exported_markdown.body.decode("utf-8")

        with pytest.raises(HTTPException) as missing:
            api.export_trace("missing", "json")
        assert missing.value.status_code == 404
    finally:
        monkeypatch.setattr(api, "engine", previous)
