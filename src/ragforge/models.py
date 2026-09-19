"""领域模型：文档、分块、证据、答案。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Document(BaseModel):
    """原始文档（一页/一篇）。"""
    id: str
    title: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)
    source_url: str | None = None
    source_type: str = ""
    category: str = ""
    language: str = ""
    content_hash: str = ""
    version: int = 1
    retrieved_at: str | None = None
    active: bool = True


class Chunk(BaseModel):
    """分块后的最小检索单元。"""
    id: str
    doc_id: str
    title: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)
    source: str = ""  # 来源说明，如"论文 xxx / 章节 3"
    source_url: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    chunk_index: int = 0

    @property
    def evidence(self) -> str:
        return self.text


class Evidence(BaseModel):
    """一次检索返回的命中证据。"""
    chunk: Chunk
    dense_score: float | None = None
    sparse_score: float | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    score_kind: dict[str, str] = Field(default_factory=dict)


class Citation(BaseModel):
    """可供 API/UI 展示的细粒度来源引用。"""

    index: int
    document_id: str
    chunk_id: str
    title: str
    url: str | None = None
    snippet: str = ""


class Answer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    citation_details: list[Citation] = Field(default_factory=list)
    citation_invalid: bool = False
    citation_support_status: Literal["unverified", "verified"] = "unverified"
    refused: bool = False
    refusal_reason: str | None = None
    grounded: bool = False
    trace_id: str = ""
    model: str | None = None
    evidences: list[Evidence] = Field(default_factory=list)
