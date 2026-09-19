from ragforge.ingest import Chunker
from ragforge.models import Document


def _doc(text: str, *, version: int = 3) -> Document:
    return Document(id="doc-1", title="Guide", text=text, version=version)


def test_heading_chunker_tracks_nested_and_jump_heading_paths_without_code_false_positives():
    doc = _doc(
        "# Root\n\nIntro.\n\n### Jump\n\nDetails.\n\n"
        "```python\n# not a heading\nvalue = 1\n```\n"
    )

    chunks = Chunker(size=200, overlap=20).chunk(doc)

    assert any(chunk.heading_path == ["Root"] for chunk in chunks)
    assert any(chunk.heading_path == ["Root", "Jump"] for chunk in chunks)
    assert all("not a heading" not in chunk.heading_path for chunk in chunks)
    assert any("# not a heading" in chunk.text for chunk in chunks)


def test_heading_chunker_splits_long_body_and_keeps_overlap_inside_one_section():
    doc = _doc(
        "# First\n\n" + "first " * 80 + "\n\n"
        "# Second\n\n" + "second " * 80
    )

    chunks = Chunker(size=120, overlap=20).chunk(doc)
    first = [chunk for chunk in chunks if chunk.heading_path == ["First"]]
    second = [chunk for chunk in chunks if chunk.heading_path == ["Second"]]

    assert len(first) > 1
    assert len(second) > 1
    assert all("second" not in chunk.text for chunk in first)
    assert all("first" not in chunk.text for chunk in second)
    assert any(first[i].text[-20:].strip() in first[i + 1].text for i in range(len(first) - 1))


def test_heading_chunk_ids_are_stable_and_include_version_and_chunk_config():
    doc = _doc("# Root\n\nA short paragraph.")
    chunker = Chunker(size=200, overlap=20)

    first = chunker.chunk(doc)
    second = chunker.chunk(doc)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert all("doc-1::v3::heading_chars-200-20::c" in chunk.id for chunk in first)


def test_heading_chunker_filters_blank_heading_only_document_and_preserves_body_coverage():
    doc = _doc("# Empty\n\n## Child\n\nUseful body here.")

    chunks = Chunker(size=2200, overlap=200).chunk(doc)

    assert len(chunks) == 1
    assert chunks[0].heading_path == ["Empty", "Child"]
    assert "Useful body here." in chunks[0].text


def test_heading_chunker_preserves_every_character_when_overlap_is_added():
    text = "".join(chr(0x4E00 + index) for index in range(300))
    chunks = Chunker(size=100, overlap=20).chunk(_doc(text))

    assert all(any(character in chunk.text for chunk in chunks) for character in text)
