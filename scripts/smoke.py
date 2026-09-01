"""离线 smoke：不依赖网络/模型，验证链路可跑。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings                       # noqa: E402
from ragforge.models import Chunk                          # noqa: E402
from ragforge.pipeline import RAGForge                     # noqa: E402

DOCS = [
    ("Transformer 科普", "Transformer 使用自注意力机制，Transformer 的核心是注意力，足以并行处理序列。"),
    ("BNF 语法", "BNF 即巴科斯范式，ANF 常被用于形式化描述程序设计语言。"),
    ("PyTorch 简介", "PyTorch 是一个开源深度学习框架，提供张量与自动求导能力。"),
]


def main() -> None:
    settings = Settings(embedder_backend="deterministic", use_rerank=False, llm_api_key="")
    engine = RAGForge(settings)
    engine.ingest_chunks([Chunk(id=f"c{i}", doc_id=f"d{i}", title=t, text=txt, source=t)
                          for i, (t, txt) in enumerate(DOCS)])
    for q in ["Transformer 的注意力机制是什么", "不相关的问题xxx"]:
        ans = engine.ask(q)
        print(f"\nQ: {q}\nA: {ans.answer[:120]}\nrefused={ans.refused}")


if __name__ == "__main__":
    main()