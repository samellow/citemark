"""Uploaded files (PRD 5.1): PDF, Markdown or HTML, read into the same form as a crawled page."""

from __future__ import annotations

import io
import re
from pathlib import PurePath

import pypdf
from pypdf.errors import PdfReadError

from citemark.ingest.extract import Extracted, ExtractError, extract_html

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
SUFFIXES = (".pdf", ".md", ".markdown", ".html", ".htm")
# PDF text comes as lines with no blank line between paragraphs. A line that ends a sentence,
# followed by one that starts a new one, is taken as a paragraph break.
PARAGRAPH_BREAK = re.compile(r"(?<=[.!?:])\n(?=[A-Z0-9•\-])")


def _markdown_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
    return match.group(1).strip() if match else fallback


def extract_pdf(data: bytes, name: str) -> Extracted:
    """Each page becomes a section headed "Page N", so a cited passage says where it is."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractError(f"{name} is password-protected, so it can't be read.")
        title = ((reader.metadata.title if reader.metadata else None) or "").strip() or PurePath(name).stem
        sections = [f"# {title}"]
        for number, page in enumerate(reader.pages, 1):
            text = "\n".join(line.strip() for line in (page.extract_text() or "").splitlines())
            text = PARAGRAPH_BREAK.sub("\n\n", text).strip()
            if text:
                sections.append(f"## Page {number}\n\n{text}")
    except PdfReadError as exc:
        raise ExtractError(f"{name} isn't a PDF that can be read.") from exc
    if len(sections) == 1:
        raise ExtractError(f"No text was found in {name}. It may be scanned images, which aren't read.")
    return Extracted(title, "\n\n".join(sections))


def extract_file(name: str, data: bytes) -> Extracted:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractError(f"{name} is larger than {MAX_UPLOAD_BYTES // 2**20} MB.")
    suffix = PurePath(name).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(data, name)
    text = data.decode("utf-8", errors="replace")
    if suffix in (".md", ".markdown"):
        if not text.strip():
            raise ExtractError(f"{name} is empty.")
        return Extracted(_markdown_title(text, PurePath(name).stem), text)
    if suffix in (".html", ".htm"):
        extracted = extract_html(text)
        return extracted if extracted.title else Extracted(PurePath(name).stem, extracted.markdown, extracted.anchors)
    raise ExtractError(f"{name} isn't a PDF, Markdown or HTML file.")
