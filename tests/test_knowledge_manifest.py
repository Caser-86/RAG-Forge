from ragforge.knowledge_manifest import KnowledgeManifest, stable_doc_id


def test_stable_doc_id_uses_normalized_url():
    assert stable_doc_id("HTTPS://Example.test:443/a#part") == stable_doc_id("https://example.test/a")


def test_manifest_tracks_versions_jobs_runs_and_aliases(tmp_path):
    manifest = KnowledgeManifest(tmp_path / "knowledge.sqlite3")
    run_id = manifest.start_run()
    doc_id = stable_doc_id("https://example.test/a")

    manifest.save_document(
        doc_id=doc_id,
        url="https://example.test/a",
        source_id="docs",
        title="A",
        content_hash="hash-a",
        version=1,
        status="pending",
        retrieved_at="2026-09-11T00:00:00Z",
        last_seen_run=run_id,
    )
    job_id = manifest.create_job(doc_id, 1)
    manifest.set_job_phase(job_id, "indexing")
    manifest.mark_indexed(doc_id, indexed_identity="identity-a", indexed_version=1)
    manifest.set_job_phase(job_id, "indexed")
    manifest.record_alias("hash-a", doc_id, "https://mirror.test/a", "mirror", run_id)
    manifest.finish_run(run_id, {"added": 1})

    row = manifest.get_document(doc_id)
    assert row["status"] == "indexed"
    assert row["indexed_version"] == 1
    assert row["indexed_identity"] == "identity-a"
    assert manifest.get_document_by_url("https://example.test/a")["doc_id"] == doc_id
    assert manifest.aliases_for(doc_id)[0]["alias_url"] == "https://mirror.test/a"
    assert manifest.incomplete_jobs() == []
    assert manifest.get_run(run_id)["summary"]["added"] == 1

