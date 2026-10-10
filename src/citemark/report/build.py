"""The report's one file (PRD 5.5): opens offline, reads without JavaScript, prints in light.

- **Inlined:** IBM's Latin-1 Plex files as data URIs (UI kit G7), then `tokens.css`,
  `citemark.css`, `record.css` and `report.css`, the print footer, and `report.js`. Nothing is
  fetched, so the file can be forwarded as an attachment and opened anywhere.
- **The print footer** goes in the page's bottom margin with the page number and count, which
  Chromium browsers print (UI kit G5). Elsewhere it prints without them.
- **The record:** each build adds a `report` row with its runs and your fix-plan estimates.
"""

from __future__ import annotations

import base64
import os
import re
import tempfile
from functools import cache
from pathlib import Path

from markupsafe import Markup
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Report as ReportRow
from citemark.report.render import environment
from citemark.report.view import Report

KIT = Path(__file__).resolve().parents[3]
STATIC = KIT / "static"
FACES = (  # family, weight and file: the five faces the type roles use (static/fonts/README.md)
    ("IBM Plex Sans Condensed", 600, "IBMPlexSansCondensed-SemiBold-Latin1.woff2"),
    ("IBM Plex Sans", 400, "IBMPlexSans-Regular-Latin1.woff2"),
    ("IBM Plex Sans", 600, "IBMPlexSans-SemiBold-Latin1.woff2"),
    ("IBM Plex Mono", 400, "IBMPlexMono-Regular-Latin1.woff2"),
    ("IBM Plex Mono", 500, "IBMPlexMono-Medium-Latin1.woff2"),
)
SHEETS = ("tokens.css", "citemark.css", "record.css", "report.css")
FONT_FACE = re.compile(r"@font-face\s*\{[^}]*\}\s*")  # citemark.css's own, which load files beside it


def css_string(text: str) -> str:
    """Text as a CSS string, safe inside a <style> element whatever it holds."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    for char in "\n\r\f":  # each would end a CSS string
        escaped = escaped.replace(char, f"\\{ord(char):X} ")
    return '"' + escaped.replace("<", "\\3C ").replace(">", "\\3E ") + '"'


@cache
def stylesheet() -> str:
    faces = []
    for family, weight, name in FACES:
        data = base64.b64encode((STATIC / "fonts" / "latin1" / name).read_bytes()).decode("ascii")
        faces.append(
            f'@font-face {{ font-family: "{family}"; font-weight: {weight}; font-style: normal; font-display: swap; '
            f'src: url("data:font/woff2;base64,{data}") format("woff2"); }}'
        )
    sheets = [FONT_FACE.sub("", (STATIC / name).read_text(encoding="utf-8")) for name in SHEETS]
    return "\n".join(faces + sheets)


@cache
def script() -> str:
    return (STATIC / "report.js").read_text(encoding="utf-8")


def _page(footer: tuple[str, str, str]) -> str:
    before, middle, after = (css_string(part) for part in footer)
    return (
        "@page { margin: 16mm 14mm 20mm; @bottom-center { "
        f"content: {before} counter(page) {middle} counter(pages) {after}; "
        'font-family: "IBM Plex Sans", sans-serif; font-size: 8pt; color: var(--text-muted); } }'
    )


def render(report: Report, *, theme: str | None = None, banner: str | None = None) -> str:
    """The report as one HTML document. `theme` forces light or dark, as the gallery shows it."""
    css, js = stylesheet() + "\n" + _page(report.footer), script()
    if "</" in css or "</script" in js.lower():  # either would end its element early
        raise ValueError("An inlined stylesheet or script holds a closing tag.")
    return (
        environment()
        .get_template("report.html")
        .render(report=report, css=Markup(css), script=Markup(js), theme=theme, banner=banner)
    )


def write(html: str, out: Path) -> None:
    """Write the file whole or not at all, so a failed build never leaves half a report."""
    out.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(html)
        os.replace(temporary, out)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


async def save(session: AsyncSession, report: Report, out: Path) -> ReportRow:
    """Record the build: its kind, every run it covers, and your estimates."""
    row = ReportRow(
        kind=report.kind,
        test_run_ids=list(report.run_ids),
        fix_plan=report.fix_estimates,
        html_path=str(out),
    )
    session.add(row)
    await session.flush()
    return row
