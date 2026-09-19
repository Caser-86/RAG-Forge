from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_benchmark_reports_warm_latency_percentiles_and_concurrency():
    script = (ROOT / "scripts" / "benchmark_runtime.py").read_text(encoding="utf-8")

    for required in ("p50_ms", "p95_ms", "concurrency", "cold_start_ms", "ThreadPoolExecutor"):
        assert required in script
