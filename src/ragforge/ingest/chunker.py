"""摄取：文件解析 → 文档 → 语义分块。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..models import Chunk, Document


# Changing this value invalidates persisted indexes because chunk boundaries
# are part of the retrieval identity.
CHUNK_ALGORITHM_VERSION = "heading-window-v2"


def load_documents(paths: list[Path]) -> list[Document]:
    """加载 md / txt / pdf / html 到 Document 列表。"""
    docs: list[Document] = []
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"文档路径不存在: {p}")
        if p.suffix.lower() in (".md", ".txt"):
            title = p.stem
            docs.append(Document(id=str(p), title=title, text=p.read_text(encoding="utf-8", errors="ignore")))
        elif p.suffix.lower() == ".pdf":
            docs.extend(_load_pdf(p))
        elif p.suffix.lower() in (".html", ".htm"):
            docs.append(_load_html(p))
    return docs


def _load_pdf(path: Path) -> list[Document]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    out: list[Document] = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if text:
            out.append(Document(
                id=f"{path}#p{i}",
                title=f"{path.stem} · 第{i + 1}页",
                text=text,
                meta={"type": "pdf", "page": i},
            ))
    return out


def _load_html(path: Path) -> Document:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return Document(
        id=str(path),
        title=soup.title.get_text(strip=True) if soup.title else path.stem,
        text=soup.get_text("\n", strip=True),
        meta={"type": "html"},
    )


_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass
class _Section:
    heading_path: list[str]
    heading_lines: list[str]
    paragraphs: list[str] = field(default_factory=list)


class Chunker:
    """按标题/段落优先、字符预算兜底的可解释分块器。"""

    def __init__(self, size: int = 2200, overlap: int = 200, strategy: str = "heading_chars"):
        if size <= 0:
            raise ValueError("chunk size must be positive")
        if overlap < 0 or overlap >= size:
            raise ValueError("chunk overlap must be between 0 and size - 1")
        if strategy not in {"heading_chars", "char"}:
            raise ValueError("chunk strategy must be heading_chars or char")
        self.size = size
        self.overlap = overlap
        self.strategy = strategy

    def chunk(self, doc: Document) -> list[Chunk]:
        if self.strategy == "char":
            return self._chunk_char(doc)

        sections = self._parse_sections(doc.text)
        chunks: list[Chunk] = []
        for section in sections:
            prefix = "\n".join(section.heading_lines)
            body_budget = max(1, self.size - len(prefix) - 2)
            section_body = "\n\n".join(section.paragraphs)
            for body_window in self._body_windows(section_body, body_budget):
                text = f"{prefix}\n\n{body_window}" if prefix else body_window
                chunks.append(self._make_chunk(doc, text.strip(), section.heading_path, len(chunks)))
        return chunks

    def _chunk_char(self, doc: Document) -> list[Chunk]:
        text = doc.text
        chunks: list[Chunk] = []
        start = 0
        n = len(text)
        idx = 0
        while start < n:
            end = min(start + self.size, n)
            piece = text[start:end]
            if piece.strip():
                chunks.append(self._make_chunk(doc, piece, [], idx))
                idx += 1
            if end >= n:
                break
            start = end - self.overlap
        return chunks

    def _make_chunk(self, doc: Document, text: str, heading_path: list[str], index: int) -> Chunk:
        meta = dict(doc.meta)
        meta["chunk_index"] = index
        meta.setdefault("document_version", doc.version)
        meta.setdefault("active", doc.active)
        meta.setdefault("source_type", doc.source_type)
        meta.setdefault("category", doc.category)
        meta.setdefault("language", doc.language)
        meta.setdefault("content_hash", doc.content_hash)
        meta.setdefault("retrieved_at", doc.retrieved_at)
        return Chunk(
            id=self._chunk_id(doc, index),
            doc_id=doc.id,
            title=doc.title,
            text=text,
            meta=meta,
            source=f"{doc.title} [段 {index + 1}]",
            source_url=doc.source_url,
            heading_path=list(heading_path),
            chunk_index=index,
        )

    def _chunk_id(self, doc: Document, index: int) -> str:
        return f"{doc.id}::v{doc.version}::{self.strategy}-{self.size}-{self.overlap}::c{index}"

    @staticmethod
    def _parse_sections(text: str) -> list[_Section]:
        stack: list[tuple[int, str]] = []
        sections: list[_Section] = [_Section([], [])]
        paragraph_lines: list[str] = []
        fence: str | None = None

        def flush_paragraph() -> None:
            value = "\n".join(paragraph_lines).strip()
            paragraph_lines.clear()
            if value:
                sections[-1].paragraphs.append(value)

        for line in text.splitlines():
            fence_match = _FENCE_RE.match(line)
            if fence is not None:
                paragraph_lines.append(line)
                if fence_match and fence_match.group(1)[0] == fence[0]:
                    fence = None
                continue
            if fence_match:
                paragraph_lines.append(line)
                fence = fence_match.group(1)
                continue

            heading_match = _HEADING_RE.match(line)
            if heading_match:
                flush_paragraph()
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip().rstrip("#").rstrip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, title))
                sections.append(_Section(
                    heading_path=[item[1] for item in stack],
                    heading_lines=["#" * item[0] + " " + item[1] for item in stack],
                ))
                continue

            if not line.strip():
                flush_paragraph()
            else:
                paragraph_lines.append(line.rstrip())
        flush_paragraph()
        return [section for section in sections if section.paragraphs]

    def _body_windows(self, body: str, budget: int) -> list[str]:
        """切出有重叠的连续正文窗口，不丢弃窗口尾部内容。"""
        if not body.strip():
            return []
        windows: list[str] = []
        start = 0
        while start < len(body):
            end = min(start + budget, len(body))
            window = body[start:end]
            if window.strip():
                windows.append(window)
            if end >= len(body):
                break
            start = end - self.overlap
        return windows
