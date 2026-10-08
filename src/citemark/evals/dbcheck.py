"""Expected sources against the indexed passages: `citemark test check --against-db` (T6).

The snapshot check proved each quote was in the help center when the questions were frozen.
This one proves it made it into the database: every expected quote is in the live passages
under its section. Otherwise a question could fail because a passage was never indexed, which
the report would blame on the bot.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Chunk, Document
from citemark.evals.checks import Finding
from citemark.evals.snapshot import normalize
from citemark.evals.testset import TestSetFile
from citemark.ingest.chunk import PATH_SEPARATOR


async def check_sources_in_db(test_set: TestSetFile, session: AsyncSession) -> list[Finding]:
    found: list[Finding] = []
    for question in test_set.questions:
        before = len(found)
        for source in question.expected_sources:
            rows = await session.execute(
                select(Chunk.heading_path, Chunk.blocks)
                .join(Document, Chunk.document_id == Document.id)
                .where(
                    Document.url.in_({source.url, source.url.rstrip("/")}),
                    Document.status == "active",
                    Chunk.retired_at.is_(None),
                )
                .order_by(Document.url, Chunk.position)
            )
            passages = rows.all()
            if not passages:
                found.append(Finding("indexed", f"{source.url} has no passages in the database", question.id))
                continue
            section = normalize(source.section)
            under = [blocks for path, blocks in passages if section in map(normalize, path.split(PATH_SEPARATOR))]
            if not under:
                message = f'no passage under "{source.section}" in {source.url}'
                found.append(Finding("indexed", message, question.id))
                continue
            text = normalize(" ".join(block for blocks in under for block in blocks))
            if normalize(source.quote) not in text:
                message = f'the quote isn\'t in the passages under "{source.section}": "{source.quote[:60]}"'
                found.append(Finding("indexed", message, question.id))
        # Two expected sources in one article would otherwise say the same thing twice
        found[before:] = list(dict.fromkeys(found[before:]))
    return found
