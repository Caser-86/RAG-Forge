"""公开知识库采集状态、版本和可恢复更新任务的 SQLite 清单。"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .collector import normalize_url
from .models import Document


SCHEMA_VERSION = 1
TERMINAL_JOB_PHASES = {"indexed", "failed", "skipped"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_doc_id(url: str) -> str:
    import hashlib

    return "doc_" + hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class KnowledgeItem:
    url: str
    source_id: str
    title: str
    text: str
    content_hash: str
    retrieved_at: str
    source_type: str = "html"
    category: str = ""
    language: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    raw_path: str | None = None
    processed_path: str | None = None
    cleaner_version: str = ""

    @property
    def doc_id(self) -> str:
        return stable_doc_id(self.url)

    def to_document(self, *, version: int) -> Document:
        metadata = dict(self.meta)
        metadata.update({
            "source_id": self.source_id,
            "raw_path": self.raw_path,
            "processed_path": self.processed_path,
            "cleaner_version": self.cleaner_version,
        })
        return Document(
            id=self.doc_id,
            title=self.title,
            text=self.text,
            meta=metadata,
            source_url=normalize_url(self.url),
            source_type=self.source_type,
            category=self.category,
            language=self.language,
            content_hash=self.content_hash,
            version=version,
            retrieved_at=self.retrieved_at,
            active=True,
        )


class KnowledgeManifest:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> KnowledgeManifest:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                indexed_at TEXT,
                last_seen_run TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                raw_path TEXT,
                processed_path TEXT,
                cleaner_version TEXT NOT NULL DEFAULT '',
                source_hint TEXT NOT NULL DEFAULT '',
                canonical_doc_id TEXT,
                indexed_content_hash TEXT,
                indexed_version INTEGER,
                indexed_identity TEXT,
                last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
            CREATE INDEX IF NOT EXISTS idx_documents_source_seen ON documents(source_id, last_seen_run);
            CREATE TABLE IF NOT EXISTS source_aliases (
                content_hash TEXT NOT NULL,
                canonical_doc_id TEXT NOT NULL,
                alias_url TEXT NOT NULL,
                source_id TEXT NOT NULL,
                last_seen_run TEXT NOT NULL,
                PRIMARY KEY(content_hash, alias_url)
            );
            CREATE TABLE IF NOT EXISTS update_jobs (
                job_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                target_version INTEGER NOT NULL,
                phase TEXT NOT NULL,
                error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_phase ON update_jobs(phase);
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                summary_json TEXT,
                discovery_complete INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        current = self.connection.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        if current is None:
            self.connection.execute(
                "INSERT INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
        elif int(current[0]) > SCHEMA_VERSION:
            raise RuntimeError("knowledge manifest schema is newer than this application")
        self.connection.commit()

    def start_run(self, run_id: str | None = None) -> str:
        run_id = run_id or uuid4().hex
        self.connection.execute(
            "INSERT INTO runs(run_id, started_at) VALUES (?, ?)",
            (run_id, _now()),
        )
        self.connection.commit()
        return run_id

    def finish_run(self, run_id: str, summary: dict[str, Any], *, discovery_complete: bool = False) -> None:
        self.connection.execute(
            "UPDATE runs SET completed_at = ?, summary_json = ?, discovery_complete = ? WHERE run_id = ?",
            (_now(), json.dumps(summary, ensure_ascii=False, sort_keys=True), int(discovery_complete), run_id),
        )
        self.connection.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["summary"] = json.loads(result.pop("summary_json") or "{}")
        return result

    def save_document(
        self,
        *,
        doc_id: str,
        url: str,
        source_id: str,
        title: str,
        content_hash: str,
        version: int,
        status: str,
        retrieved_at: str,
        last_seen_run: str | None = None,
        active: bool = True,
        raw_path: str | None = None,
        processed_path: str | None = None,
        cleaner_version: str = "",
        source_hint: str = "",
        canonical_doc_id: str | None = None,
        last_error: str | None = None,
    ) -> None:
        normalized = normalize_url(url)
        self.connection.execute(
            """
            INSERT INTO documents(
                doc_id, url, source_id, title, content_hash, version, status,
                retrieved_at, last_seen_run, active, raw_path, processed_path,
                cleaner_version, source_hint, canonical_doc_id, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                url = excluded.url,
                source_id = excluded.source_id,
                title = excluded.title,
                content_hash = excluded.content_hash,
                version = excluded.version,
                status = excluded.status,
                retrieved_at = excluded.retrieved_at,
                last_seen_run = excluded.last_seen_run,
                active = excluded.active,
                raw_path = excluded.raw_path,
                processed_path = excluded.processed_path,
                cleaner_version = excluded.cleaner_version,
                source_hint = excluded.source_hint,
                canonical_doc_id = excluded.canonical_doc_id,
                last_error = excluded.last_error
            """,
            (doc_id, normalized, source_id, title, content_hash, version, status,
             retrieved_at, last_seen_run, int(active), raw_path, processed_path,
             cleaner_version, source_hint, canonical_doc_id, last_error),
        )
        self.connection.commit()

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row is not None else None

    def get_document_by_url(self, url: str) -> dict[str, Any] | None:
        normalized = normalize_url(url)
        row = self.connection.execute("SELECT * FROM documents WHERE url = ?", (normalized,)).fetchone()
        return dict(row) if row is not None else None

    def find_indexed_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT * FROM documents
            WHERE content_hash = ? AND status = 'indexed' AND active = 1
              AND indexed_content_hash = content_hash
            ORDER BY indexed_at, doc_id LIMIT 1
            """,
            (content_hash,),
        ).fetchone()
        return dict(row) if row is not None else None

    def mark_indexed(self, doc_id: str, *, indexed_identity: str, indexed_version: int | None = None) -> None:
        row = self.get_document(doc_id)
        if row is None:
            raise KeyError(doc_id)
        version = indexed_version if indexed_version is not None else row["version"]
        self.connection.execute(
            """
            UPDATE documents SET status = 'indexed', indexed_at = ?,
                indexed_content_hash = content_hash, indexed_version = ?,
                indexed_identity = ?, last_error = NULL, active = 1
            WHERE doc_id = ?
            """,
            (_now(), version, indexed_identity, doc_id),
        )
        self.connection.commit()

    def create_job(self, doc_id: str, target_version: int, phase: str = "pending") -> str:
        job_id = uuid4().hex
        now = _now()
        self.connection.execute(
            "INSERT INTO update_jobs(job_id, doc_id, target_version, phase, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, doc_id, target_version, phase, now, now),
        )
        self.connection.commit()
        return job_id

    def set_job_phase(self, job_id: str, phase: str, error_code: str | None = None) -> None:
        self.connection.execute(
            "UPDATE update_jobs SET phase = ?, error_code = ?, updated_at = ? WHERE job_id = ?",
            (phase, error_code, _now(), job_id),
        )
        self.connection.commit()

    def incomplete_jobs(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM update_jobs WHERE phase NOT IN ('indexed', 'failed', 'skipped') ORDER BY created_at"
        ).fetchall()
        return [dict(row) for row in rows]

    def record_alias(self, content_hash: str, canonical_doc_id: str, alias_url: str, source_id: str, run_id: str) -> None:
        self.connection.execute(
            """
            INSERT INTO source_aliases(content_hash, canonical_doc_id, alias_url, source_id, last_seen_run)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(content_hash, alias_url) DO UPDATE SET
                canonical_doc_id = excluded.canonical_doc_id,
                source_id = excluded.source_id,
                last_seen_run = excluded.last_seen_run
            """,
            (content_hash, canonical_doc_id, normalize_url(alias_url), source_id, run_id),
        )
        self.connection.commit()

    def aliases_for(self, canonical_doc_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM source_aliases WHERE canonical_doc_id = ? ORDER BY alias_url",
            (canonical_doc_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_inactive_missing(self, source_id: str, run_id: str) -> list[str]:
        rows = self.connection.execute(
            "SELECT doc_id FROM documents WHERE source_id = ? AND active = 1 AND (last_seen_run IS NULL OR last_seen_run != ?)",
            (source_id, run_id),
        ).fetchall()
        ids = [row[0] for row in rows]
        if ids:
            self.connection.executemany(
                "UPDATE documents SET active = 0, status = 'inactive' WHERE doc_id = ?",
                [(doc_id,) for doc_id in ids],
            )
            self.connection.commit()
        return ids


class IncrementalUpdater:
    """把清洗后的页面以可恢复的单进程窗口写入索引。"""

    def __init__(
        self,
        manifest: KnowledgeManifest,
        index_document: Callable[[Document], int] | Any,
        has_indexed: Callable[[str, int], bool] | None = None,
        cleanup_version: Callable[[str, int], None] | None = None,
        set_active: Callable[[str, bool], None] | None = None,
        *,
        index_identity: str | dict[str, Any] = "",
    ):
        self.manifest = manifest
        if not callable(index_document) and hasattr(index_document, "index_document"):
            indexer = index_document
            index_document = indexer.index_document
            has_indexed = has_indexed or indexer.has_indexed
            cleanup_version = cleanup_version or getattr(indexer, "cleanup_version", None)
            set_active = set_active or getattr(indexer, "set_active", None)
        if has_indexed is None:
            raise TypeError("has_indexed callback is required")
        self.index_document = index_document
        self.has_indexed = has_indexed
        self.cleanup_version = cleanup_version or (lambda _doc_id, _version: None)
        self.set_active = set_active
        self.index_identity = (
            json.dumps(index_identity, ensure_ascii=False, sort_keys=True)
            if isinstance(index_identity, dict) else str(index_identity)
        )

    def recover_incomplete(self) -> None:
        for job in self.manifest.incomplete_jobs():
            self.cleanup_version(job["doc_id"], job["target_version"])
            self.manifest.set_job_phase(job["job_id"], "failed", "interrupted_recovered")

    def update(
        self,
        items: Iterable[KnowledgeItem],
        *,
        run_id: str | None = None,
        source_completeness: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        run_id = self.manifest.start_run(run_id)
        summary: dict[str, Any] = {
            "run_id": run_id, "added": 0, "updated": 0, "unchanged": 0,
            "failed": 0, "inactive": 0, "skipped": 0, "embedded": 0,
            "errors": [], "discovery_complete": False,
        }
        self.recover_incomplete()
        for item in items:
            normalized = normalize_url(item.url)
            state = self.manifest.get_document_by_url(normalized)
            if state is None:
                canonical = self.manifest.find_indexed_by_hash(item.content_hash)
                if canonical is not None and canonical["url"] != normalized:
                    self.manifest.record_alias(item.content_hash, canonical["doc_id"], normalized, item.source_id, run_id)
                    self.manifest.save_document(
                        doc_id=item.doc_id, url=normalized, source_id=item.source_id, title=item.title,
                        content_hash=item.content_hash, version=canonical["version"], status="alias",
                        retrieved_at=item.retrieved_at, last_seen_run=run_id, canonical_doc_id=canonical["doc_id"],
                    )
                    summary["skipped"] += 1
                    continue
            if (
                state is not None
                and state["content_hash"] == item.content_hash
                and state["status"] == "indexed"
                and state["indexed_content_hash"] == item.content_hash
                and state["indexed_version"] == state["version"]
                and state["indexed_identity"] == self.index_identity
                and self.has_indexed(state["doc_id"], state["version"])
            ):
                self.manifest.save_document(
                    doc_id=state["doc_id"], url=normalized, source_id=item.source_id, title=item.title,
                    content_hash=item.content_hash, version=state["version"], status="indexed",
                    retrieved_at=item.retrieved_at, last_seen_run=run_id, active=True,
                    raw_path=item.raw_path, processed_path=item.processed_path, cleaner_version=item.cleaner_version,
                )
                summary["unchanged"] += 1
                continue

            doc_id = state["doc_id"] if state is not None else item.doc_id
            version = (state["version"] + 1) if state is not None else 1
            self.manifest.save_document(
                doc_id=doc_id, url=normalized, source_id=item.source_id, title=item.title,
                content_hash=item.content_hash, version=version, status="pending",
                retrieved_at=item.retrieved_at, last_seen_run=run_id, active=True,
                raw_path=item.raw_path, processed_path=item.processed_path, cleaner_version=item.cleaner_version,
            )
            job_id = self.manifest.create_job(doc_id, version)
            self.manifest.set_job_phase(job_id, "indexing")
            document = item.to_document(version=version)
            document = document.model_copy(update={"id": doc_id})
            try:
                embedded = self.index_document(document)
                if embedded <= 0 or not self.has_indexed(doc_id, version):
                    raise RuntimeError("index verification failed")
            except Exception as exc:  # noqa: BLE001 - status must be persisted for recovery
                self.cleanup_version(doc_id, version)
                self.manifest.save_document(
                    doc_id=doc_id, url=normalized, source_id=item.source_id, title=item.title,
                    content_hash=item.content_hash, version=version, status="failed",
                    retrieved_at=item.retrieved_at, last_seen_run=run_id, active=True,
                    raw_path=item.raw_path, processed_path=item.processed_path, cleaner_version=item.cleaner_version,
                    last_error=str(exc),
                )
                self.manifest.set_job_phase(job_id, "failed", type(exc).__name__)
                summary["failed"] += 1
                summary["errors"].append({"url": normalized, "error": type(exc).__name__})
                continue
            self.manifest.mark_indexed(doc_id, indexed_identity=self.index_identity, indexed_version=version)
            self.manifest.set_job_phase(job_id, "indexed")
            summary["embedded"] += 1
            summary["updated" if state is not None else "added"] += 1

        source_completeness = source_completeness or {}
        complete = bool(source_completeness) and all(source_completeness.values())
        summary["discovery_complete"] = complete
        if complete:
            for source_id, is_complete in source_completeness.items():
                if not is_complete:
                    continue
                inactive = self.manifest.mark_inactive_missing(source_id, run_id)
                summary["inactive"] += len(inactive)
                if self.set_active:
                    for doc_id in inactive:
                        self.set_active(doc_id, False)
        self.manifest.finish_run(run_id, summary, discovery_complete=complete)
        return summary
