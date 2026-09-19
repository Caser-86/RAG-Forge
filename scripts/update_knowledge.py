"""抓取、清洗并增量更新本地知识库。

更新期间应停止 FastAPI；脚本只维护一个进程窗口，避免 Qdrant Local 文件锁冲突。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.collector import HttpCollector, load_sources
from ragforge.config import Settings, get_settings
from ragforge.ingest.cleaner import clean_html
from ragforge.knowledge_manifest import IncrementalUpdater, KnowledgeItem, KnowledgeManifest
from ragforge.pipeline import RAGForge


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _settings_from_cli(args: argparse.Namespace, base_settings: Settings | None = None) -> Settings:
    """构造更新任务配置，避免把 .env 中的检索实验配置带入索引流程。"""
    base_settings = base_settings or get_settings()
    overrides = {
        key: value for key, value in {
            "vector_store": args.vector_store,
            "qdrant_url": args.qdrant_url,
            "qdrant_collection": args.qdrant_collection,
            "index_manifest_path": Path(args.index_manifest_path) if args.index_manifest_path else None,
            "knowledge_manifest_path": Path(args.knowledge_manifest_path) if args.knowledge_manifest_path else None,
            "embedder_backend": args.embedder_backend,
            "embedder_model": args.embedder_model,
            # 索引阶段会构造 Retriever，但不需要 CrossEncoder 重排；默认显式关闭。
            "use_rerank": bool(args.use_rerank),
        }.items() if value is not None
    }
    return Settings(_env_file=None, **{**base_settings.model_dump(), **overrides})


def update_knowledge(
    config: Path,
    *,
    settings: Settings | None = None,
    max_pages: int | None = None,
    max_seconds: float | None = None,
    raw_dir: Path | None = None,
    processed_dir: Path | None = None,
    report_dir: Path = Path("data/reports"),
) -> dict[str, object]:
    settings = settings or get_settings()
    raw_dir = raw_dir or settings.raw_data_dir / "web"
    processed_dir = processed_dir or settings.processed_data_dir / "web"
    sources = load_sources(config)
    source_by_id = {source.id: source for source in sources}
    items: list[KnowledgeItem] = []
    collector_errors: list[dict[str, object]] = []
    source_completeness: dict[str, bool] = {}
    with HttpCollector(sources, max_duration=max_seconds) as collector:
        results = collector.collect(max_pages=max_pages)
        for result in results:
            source_completeness[result.source_id] = result.enumeration_complete
            collector_errors.extend(
                {"source_id": result.source_id, "code": error.code, "url": error.url, "message": error.message}
                for error in result.errors
            )
            source = source_by_id[result.source_id]
            for page in result.pages:
                digest = hashlib.sha256(page.content).hexdigest()
                raw_path = raw_dir / result.source_id / f"{digest}.html"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                if not raw_path.exists():
                    raw_path.write_bytes(page.content)
                cleaned = clean_html(
                    page.content,
                    page.url,
                    response_status=page.status or 200,
                    source_meta={
                        "source_id": source.id,
                        "category": source.category,
                        "trust": source.trust,
                        "license_hint": source.license_hint,
                    },
                )
                if cleaned.status != "ok":
                    collector_errors.append({"source_id": source.id, "code": "cleaner_skipped", "url": page.url, "message": cleaned.reason})
                    continue
                processed_path = processed_dir / result.source_id / f"{cleaned.content_hash}.md"
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                if not processed_path.exists():
                    processed_path.write_text(cleaned.text, encoding="utf-8")
                items.append(KnowledgeItem(
                    url=page.url,
                    source_id=source.id,
                    title=cleaned.title,
                    text=cleaned.text,
                    content_hash=cleaned.content_hash,
                    retrieved_at=cleaned.retrieved_at,
                    source_type="official_html",
                    category=source.category,
                    language=source.language,
                    meta={"trust": source.trust, "license_hint": source.license_hint},
                    raw_path=str(raw_path),
                    processed_path=str(processed_path),
                    cleaner_version=cleaned.meta.get("cleaner_version", ""),
                ))

    manifest = KnowledgeManifest(settings.knowledge_manifest_path)
    engine: RAGForge | None = None
    try:
        engine = RAGForge(settings)

        def has_indexed(doc_id: str, version: int) -> bool:
            return any(
                chunk.doc_id == doc_id and chunk.meta.get("document_version") == version
                for chunk in engine.store.list_chunks()
            )

        updater = IncrementalUpdater(
            manifest,
            engine.ingest_document,
            has_indexed,
            cleanup_version=lambda doc_id, version: engine.store.delete_document(doc_id, version=version),
            set_active=engine.set_document_active,
            index_identity=engine._expected_manifest(),
        )
        summary = updater.update(items, source_completeness=source_completeness)
    finally:
        if engine is not None:
            engine.close()
        manifest.close()

    summary["collector_errors"] = collector_errors
    summary["source_completeness"] = source_completeness
    summary["collection_max_seconds"] = max_seconds
    summary["embedded_calls"] = summary.get("embedded", 0)
    summary["configuration"] = {
        "vector_store": settings.vector_store,
        "qdrant_url": settings.qdrant_url,
        "qdrant_collection": settings.qdrant_collection,
        "embedder_backend": settings.embedder_backend,
        "embedder_model": settings.embedder_model,
        "use_rerank": settings.use_rerank,
        "knowledge_manifest_path": str(settings.knowledge_manifest_path),
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"update-{summary['run_id']}.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally update the local RAG knowledge base")
    parser.add_argument("--config", default="configs/sources.yaml")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-seconds", type=float, help="停止本次采集与更新的总时限")
    parser.add_argument("--raw-dir")
    parser.add_argument("--processed-dir")
    parser.add_argument("--report-dir", default="data/reports")
    parser.add_argument("--vector-store", choices=["qdrant_local", "qdrant_server", "in_memory", "qdrant"])
    parser.add_argument("--qdrant-url")
    parser.add_argument("--qdrant-collection")
    parser.add_argument("--index-manifest-path")
    parser.add_argument("--knowledge-manifest-path")
    parser.add_argument("--embedder-backend", choices=["ollama", "local", "api", "deterministic"])
    parser.add_argument("--embedder-model")
    parser.add_argument(
        "--use-rerank",
        action="store_true",
        help="索引期间启用 CrossEncoder 重排器；默认关闭以避免加载不必要的本地模型",
    )
    args = parser.parse_args()
    if args.max_seconds is not None and args.max_seconds <= 0:
        parser.error("--max-seconds must be positive")
    base_settings = get_settings()
    # CLI 参数显式覆盖 .env；重新构造时关闭 dotenv，避免 Windows 子进程再次读到旧后端。
    settings = _settings_from_cli(args, base_settings)
    print(json.dumps({
        "effective_configuration": {
            "vector_store": settings.vector_store,
            "qdrant_url": settings.qdrant_url,
            "qdrant_collection": settings.qdrant_collection,
            "embedder_backend": settings.embedder_backend,
            "embedder_model": settings.embedder_model,
            "use_rerank": settings.use_rerank,
            "knowledge_manifest_path": str(settings.knowledge_manifest_path),
        }
    }, ensure_ascii=False))
    result = update_knowledge(
        Path(args.config), max_pages=args.max_pages, max_seconds=args.max_seconds,
        raw_dir=Path(args.raw_dir) if args.raw_dir else None,
        processed_dir=Path(args.processed_dir) if args.processed_dir else None,
        report_dir=Path(args.report_dir),
        settings=settings,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
