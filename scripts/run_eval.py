"""评测脚本：对 MLQA 子集跑检索/生成指标，并做检索策略消融。

用法：
    python -m scripts.run_eval data/raw/mlqa_en_zh.jsonl 10   # 10 为 k（召回/命中 top-k）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragforge.config import Settings, get_settings            # noqa: E402
from ragforge.evaluation import (                    # noqa: E402
    GenerationReport, RetrievalReport, citation_support,
    faithfulness_proxy, hit_at_k, mrr, recall_at_k,
)
from ragforge.observability import setup_logging     # noqa: E402
from ragforge.pipeline import RAGForge               # noqa: E402

setup_logging()


def build_engine(settings: Settings, corpus: list[tuple[str, str]]) -> RAGForge:
    from ragforge.models import Chunk

    engine = RAGForge(settings)
    chunks = [Chunk(id=f"doc{i}", doc_id=f"doc{i}", title=f"{title}",
                    text=text, source=title)
              for i, (title, text) in enumerate(corpus)]
    engine.ingest_chunks(chunks)
    return engine


def main(eval_file: str, k: int = 10) -> None:
    rows = [json.loads(line) for line in Path(eval_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    # 按唯一 context 去重建语料，gold 指向 query 所属 context：
    # 避免 MLQA 同一篇文章含多个问题时，相同段落被重复索引为不同 id，
    # 造成「内容其实命中却被判不中」的假阴性。
    ctx_to_id: dict[str, str] = {}
    corpus: list[tuple[str, str]] = []
    for r in rows:
        if r["context"] not in ctx_to_id:
            ctx_to_id[r["context"]] = f"doc{len(corpus)}"
            corpus.append((ctx_to_id[r["context"]], r["context"]))
    gold_for_q = {i: {ctx_to_id[r["context"]]} for i, r in enumerate(rows)}

    base = get_settings()

    # ---- 消融：纯稠密 vs 稠密+BM25(RRF)；沿用 env 的嵌入(bge)/重排设置 ----
    for mode in ("dense_only", "hybrid"):
        s = base.model_copy(deep=True)
        s.sparse_top_k = 15 if mode == "hybrid" else 0
        engine = build_engine(s, corpus)
        rep = RetrievalReport()
        for i, r in enumerate(rows):
            evs = engine.retrieve_only(r["query"])
            rep.hit_at_k.append(hit_at_k(evs, gold_for_q[i], k))
            rep.recall_at_k.append(recall_at_k(evs, gold_for_q[i], k))
            rep.mrr_list.append(mrr(evs, gold_for_q[i]))
        print(f"\n=== 检索策略: {mode} ===")
        print(rep.summarize(k=k))

    # ---- 生成层指标（忠实度代理，用 env 的方舟 LLM）----
    engine = build_engine(base, corpus)
    greport = GenerationReport()
    for i, r in enumerate(rows):
        ans = engine.ask(r["query"])
        if ans.refused:
            greport.refused += 1
        else:
            ev_texts = [e.chunk.text for e in ans.evidences]
            greport.faithfulness.append(faithfulness_proxy(ans.answer, ev_texts))
            greport.citation_support.append(citation_support(ans.answer, ev_texts))
        greport.total += 1
    print("\n=== 生成层 ===")
    print(greport.summarize())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/raw/mlqa_en_zh.jsonl",
         int(sys.argv[2]) if len(sys.argv) > 2 else 10)