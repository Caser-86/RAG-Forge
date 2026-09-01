"""摄取脚本：把 data/raw/docs 下的文档索引进引擎。

用法：
    python -m scripts.ingest_docs data/raw/docs
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import get_settings          # noqa: E402
from ragforge.observability import setup_logging  # noqa: E402
from ragforge.pipeline import RAGForge             # noqa: E402

setup_logging()


def main(doc_dir: str) -> None:
    settings = get_settings()
    engine = RAGForge(settings)
    paths = [p for p in Path(doc_dir).rglob("*") if p.suffix.lower() in (".md", ".txt", ".pdf", ".html", ".htm")]
    if not paths:
        print(f"未发现文档于 {doc_dir}（支持 md/txt/pdf/html）")
        return
    n = engine.ingest_files([str(p) for p in paths])
    print(f"已索引 {n} 个分块。示例查询：python -m scripts.smoke")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/docs")