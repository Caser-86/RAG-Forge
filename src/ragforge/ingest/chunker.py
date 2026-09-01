"""摄取：文件解析 → 文档 → 语义分块。"""
from __future__ import annotations

from pathlib import Path

from ..models import Chunk, Document


def load_documents(paths: list[Path]) -> list[Document]:
    """加载 md / txt / pdf / html 到 Document 列表。"""
    docs: list[Document] = []
    for p in paths:
        if not p.exists():
            continue
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


class Chunker:
    """字符级分块 + overlap；chunk_size 可配置用于消融实验。"""

    def __init__(self, size: int = 800, overlap: int = 100):
        self.size = size
        self.overlap = overlap

    def chunk(self, doc: Document) -> list[Chunk]:
        text = doc.text
        chunks: list[Chunk] = []
        start = 0
        n = len(text)
        idx = 0
        while start < n:
            end = min(start + self.size, n)
            piece = text[start:end]
            if piece.strip():
                meta = dict(doc.meta)
                meta["chunk_index"] = idx
                chunks.append(Chunk(
                    id=f"{doc.id}::c{idx}",
                    doc_id=doc.id,
                    title=doc.title,
                    text=piece,
                    meta=meta,
                    source=f"{doc.title} [段 {idx + 1}]",
                ))
                idx += 1
            if end >= n:
                break
            start = end - self.overlap
        return chunks