from ragforge.models import Chunk
from ragforge.retriever.sparse import BM25Index, TOKENIZER_VERSION, tokenize


def _chunk(doc_id: str, text: str) -> Chunk:
    return Chunk(id=doc_id, doc_id=doc_id, title=doc_id, text=text)


def test_tokenizer_keeps_error_codes_and_adds_cjk_unigrams_and_bigrams():
    tokens = tokenize("ERR_CONNECTION_RESET HTTP_404 中文检索")

    assert TOKENIZER_VERSION
    assert "err_connection_reset" in tokens
    assert "http_404" in tokens
    assert {"中", "文", "检", "索", "中文", "文检", "检索"}.issubset(tokens)


def test_bm25_handles_empty_token_corpus_and_zero_score_matches():
    empty = BM25Index([_chunk("punct", "!!! ???")])
    assert empty.search("anything", 5) == []

    same = BM25Index([_chunk("a", "same"), _chunk("b", "same")])
    hits = same.search("same", 5)
    assert {chunk.id for chunk, _score in hits} == {"a", "b"}


def test_bm25_top_k_zero_returns_no_results():
    index = BM25Index([_chunk("a", "keyword")])

    assert index.search("keyword", 0) == []
