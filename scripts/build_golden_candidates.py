"""从本地已处理语料生成待人工审核的 100 条候选题。"""
from __future__ import annotations

import argparse
import json
import re
from itertools import cycle
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / "src"))

from ragforge.evaluation.benchmark import corpus_identity, stable_document_id


COUNTS = {
    "basic": 20,
    "definition": 15,
    "keyword": 15,
    "rewrite": 15,
    "cross-language": 15,
    "cross-document": 10,
    "unanswerable": 10,
}


def _files(root: Path) -> list[Path]:
    return [
        path for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    ]


def _clean(text: str) -> str:
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`>#]", "", text)
    return " ".join(text.split()).strip()


def _summary(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    heading = path.stem.replace("-", " ").replace("_", " ").strip()
    in_fence = False
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match and heading == path.stem.replace("-", " ").replace("_", " ").strip():
            heading = _clean(match.group(1)) or heading
        if not line.strip():
            if current:
                paragraphs.append(_clean(" ".join(current)))
                current = []
        elif not line.lstrip().startswith("#"):
            current.append(line)
    if current:
        paragraphs.append(_clean(" ".join(current)))
    body = next((p for p in paragraphs if len(p) >= 40), "")
    return heading or path.stem, body[:480]


def _corpus_identity(root: Path) -> dict:
    identity = corpus_identity(root)
    identity["root"] = root.relative_to(ROOT).as_posix()
    return identity


def _case(
    case_id: str,
    question: str,
    expected_doc_ids: list[str],
    expected_answer: str,
    category: str,
    identity: dict,
    index_identity: dict,
    sources: list[str],
) -> dict:
    return {
        "id": case_id,
        "question": question,
        "expected_doc_ids": expected_doc_ids,
        "expected_answer": expected_answer,
        "answerable": bool(expected_doc_ids),
        "category": category,
        "review_status": "candidate",
        "reviewer": None,
        "reviewed_at": None,
        "corpus_identity": identity,
        "index_identity": index_identity,
        "source_refs": sources,
        "generation_method": "deterministic section summary; requires human review",
    }


def build_candidates(corpus_root: Path) -> list[dict]:
    files = _files(corpus_root)
    if len(files) < 30:
        raise ValueError(f"corpus needs at least 30 markdown/text files, found {len(files)}")
    docs = []
    for path in files:
        heading, summary = _summary(path)
        if summary:
            docs.append((path, stable_document_id(path), heading, summary))
    if len(docs) < 20:
        raise ValueError("corpus has too few non-empty documents for candidate generation")

    identity = _corpus_identity(corpus_root)
    index_identity = {
        "backend": "in_memory",
        "embedder_backend": "deterministic",
        "embedder_model": "deterministic",
        "embedder_dim": 64,
        "chunk_strategy": "heading_chars",
        "chunk_size": 2200,
        "chunk_overlap": 200,
    }
    rows: list[dict] = []
    answerable_categories = [key for key in COUNTS if key not in {"unanswerable", "cross-document"}]
    cursor = cycle(docs)
    for category in answerable_categories:
        for offset in range(COUNTS[category]):
            first = next(cursor)
            path, doc_id, heading, summary = first
            label = f"{heading} ({path.stem})"
            if category == "basic":
                question = f"What is covered in the documentation section '{label}'?"
            elif category == "definition":
                question = f"How does the documentation define or explain '{label}'?"
            elif category == "keyword":
                question = f"Which keywords or configuration terms are associated with '{label}'?"
            elif category == "rewrite":
                question = f"In the context of '{label}', what should a reader check?"
            else:
                question = f"请说明文档中“{label}”这一部分的关键内容。"
            rows.append(_case(
                f"cand-{category}-{offset + 1:03d}", question,
                [doc_id], summary, category, identity, index_identity,
                [path.relative_to(ROOT).as_posix()],
            ))

    for offset in range(COUNTS["cross-document"]):
        first = docs[(offset * 2) % len(docs)]
        second = docs[(offset * 2 + 1) % len(docs)]
        question = f"Compare the topics covered by '{first[2]}' and '{second[2]}'."
        rows.append(_case(
            f"cand-cross-document-{offset + 1:03d}", question,
            [first[1], second[1]],
            f"{first[2]}: {first[3]}\n{second[2]}: {second[3]}",
            "cross-document", identity, index_identity,
            [first[0].relative_to(ROOT).as_posix(), second[0].relative_to(ROOT).as_posix()],
        ))

    unrelated = [
        "What is the private policy for interplanetary espresso machines?",
        "Which unreleased payroll password is used by the finance team?",
        "What is the weather on a fictional planet tomorrow?",
        "Who won a game that is not mentioned in the local corpus?",
        "How should a submarine repair a quantum coffee grinder?",
        "What is the secret customer database retention rule?",
        "Which medical diagnosis does the documentation assign to the reader?",
        "What is the current exchange rate for an imaginary currency?",
        "What is the private source code of an unrelated vendor?",
        "Tell me a joke unrelated to the documentation.",
    ]
    for offset, question in enumerate(unrelated, start=1):
        rows.append(_case(
            f"cand-unanswerable-{offset:03d}", question, [], "", "unanswerable",
            identity, index_identity, [],
        ))
    if len(rows) != 100:
        raise AssertionError(f"expected 100 candidates, got {len(rows)}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="data/processed/web")
    parser.add_argument("--output", default="benchmarks/candidates.jsonl")
    args = parser.parse_args()
    corpus_root = (ROOT / args.corpus).resolve()
    rows = build_candidates(corpus_root)
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "count": len(rows), "categories": COUNTS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
