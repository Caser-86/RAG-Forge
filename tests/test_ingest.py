import pytest

from ragforge.ingest import Chunker


def test_chunker_rejects_non_advancing_window():
    with pytest.raises(ValueError):
        Chunker(size=100, overlap=100)


def test_chunker_rejects_non_positive_size():
    with pytest.raises(ValueError):
        Chunker(size=0, overlap=0)
