"""领域模型：文档、分块、证据、答案。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """原始文档（一页/一篇）。"""
    id: str
    title: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """分块后的最小检索单元。"""
    id: str
    doc_id: str
    title: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)
    source: str = ""  # 来源说明，如"论文 xxx / 章节 3"

    @property
    def evidence(self) -> str:
        return self.text


class Evidence(BaseModel):
    """一次检索返回的命中证据。"""
    chunk: Chunk
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0


class Answer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    refused: bool = False
    trace_id: str = ""
    evidences: list[Evidence] = Field(default_factory=list)