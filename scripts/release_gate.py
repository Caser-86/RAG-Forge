"""只读发布门禁：检查发布前的硬性输入是否齐备。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.evaluation.benchmark import benchmark_dataset_content_sha256, load_cases

EXPECTED_GOLDEN_COUNT = 100
EXPECTED_CALIBRATION_COUNT = 20

REQUIRED_FILES = (
    ".env.example",
    ".github/workflows/ci.yml",
    "benchmarks/README.md",
    "configs/experiments-release.yaml",
    "Dockerfile",
    "README.md",
    "docker-compose.yml",
    "docker-compose.ollama.yml",
    "docs/LOCAL-SETUP.md",
    "docs/RELEASE.md",
    "docs/reports/final-acceptance.md",
    "pyproject.toml",
    "requirements/docker-py311-piptools.txt",
    "requirements/windows-collector-py314-piptools.txt",
    "requirements/windows-local-py314-piptools.txt",
    "requirements/windows-vector-dev-py314-piptools.txt",
)


def _check(name: str, passed: bool, detail: str, *blockers: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "BLOCKED",
        "detail": detail,
        "blockers": list(blockers),
    }


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], f"{type(exc).__name__}: {path}"
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            return [], f"invalid JSON at line {line_number}"
        if not isinstance(row, dict):
            return [], f"row at line {line_number} is not an object"
        rows.append(row)
    return rows, None


def _resolve_path(value: Path | None, repo_root: Path, default: str) -> Path:
    path = value if value is not None else Path(default)
    return (repo_root / path if not path.is_absolute() else path).resolve()


def _check_required_files(repo_root: Path) -> dict[str, Any]:
    missing = [relative for relative in REQUIRED_FILES if not (repo_root / relative).is_file()]
    if missing:
        return _check(
            "required_files",
            False,
            f"missing {len(missing)} required files",
            "required_files_missing",
        ) | {"missing": missing}
    return _check("required_files", True, f"{len(REQUIRED_FILES)} required files present")


def _check_license(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "LICENSE"
    try:
        present = path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeError):
        present = False
    if not present:
        return _check(
            "license",
            False,
            "root LICENSE is missing or empty; pyproject metadata alone is insufficient",
            "license_missing",
        )
    return _check("license", True, "non-empty root LICENSE is present")


def _check_golden(repo_root: Path, golden_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], set[str]]:
    rows, error = _read_jsonl(golden_path)
    if error:
        blocker = "golden_missing" if not golden_path.exists() else "golden_invalid"
        return _check("golden", False, error, blocker), [], set()
    if not rows:
        return _check("golden", False, "golden.jsonl contains no reviewed cases", "golden_empty"), [], set()

    try:
        load_cases(golden_path, require_reviewed=True)
    except (FileNotFoundError, OSError, UnicodeError, ValueError) as exc:
        return (
            _check("golden", False, f"invalid benchmark schema: {type(exc).__name__}", "golden_invalid_schema"),
            rows,
            {str(row["id"]) for row in rows if isinstance(row.get("id"), str)},
        )

    case_ids: set[str] = set()
    row_blockers: set[str] = set()
    corpus_root = (repo_root / "data/processed/web").resolve()
    for row in rows:
        case_id = row.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            row_blockers.add("golden_invalid_row")
            continue
        if case_id in case_ids:
            row_blockers.add("golden_duplicate_id")
        case_ids.add(case_id)
        if row.get("review_status") != "reviewed":
            row_blockers.add("golden_unreviewed_cases")
        if not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
            row_blockers.add("golden_missing_reviewer")
        if not isinstance(row.get("reviewed_at"), str) or not row["reviewed_at"].strip():
            row_blockers.add("golden_missing_reviewed_at")
        refs = row.get("source_refs")
        if not isinstance(refs, list):
            row_blockers.add("golden_missing_source_refs")
            continue
        # Unanswerable cases intentionally may have no supporting document;
        # answerable cases must remain traceable to at least one source.
        if row.get("answerable") is True and not refs:
            row_blockers.add("golden_missing_source_refs")
            continue
        for ref in refs:
            if not isinstance(ref, str) or not ref:
                row_blockers.add("golden_invalid_source_ref")
                continue
            candidate = (repo_root / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
            try:
                candidate.relative_to(corpus_root)
            except ValueError:
                row_blockers.add("golden_source_outside_corpus")
                continue
            if not candidate.is_file():
                row_blockers.add("golden_source_missing")

    if len(rows) != EXPECTED_GOLDEN_COUNT:
        row_blockers.add("golden_count")
    if row_blockers:
        detail = f"{len(rows)} rows; blockers: {', '.join(sorted(row_blockers))}"
        return _check("golden", False, detail, *sorted(row_blockers)), rows, case_ids
    return _check("golden", True, f"{len(rows)} reviewed cases with reviewer/time/source_refs"), rows, case_ids


def _check_split(split_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not split_path.is_file():
        return _check("frozen_split", False, "golden-split.json is missing", "split_missing")
    try:
        payload = json.loads(split_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _check("frozen_split", False, f"invalid frozen split: {type(exc).__name__}", "split_invalid")
    if not isinstance(payload, dict):
        return _check("frozen_split", False, "frozen split must be an object", "split_invalid")

    blockers: set[str] = set()
    stored_hash = payload.get("split_sha256")
    body = {key: value for key, value in payload.items() if key != "split_sha256"}
    actual_hash = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if not isinstance(stored_hash, str) or stored_hash != actual_hash:
        blockers.add("split_hash_mismatch")
    if payload.get("schema_version") != 2:
        blockers.add("split_schema")
    expected_dataset_hash = benchmark_dataset_content_sha256(rows)
    if payload.get("dataset_content_sha256") != expected_dataset_hash:
        blockers.add("split_dataset_content_mismatch")

    calibration = payload.get("calibration_ids")
    test = payload.get("test_ids")
    if not isinstance(calibration, list) or not isinstance(test, list):
        return _check("frozen_split", False, "calibration_ids and test_ids are required lists", "split_invalid")
    if not all(isinstance(item, str) and item for item in calibration + test):
        blockers.add("split_invalid_id")
    calibration_ids = [item for item in calibration if isinstance(item, str)]
    test_ids = [item for item in test if isinstance(item, str)]
    if len(set(calibration_ids)) != len(calibration_ids) or len(set(test_ids)) != len(test_ids):
        blockers.add("split_duplicate_id")
    if set(calibration_ids) & set(test_ids):
        blockers.add("split_overlap")
    case_ids = {str(row.get("id")) for row in rows if isinstance(row.get("id"), str)}
    if set(calibration_ids) | set(test_ids) != case_ids:
        blockers.add("split_union_mismatch")
    if len(calibration_ids) != EXPECTED_CALIBRATION_COUNT:
        blockers.add("split_calibration_count")
    if len(test_ids) != EXPECTED_GOLDEN_COUNT - EXPECTED_CALIBRATION_COUNT:
        blockers.add("split_test_count")

    if blockers:
        return _check(
            "frozen_split",
            False,
            f"calibration={len(calibration_ids)}, test={len(test_ids)}; blockers: {', '.join(sorted(blockers))}",
            *sorted(blockers),
        )
    return _check("frozen_split", True, "hash-valid 20/80 calibration/test split")


def evaluate_release(
    repo_root: Path = ROOT,
    *,
    golden_path: Path | None = None,
    split_path: Path | None = None,
) -> dict[str, Any]:
    """返回可审计的发布前置检查结果；本函数不写入任何文件。"""
    root = repo_root.resolve()
    golden = _resolve_path(golden_path, root, "benchmarks/golden.jsonl")
    split = _resolve_path(split_path, root, "benchmarks/golden-split.json")
    checks = [_check_required_files(root), _check_license(root)]
    golden_check, rows, case_ids = _check_golden(root, golden)
    checks.append(golden_check)
    checks.append(_check_split(split, rows))
    blockers: list[str] = []
    for check in checks:
        for blocker in check["blockers"]:
            if blocker not in blockers:
                blockers.append(blocker)
    return {
        "schema_version": 1,
        "status": "READY" if not blockers else "BLOCKED",
        "ready": not blockers,
        "repo_root": str(root),
        "golden": str(golden),
        "frozen_split": str(split),
        "golden_row_count": len(rows),
        "checks": checks,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--split", type=Path)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args(argv)
    report = evaluate_release(args.repo_root, golden_path=args.golden, split_path=args.split)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Release gate: {report['status']}")
        for check in report["checks"]:
            print(f"[{check['status']}] {check['name']}: {check['detail']}")
        if report["blockers"]:
            print("Blockers: " + ", ".join(report["blockers"]))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
