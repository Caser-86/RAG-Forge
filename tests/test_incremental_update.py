from __future__ import annotations

from dataclasses import dataclass, field

from ragforge.knowledge_manifest import IncrementalUpdater, KnowledgeItem, KnowledgeManifest


@dataclass
class FakeIndexer:
    calls: list[tuple[str, int]] = field(default_factory=list)
    indexed: dict[tuple[str, int], int] = field(default_factory=dict)
    fail_urls: set[str] = field(default_factory=set)

    def index_document(self, document):
        if document.source_url in self.fail_urls:
            raise RuntimeError("embedding failed")
        key = (document.id, document.version)
        self.calls.append(key)
        self.indexed[key] = len(document.text)
        return 1

    def has_indexed(self, doc_id: str, version: int) -> bool:
        return (doc_id, version) in self.indexed

    def cleanup_version(self, doc_id: str, version: int) -> None:
        self.indexed.pop((doc_id, version), None)


def _item(url: str, text: str, content_hash: str, source_id: str = "docs") -> KnowledgeItem:
    return KnowledgeItem(
        url=url,
        source_id=source_id,
        title=url.rsplit("/", 1)[-1],
        text=text,
        content_hash=content_hash,
        retrieved_at="2026-09-11T00:00:00Z",
    )


def test_second_unchanged_run_does_not_reindex_and_update_only_touches_changed_doc(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    indexer = FakeIndexer()
    updater = IncrementalUpdater(manifest, indexer, index_identity="identity-a")
    first = [_item("https://example.test/a", "A", "ha"), _item("https://example.test/b", "B", "hb")]

    assert updater.update(first)["added"] == 2
    assert updater.update(first)["unchanged"] == 2
    changed = [_item("https://example.test/a", "A2", "ha2"), first[1]]
    result = updater.update(changed)

    assert result["updated"] == 1
    assert result["unchanged"] == 1
    assert len(indexer.calls) == 3


def test_failed_update_keeps_previous_index_and_recovery_cleans_partial_version(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    indexer = FakeIndexer()
    updater = IncrementalUpdater(manifest, indexer, index_identity="identity-a")
    item = _item("https://example.test/a", "A", "ha")
    updater.update([item])

    indexer.fail_urls.add(item.url)
    result = updater.update([_item(item.url, "A2", "ha2")])
    row = manifest.get_document_by_url(item.url)
    assert result["failed"] == 1
    assert row["status"] == "failed"
    assert row["indexed_version"] == 1
    assert indexer.has_indexed(row["doc_id"], 1)

    # A job left in indexing is treated as an interrupted candidate and removed,
    # while the previously indexed version remains available.
    job_id = manifest.create_job(row["doc_id"], 2)
    manifest.set_job_phase(job_id, "indexing")
    indexer.indexed[(row["doc_id"], 2)] = 99
    updater.recover_incomplete()
    assert not indexer.has_indexed(row["doc_id"], 2)
    assert indexer.has_indexed(row["doc_id"], 1)


def test_same_hash_from_second_url_keeps_provenance_alias_without_second_embedding(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    indexer = FakeIndexer()
    updater = IncrementalUpdater(manifest, indexer, index_identity="identity-a")
    first = _item("https://example.test/a", "same", "same-hash")
    mirror = _item("https://mirror.test/a", "same", "same-hash", source_id="mirror")

    result = updater.update([first, mirror])

    assert result["added"] == 1
    assert result["skipped"] == 1
    first_row = manifest.get_document_by_url(first.url)
    assert manifest.aliases_for(first_row["doc_id"])[0]["alias_url"] == mirror.url
    assert len(indexer.calls) == 1


def test_changed_index_identity_reindexes_even_when_content_is_unchanged(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    indexer = FakeIndexer()
    item = _item("https://example.test/a", "same", "same-hash")

    assert IncrementalUpdater(manifest, indexer, index_identity="identity-a").update([item])["added"] == 1
    result = IncrementalUpdater(manifest, indexer, index_identity="identity-b").update([item])

    assert result["updated"] == 1
    assert result["unchanged"] == 0
    assert len(indexer.calls) == 2


def test_incomplete_source_enumeration_does_not_mark_missing_document_inactive(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    indexer = FakeIndexer()
    item = _item("https://example.test/a", "A", "ha")
    updater = IncrementalUpdater(manifest, indexer, index_identity="identity-a")
    updater.update([item], source_completeness={"docs": True})

    result = updater.update([], source_completeness={"docs": False})

    assert result["inactive"] == 0
    assert manifest.get_document_by_url(item.url)["active"] == 1
