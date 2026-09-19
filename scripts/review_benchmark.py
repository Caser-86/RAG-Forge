"""本地人工审核 benchmark 候选题；不自动伪造 reviewer/reviewed_at。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
_MAX_SOURCE_SCAN_CHARS = 256_000
sys.path.insert(0, str(ROOT / "src"))

from ragforge.evaluation.benchmark import (  # noqa: E402
    benchmark_content_sha256,
    benchmark_dataset_content_sha256,
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"invalid benchmark row at {path}:{line_number}")
        rows.append(row)
    return rows


def validate_source_refs(row: dict[str, Any], *, repo_root: Path, corpus_root: Path) -> None:
    refs = row.get("source_refs", [])
    if not isinstance(refs, list) or not all(isinstance(ref, str) and ref for ref in refs):
        raise ValueError(f"source_refs must be a list for {row.get('id')}")
    resolved_corpus = corpus_root.resolve()
    for ref in refs:
        candidate = (repo_root / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
        try:
            candidate.relative_to(resolved_corpus)
        except ValueError as exc:
            raise ValueError(f"source ref outside corpus for {row.get('id')}: {ref}") from exc
        if not candidate.is_file():
            raise ValueError(f"source ref does not exist for {row.get('id')}: {ref}")


def source_previews(
    row: dict[str, Any], *, repo_root: Path, corpus_root: Path, max_chars: int = 1600
) -> list[dict[str, str]]:
    """Read bounded previews only after source paths have passed corpus containment checks."""
    validate_source_refs(row, repo_root=repo_root, corpus_root=corpus_root)
    previews: list[dict[str, str]] = []
    for ref in row.get("source_refs", []):
        candidate = (repo_root / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                source_text = handle.read(_MAX_SOURCE_SCAN_CHARS)
            text = _preview_window(source_text, row, max_chars=max_chars)
        except (OSError, UnicodeError) as exc:
            text = f"[source preview unavailable: {type(exc).__name__}]"
        previews.append({"source_ref": ref, "text": text})
    return previews


def _preview_window(source_text: str, row: dict[str, Any], *, max_chars: int) -> str:
    limit = max(1, int(max_chars))
    if len(source_text) <= limit:
        return source_text
    source_casefolded = source_text.casefold()
    match_at = -1
    needles = [str(row.get(field, "")).strip() for field in ("expected_answer", "question")]
    question = str(row.get("question", ""))
    for quoted in re.findall(r"['\"]([^'\"]+)['\"]", question):
        needles.append(re.split(r"[¶]", quoted, maxsplit=1)[0].strip())
    for needle in needles:
        if len(needle) < 4:
            continue
        match_at = source_casefolded.find(needle.casefold())
        if match_at >= 0:
            break
    if match_at < 0:
        return source_text[:limit]
    start = max(0, match_at - limit // 3)
    end = min(len(source_text), start + limit)
    if end - start < limit:
        start = max(0, end - limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(source_text) else ""
    content_limit = limit - len(prefix) - len(suffix)
    if content_limit <= 0:
        return source_text[:limit]
    end = min(len(source_text), start + content_limit)
    if end - start < content_limit:
        start = max(0, end - content_limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(source_text) else ""
    return prefix + source_text[start:end] + suffix


def load_progress(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            decision = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid review decision at {path}:{line_number}") from exc
        if not isinstance(decision, dict) or not isinstance(decision.get("id"), str):
            raise ValueError(f"invalid review decision at {path}:{line_number}")
        if decision.get("action") not in {"accept", "reject", "defer"}:
            raise ValueError(f"unsupported review action at {path}:{line_number}")
        latest[decision["id"]] = decision
    return latest


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _append_progress(path: Path, decision: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(decision, ensure_ascii=False) + "\n")


def review_content_sha256(row: dict[str, Any]) -> str:
    """Backward-compatible name for the shared benchmark content hash."""
    return benchmark_content_sha256(row)


def export_reviewed(
    rows: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    output: Path,
) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for row in rows:
        decision = decisions.get(row.get("id", ""))
        if not decision or decision.get("action") != "accept":
            continue
        if decision.get("content_sha256") != review_content_sha256(row):
            raise ValueError(f"review content mismatch for {row.get('id')}; review this case again")
        reviewer = decision.get("reviewer")
        reviewed_at = decision.get("reviewed_at")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError(f"accepted case {row.get('id')} has no reviewer")
        if not isinstance(reviewed_at, str) or not reviewed_at.strip():
            raise ValueError(f"accepted case {row.get('id')} has no reviewed_at")
        accepted = deepcopy(row)
        accepted["review_status"] = "reviewed"
        accepted["reviewer"] = reviewer.strip()
        accepted["reviewed_at"] = reviewed_at.strip()
        exported.append(accepted)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in exported)
        + ("\n" if exported else ""),
        encoding="utf-8",
    )
    return exported


def freeze_split(rows: list[dict[str, Any]], *, calibration_count: int = 20) -> dict[str, Any]:
    if calibration_count < 0 or calibration_count > len(rows):
        raise ValueError("calibration_count must be between zero and row count")
    seen_questions: set[str] = set()
    for row in rows:
        if (
            row.get("review_status") != "reviewed"
            or not isinstance(row.get("reviewer"), str)
            or not row["reviewer"].strip()
            or not isinstance(row.get("reviewed_at"), str)
            or not row["reviewed_at"].strip()
        ):
            raise ValueError(f"all split rows must be reviewed: {row.get('id')}")
        question = " ".join(str(row.get("question", "")).casefold().split())
        if not question:
            raise ValueError(f"empty question in {row.get('id')}")
        if question in seen_questions:
            raise ValueError(f"duplicate question cannot be split safely: {row.get('id')}")
        seen_questions.add(question)
    ordered = sorted(rows, key=lambda row: (str(row.get("category", "")), str(row["id"])))
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in ordered:
        buckets.setdefault(str(row.get("category", "")), []).append(row)
    calibration: list[dict[str, Any]] = []
    if calibration_count:
        for _round in range(max(1, len(rows))):
            for category in sorted(buckets):
                bucket = buckets[category]
                if not bucket:
                    continue
                calibration.append(bucket.pop(0))
                if len(calibration) == calibration_count:
                    break
            if len(calibration) == calibration_count:
                break
    calibration_ids = {str(row["id"]) for row in calibration}
    test = [row for row in ordered if str(row["id"]) not in calibration_ids]
    split = {
        "schema_version": 2,
        "calibration_ids": [str(row["id"]) for row in calibration],
        "test_ids": [str(row["id"]) for row in test],
        "dataset_content_sha256": benchmark_dataset_content_sha256(rows),
        "category_counts": {
            category: sum(str(row.get("category", "")) == category for row in rows)
            for category in sorted(buckets)
        },
    }
    encoded = json.dumps(split, ensure_ascii=False, sort_keys=True).encode("utf-8")
    split["split_sha256"] = hashlib.sha256(encoded).hexdigest()
    return split


def review_interactively(
    rows: list[dict[str, Any]], progress_path: Path, reviewer: str, *, repo_root: Path, corpus_root: Path
) -> None:
    if not reviewer.strip():
        raise ValueError("reviewer is required for interactive review")
    decisions = load_progress(progress_path)
    for index, row in enumerate(rows, start=1):
        current = decisions.get(row["id"])
        if (
            current and current.get("action") in {"accept", "reject"}
            and current.get("content_sha256") == review_content_sha256(row)
        ):
            continue
        print(f"\n[{index}/{len(rows)}] {row['id']} · {row.get('category', '')}")
        print(f"Q: {row.get('question', '')}")
        print(f"Expected: {row.get('expected_answer', '')}")
        print(f"Sources: {', '.join(row.get('source_refs', [])) or '(none)'}")
        for preview in source_previews(row, repo_root=repo_root, corpus_root=corpus_root):
            print(f"Evidence preview ({preview['source_ref']}):\n{preview['text']}")
        action = input("[a]ccept / [r]eject / [d]efer: ").strip().lower()
        if action not in {"a", "r", "d"}:
            raise ValueError("请输入 a、r 或 d；进度已保存到上一题")
        decision = {
            "id": row["id"],
            "action": {"a": "accept", "r": "reject", "d": "defer"}[action],
            "reviewer": reviewer.strip(),
            "reviewed_at": _now_utc(),
            "content_sha256": review_content_sha256(row),
        }
        _append_progress(progress_path, decision)
        decisions[row["id"]] = decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="benchmarks/candidates.jsonl")
    parser.add_argument("--progress", default="benchmarks/review-progress.jsonl")
    parser.add_argument("--output", default="benchmarks/golden.jsonl")
    parser.add_argument("--split", default="benchmarks/golden-split.json")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--corpus-root", type=Path, default=ROOT / "data/processed/web")
    parser.add_argument("--reviewer", help="真实审核人的标识；不会自动猜测")
    parser.add_argument("--export-only", action="store_true", help="只导出已保存的 accept 决策")
    parser.add_argument("--freeze-split", action="store_true")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    rows = load_rows(input_path.resolve())
    for row in rows:
        validate_source_refs(row, repo_root=args.repo_root.resolve(), corpus_root=args.corpus_root.resolve())
    progress_path = (ROOT / args.progress).resolve() if not Path(args.progress).is_absolute() else Path(args.progress)
    if not args.export_only:
        if not args.reviewer:
            parser.error("interactive review requires --reviewer")
        review_interactively(
            rows,
            progress_path,
            args.reviewer,
            repo_root=args.repo_root.resolve(),
            corpus_root=args.corpus_root.resolve(),
        )
    decisions = load_progress(progress_path)
    output = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    exported = export_reviewed(rows, decisions, output)
    if args.freeze_split:
        split = freeze_split(exported)
        split_path = (ROOT / args.split).resolve() if not Path(args.split).is_absolute() else Path(args.split)
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reviewed_exported": len(exported), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
