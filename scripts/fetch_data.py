"""数据获取：从公开源拉取语料/评测集。

用法（建议先跑，离线后不再需要网络）：
    python -m scripts.fetch_data --mlqa 20 --arxiv 0

产出：
  data/raw/mlqa_en_zh.jsonl   # 英-中跨语言 QA 评测子集（含 context/query/答案）
  说明：arXiv 抓取需网络与 ardag；未配置时不拉取。MD 语料请自行放入 data/raw/docs/。
"""
from __future__ import annotations

import argparse
import json

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DOCS = RAW / "docs"


def fetch_mlqa(n: int = 20) -> Path:
    """从 HuggingFace xtreme/MLQA.en.zh 取前 n 条评测样本（含中文答案标注）。"""
    from datasets import load_dataset

    ds = load_dataset("google/xtreme", "MLQA.en.zh", split="test")
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "mlqa_en_zh.jsonl"
    rows = []
    for item in ds.select(range(min(n, len(ds)))):
        rows.append({
            "query": item["question"],
            "context": item["context"],
            "answers": item["answers"],
            "gold_ids": item["id"],
        })
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlqa", type=int, default=20, help="MLQA 评测样本数")
    args = parser.parse_args()

    DOCS.mkdir(parents=True, exist_ok=True)
    print(f"[fetch] 语料目录: {DOCS}  (放入 md/txt/pdf/html 即可作为知识库)")
    if args.mlqa > 0:
        p = fetch_mlqa(args.mlqa)
        print(f"[fetch] MLQA 评测子集已写入: {p}")

    # arxiv 抓取示例（需 pip install ardage，可选）
    # from ardage import PaperDownloader; ... 见 README「数据来源」章节


if __name__ == "__main__":
    main()