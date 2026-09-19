"""Measure reproducible local retrieval/answer latency without external services."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings
from ragforge.models import Chunk
from ragforge.pipeline import RAGForge


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int((len(ordered) * percentile) + 0.9999) - 1),
    )
    return ordered[index]


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        vector_store="in_memory",
        embedder_backend="deterministic",
        embedder_dim=64,
        generation_backend="offline",
        default_generation_model="offline",
        allowed_generation_models=["offline"],
        use_rerank=False,
    )


def _measure(engine: RAGForge, concurrency: int, repeats: int) -> list[float]:
    def one(_: int) -> float:
        started = time.perf_counter()
        engine.ask("What does RAG combine?")
        return (time.perf_counter() - started) * 1000

    values: list[float] = []
    for start in range(0, repeats, concurrency):
        batch_size = min(concurrency, repeats - start)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            values.extend(pool.map(one, range(batch_size)))
    return values


def run(repeats: int = 12, concurrencies: tuple[int, ...] = (1, 2, 4)) -> dict:
    cold_started = time.perf_counter()
    engine = RAGForge(_settings())
    engine.ingest_chunks([
        Chunk(
            id=f"benchmark-{index}",
            doc_id=f"doc-{index}",
            title="benchmark",
            text="RAG combines retrieval with generation.",
            source="benchmark",
        )
        for index in range(40)
    ])
    cold_start_ms = (time.perf_counter() - cold_started) * 1000
    try:
        measurements = {}
        for concurrency in concurrencies:
            values = _measure(engine, concurrency, repeats)
            measurements[str(concurrency)] = {
                "concurrency": concurrency,
                "samples": len(values),
                "mean_ms": round(statistics.mean(values), 3),
                "p50_ms": round(_percentile(values, 0.50), 3),
                "p95_ms": round(_percentile(values, 0.95), 3),
            }
        return {
            "profile": "diagnostic",
            "backend": "in_memory + deterministic + offline",
            "repeats_per_concurrency": repeats,
            "cold_start_ms": round(cold_start_ms, 3),
            "measurements": measurements,
            "note": "Synthetic offline measurements; not a production model or corpus benchmark.",
        }
    finally:
        engine.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=12)
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("--repeats must be positive")
    print(json.dumps(run(args.repeats), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
