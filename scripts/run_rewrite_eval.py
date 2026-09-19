"""Evaluate optional query rewriting on the fixed M8 context-dependent cases."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings
from ragforge.query_rewriter import QueryRewriter


def _load(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(fixtures: Path) -> dict[str, object]:
    settings = Settings(
        _env_file=None,
        embedder_backend="deterministic",
        embedder_dim=8,
        generation_backend="ollama",
        rewrite_enabled=True,
        rewrite_model="qwen3:0.6b",
        ollama_generate_timeout=30,
    )
    cases = _load(fixtures / "rewrite_cases.jsonl")
    off_rewriter = QueryRewriter(settings)
    rewriter = QueryRewriter(settings)
    rows: list[dict[str, object]] = []
    try:
        for case in cases:
            query = str(case["query"])
            history = [{"role": "user", "content": "请继续上一轮并保留原问题中的关键限定。"}]
            off_start = time.monotonic()
            off = off_rewriter.rewrite(query, history, enabled=False)
            off_ms = (time.monotonic() - off_start) * 1000
            on_start = time.monotonic()
            on = rewriter.rewrite(query, history, enabled=True)
            on_ms = (time.monotonic() - on_start) * 1000
            rows.append({
                "id": case["id"],
                "expected_doc_ids": case["expected_doc_ids"],
                "off_query": off,
                "on_query": on,
                "on_fallback": rewriter.last_result.fallback,
                "on_reason": rewriter.last_result.reason,
                "critical_tokens_preserved": not bool(
                    QueryRewriter._critical_tokens(query)
                    - QueryRewriter._casefold_tokens(on)
                ),
                "off_ms": off_ms,
                "on_ms": on_ms,
            })
    finally:
        off_rewriter.close()
        rewriter.close()
    changed = sum(row["on_query"] != row["off_query"] for row in rows)
    fallbacks = sum(bool(row["on_fallback"]) for row in rows)
    preserved = sum(bool(row["critical_tokens_preserved"]) for row in rows)
    return {
        "model": settings.rewrite_model,
        "cases": len(rows),
        "changed": changed,
        "fallback": fallbacks,
        "critical_tokens_preserved": preserved,
        "mean_off_ms": sum(float(row["off_ms"]) for row in rows) / max(len(rows), 1),
        "mean_on_ms": sum(float(row["on_ms"]) for row in rows) / max(len(rows), 1),
        "rows": rows,
        "note": "Rewrite-only comparison; expected_doc_ids are fixed labels and retrieval quality needs a separate isolated corpus experiment.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run(args.fixtures)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
