"""Uploaded PDF, Markdown and HTML files (PRD 5.1), and a PDF at a single address."""

import httpx2
import pytest

from citemark.ingest.chunk import PATH_SEPARATOR, chunk_document
from citemark.ingest.crawl import Crawl, Page, SourceSpec
from citemark.ingest.extract import ExtractError
from citemark.ingest.fetch import Fetcher
from citemark.ingest.files import extract_file


def tiny_pdf(*pages: list[str]) -> bytes:
    """A small, valid PDF with a line of text per entry, built here so no binary fixture is needed.
    Objects: 1 catalog, 2 page list, 3 font, then each page's text and the page itself."""
    objects = {1: "<< /Type /Catalog /Pages 2 0 R >>", 3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    kids = []
    for n, lines in enumerate(pages):
        content, page = 4 + 2 * n, 5 + 2 * n
        stream = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
        objects[content] = f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"
        objects[page] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        kids.append(f"{page} 0 R")
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    body, offsets = b"%PDF-1.4\n", {}
    for number in sorted(objects):
        offsets[number] = len(body)
        body += f"{number} 0 obj\n{objects[number]}\nendobj\n".encode()
    xref, size = len(body), max(objects) + 1
    body += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{offsets[number]:010d} 00000 n \n".encode() for number in range(1, size))
    body += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body


HANDBOOK = tiny_pdf(
    ["Getting started.", "Install the app from your app store."],
    ["Refunds are issued within 14 days.", "Contact billing for anything else."],
)


def test_a_pdf_becomes_one_section_per_page():
    extracted = extract_file("handbook.pdf", HANDBOOK)
    assert extracted.title == "handbook"
    passages = chunk_document(extracted.title, extracted.markdown, "upload:handbook.pdf")
    assert [p.heading_path for p in passages] == [f"handbook{PATH_SEPARATOR}Page 1", f"handbook{PATH_SEPARATOR}Page 2"]
    assert "Refunds are issued within 14 days." in passages[1].text


def test_markdown_and_html_files_are_read():
    markdown = extract_file("returns.md", b"# Returns policy\n\nYou can return an unused item within 30 days.\n")
    assert markdown.title == "Returns policy"
    page = b"<html><body><article><h1>Shipping</h1><p>Orders ship within two working days of payment.</p></article>"
    html = extract_file("shipping.html", page + b"</body></html>")
    assert html.title == "Shipping" and "two working days" in html.markdown


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("notes.docx", b"PK...", "isn't a PDF, Markdown or HTML file"),
        ("empty.md", b"  \n", "is empty"),
        ("empty.html", b"", "is empty, or isn't HTML"),
        ("broken.pdf", b"%PDF-1.4 not really", "isn't a PDF that can be read"),
        ("scanned.pdf", tiny_pdf([]), "No text was found"),
    ],
)
def test_a_file_that_cant_be_read_says_why(name, data, message):
    with pytest.raises(ExtractError, match=message):
        extract_file(name, data)


async def no_wait(seconds: float) -> None:
    pass


@pytest.mark.anyio
async def test_a_single_address_can_be_a_pdf():
    def handle(request):
        if request.url.path == "/files/handbook.pdf":
            return httpx2.Response(200, headers={"content-type": "application/pdf"}, content=HANDBOOK)
        return httpx2.Response(404)

    spec = SourceSpec("url", "https://docs.example.com/files/handbook.pdf")
    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handle)) as client:
        crawl = Crawl(spec, Fetcher(client, spec.scope(), agent="CitemarkBot (+test)", interval=0, sleep=no_wait))
        [item] = [item async for item in crawl.pages()]
    assert isinstance(item, Page) and "## Page 2" in item.extracted.markdown
