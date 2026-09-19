"""抓取来源配置中的公开页面并保存 raw/processed 资料与摘要。"""
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
from ragforge.ingest.cleaner import clean_html


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def fetch_sources(
    config: Path,
    *,
    max_pages: int | None = None,
    max_seconds: float | None = None,
    raw_dir: Path = Path("data/raw/web"),
    processed_dir: Path = Path("data/processed/web"),
    report_dir: Path = Path("data/reports"),
) -> dict[str, object]:
    sources = load_sources(config)
    summary: dict[str, object] = {
        "run_id": _timestamp(), "sources": [], "pages": 0, "cleaned": 0,
        "skipped": 0, "failed": 0, "errors": [], "max_seconds": max_seconds,
    }
    with HttpCollector(sources, max_duration=max_seconds) as collector:
        for result in collector.collect(max_pages=max_pages):
            source_summary = {
                "source_id": result.source_id,
                "discovered": len(result.discovered_urls),
                "pages": len(result.pages),
                "errors": len(result.errors),
                "skipped": len(result.skipped),
                "enumeration_complete": result.enumeration_complete,
            }
            summary["sources"].append(source_summary)
            summary["pages"] = int(summary["pages"]) + len(result.pages)
            summary["failed"] = int(summary["failed"]) + len(result.errors)
            summary["skipped"] = int(summary["skipped"]) + len(result.skipped)
            summary["errors"].extend({"code": error.code, "url": error.url, "message": error.message} for error in result.errors)
            for page in result.pages:
                digest = hashlib.sha256(page.content).hexdigest()
                raw_path = raw_dir / result.source_id / f"{digest}.html"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                if not raw_path.exists():
                    raw_path.write_bytes(page.content)
                cleaned = clean_html(page.content, page.url, response_status=page.status or 200)
                if cleaned.status != "ok":
                    summary["skipped"] = int(summary["skipped"]) + 1
                    continue
                processed_path = processed_dir / result.source_id / f"{cleaned.content_hash}.md"
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                if not processed_path.exists():
                    processed_path.write_text(cleaned.text, encoding="utf-8")
                summary["cleaned"] = int(summary["cleaned"]) + 1
    summary["time_budget_exhausted"] = any(
        error.get("code") == "time_budget_exhausted" for error in summary["errors"]
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"fetch-{summary['run_id']}.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["report_path"] = str(report_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and clean official public documentation")
    parser.add_argument("--config", default="configs/sources.yaml")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-seconds", type=float, help="停止本次采集的总时限；适合批量任务的可控运行")
    parser.add_argument("--raw-dir", default="data/raw/web")
    parser.add_argument("--processed-dir", default="data/processed/web")
    parser.add_argument("--report-dir", default="data/reports")
    args = parser.parse_args()
    if args.max_seconds is not None and args.max_seconds <= 0:
        parser.error("--max-seconds must be positive")
    result = fetch_sources(
        Path(args.config), max_pages=args.max_pages, max_seconds=args.max_seconds, raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.processed_dir), report_dir=Path(args.report_dir),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
