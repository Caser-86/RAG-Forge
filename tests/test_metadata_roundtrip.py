from ragforge.models import Chunk
from ragforge.vectorstore import _chunk_from_payload, _chunk_to_payload


def test_chunk_payload_roundtrip_preserves_new_metadata_fields():
    chunk = Chunk(
        id="c1",
        doc_id="d1",
        title="中文标题",
        text="正文",
        source="来源",
        source_url="https://example.test/doc",
        heading_path=["父级", "子级"],
        chunk_index=3,
        meta={"version": 2, "active": True},
    )

    restored = _chunk_from_payload(_chunk_to_payload(chunk))

    assert restored == chunk


def test_old_or_empty_payload_uses_backward_compatible_defaults():
    old = _chunk_from_payload(
        {"id": "c-old", "doc_id": "d-old", "title": "old", "text": "text"}
    )
    empty = _chunk_from_payload({}, fallback_id="fallback")

    assert old.source_url is None
    assert old.heading_path == []
    assert old.chunk_index == 0
    assert empty.id == "fallback"
    assert empty.doc_id == ""
    assert empty.text == ""
