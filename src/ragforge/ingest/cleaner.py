"""HTML 正文清洗与来源元数据保留。"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast

from bs4 import BeautifulSoup, NavigableString, Tag


CLEANER_VERSION = "html-markdown-v1"
_LOGIN_RE = re.compile(r"\b(sign\s*in|log\s*in|login|authenticate|授权登录)\b", re.I)
_TEMPLATE_RE = re.compile(r"(enable javascript|javascript is required|page not found|access denied)", re.I)
_UNWANTED_RE = re.compile(r"(cookie|consent|banner|breadcrumb|pagination|previous|next|skip-link)", re.I)


@dataclass
class CleanResult:
    status: str
    reason: str | None = None
    title: str = ""
    text: str = ""
    content_hash: str = ""
    source_url: str = ""
    retrieved_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def clean_html(
    html: str | bytes,
    source_url: str,
    *,
    response_status: int = 200,
    retrieved_at: str | None = None,
    source_meta: dict[str, Any] | None = None,
) -> CleanResult:
    """优先使用 trafilatura，失败或输出缺少结构时回退到 BeautifulSoup。"""
    if response_status in {401, 403, 404, 410}:
        return _skipped("http_status", source_url, retrieved_at, source_meta)
    raw_html = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    if not raw_html.strip():
        return _skipped("empty_body", source_url, retrieved_at, source_meta)
    soup = BeautifulSoup(raw_html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    extracted = _extract_trafilatura(raw_html)
    if not extracted or not _looks_structured(extracted):
        extracted = _extract_with_bs4(soup)
    text = normalize_text(extracted or "")
    probe = f"{title}\n{text}".strip()
    if _LOGIN_RE.search(probe) and ("sign in" in probe.lower() or "log in" in probe.lower() or len(text) < 500):
        return _skipped("login_page", source_url, retrieved_at, source_meta, title=title)
    if not text:
        return _skipped("empty_after_cleaning", source_url, retrieved_at, source_meta, title=title)
    if _TEMPLATE_RE.search(text) and len(text) < 500:
        return _skipped("template_page", source_url, retrieved_at, source_meta, title=title)
    retrieved = retrieved_at or datetime.now(timezone.utc).isoformat()
    metadata = dict(source_meta or {})
    metadata.update({
        "cleaner_version": CLEANER_VERSION,
        "response_status": response_status,
        "source_url": source_url,
        "retrieved_at": retrieved,
    })
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return CleanResult("ok", title=title or source_url, text=text, content_hash=digest,
                       source_url=source_url, retrieved_at=retrieved, meta=metadata)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                normalized.append("")
            blank = True
        else:
            normalized.append(line)
            blank = False
    return "\n".join(normalized).strip()


def _extract_trafilatura(html: str) -> str | None:
    try:
        import trafilatura
    except ImportError:
        return None
    try:
        return trafilatura.extract(
            html,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            favor_precision=True,
        )
    except (RuntimeError, TypeError, ValueError):
        return None


def _looks_structured(text: str) -> bool:
    return bool(re.search(r"(^|\n)#{1,3}\s+\S|```|(^|\n)[*-]\s+\S", text))


def _extract_with_bs4(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(["script", "style", "noscript", "template", "nav", "footer", "aside"]):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        attrs = tag.attrs or {}
        classes: Any = attrs.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        identity = f"{attrs.get('id', '')} {' '.join(str(item) for item in classes)} {attrs.get('role', '')}"
        if _UNWANTED_RE.search(identity):
            tag.decompose()
    role_main = cast(Any, soup).find(attrs={"role": "main"})
    root = soup.find("main") or soup.find("article") or role_main or soup.body or soup
    lines = _render_blocks(root)
    return "\n\n".join(line for line in lines if line.strip())


def _render_blocks(node: Tag) -> list[str]:
    output: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            value = str(child).strip()
            if value:
                output.append(value)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name.lower()
        if name in {"h1", "h2", "h3"}:
            value = _inline_text(child)
            if value:
                output.append("#" * int(name[1]) + " " + value)
        elif name == "pre":
            value = child.get_text("\n", strip=False).strip()
            if value:
                output.append("```\n" + value + "\n```")
        elif name == "li":
            value = _inline_text(child)
            if value:
                output.append("- " + value)
        elif name in {"ul", "ol"}:
            output.extend(_render_blocks(child))
        elif name in {"p", "blockquote", "dt", "dd", "figcaption"}:
            value = _inline_text(child)
            if value:
                output.append(value)
        elif name == "table":
            for row in child.find_all("tr"):
                cells = [_inline_text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
                cells = [cell for cell in cells if cell]
                if cells:
                    output.append(" | ".join(cells))
        elif name not in {"a", "span", "strong", "em", "code", "br"}:
            output.extend(_render_blocks(child))
    return output


def _inline_text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _skipped(
    reason: str,
    source_url: str,
    retrieved_at: str | None,
    source_meta: dict[str, Any] | None,
    *,
    title: str = "",
) -> CleanResult:
    metadata = dict(source_meta or {})
    metadata["cleaner_version"] = CLEANER_VERSION
    return CleanResult(
        status="skipped",
        reason=reason,
        title=title,
        source_url=source_url,
        retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat(),
        meta=metadata,
    )
