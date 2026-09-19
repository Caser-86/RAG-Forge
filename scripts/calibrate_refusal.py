"""Run the deterministic M6 refusal gate on fixed calibration fixtures.

This is an engineering calibration, not a semantic LLM quality benchmark. It
deliberately does not tune a threshold against an evaluation split.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings
from ragforge.generator import OfflineGenerator
from ragforge.models import Chunk, Evidence


def _load(path: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(calibration_dir: Path) -> dict[str, object]:
    settings = Settings(
        _env_file=None,
        vector_store="in_memory",
        generation_backend="offline",
        embedder_backend="deterministic",
        embedder_dim=8,
        refuse_threshold=0.15,
        use_rerank=False,
    )
    generator = OfflineGenerator(settings)
    unanswerable = _load(calibration_dir / "unanswerable.jsonl")
    answerable = _load(calibration_dir / "answerable.jsonl")

    no_answer_results = [
        generator.generate(item["query"], [], f"cal-na-{item['id']}")
        for item in unanswerable
    ]
    answer_results = []
    for item in answerable:
        evidence = Evidence(
            chunk=Chunk(
                id=f"chunk-{item['id']}",
                doc_id=item["id"],
                title=item["id"],
                text=item["answer"],
                source="calibration-fixture",
            )
        )
        answer_results.append(
            generator.generate(item["query"], [evidence], f"cal-a-{item['id']}")
        )

    missed_refusals = sum(not answer.refused for answer in no_answer_results)
    false_refusals = sum(answer.refused for answer in answer_results)
    return {
        "mode": "engineering_offline",
        "retrieval_mode": "not evaluated; fixed evidence labels",
        "threshold": settings.refuse_threshold,
        "threshold_status": "uncalibrated",
        "calibration_only": True,
        "no_answer": {
            "total": len(no_answer_results),
            "correct_refusal": len(no_answer_results) - missed_refusals,
            "missed_refusal": missed_refusals,
        },
        "answerable": {
            "total": len(answer_results),
            "false_refusal": false_refusals,
            "false_refusal_rate": false_refusals / max(len(answer_results), 1),
        },
        "gate": "PASS" if len(no_answer_results) - missed_refusals > len(no_answer_results) / 2 else "FAIL",
        "note": "Offline deterministic fixture gate; independent semantic and LLM evaluation remains required.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("tests/fixtures"),
        help="directory containing unanswerable.jsonl and answerable.jsonl",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.fixtures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
