"""Seven Zulip articles the frozen test set doesn't use, loaded as live passages with stand-in
vectors, for tests that answer real questions from real help-center text."""

import datetime as dt
import uuid
from decimal import Decimal
from pathlib import Path

from citemark.db.models import Chunk, Document, Price, Source
from citemark.ingest.chunk import chunk_document
from citemark.testing.fakes import FakeEmbedder, fake_vector

ZULIP = Path(__file__).parents[2] / "fixtures" / "zulip" / "text"
SUBSET = {  # none of them used by the frozen test set
    "typing-notifications": "Typing notifications",
    "font-size": "Font size",
    "change-your-language": "Change your language",
    "custom-emoji": "Custom emoji",
    "email-notifications": "Email notifications",
    "topic-notifications": "Topic notifications",
    "keyboard-shortcuts": "Keyboard shortcuts",
}


async def add_zulip(session) -> dict[str, uuid.UUID]:
    """The subset's passages as live chunks, by heading path. The stand-in embedder gets a
    price of zero, since a run prices every call."""
    source = Source(kind="url", url="https://zulip.com/help/")
    session.add(source)
    await session.flush()
    ids = {}
    for slug, title in SUBSET.items():
        url = f"https://zulip.com/help/{slug}"
        document = Document(source_id=source.id, url=url, title=title, content_hash=slug)
        session.add(document)
        await session.flush()
        for passage in chunk_document(title, (ZULIP / f"{slug}.md").read_text(encoding="utf-8"), url):
            chunk = Chunk(
                document_id=document.id,
                position=passage.position,
                heading_path=passage.heading_path,
                anchor_url=passage.anchor_url,
                blocks=list(passage.blocks),
                text=passage.text,
                token_count=passage.token_count,
                embedding=fake_vector(passage.text),
            )
            session.add(chunk)
            await session.flush()
            ids[passage.heading_path] = chunk.id
    session.add(Price(model=FakeEmbedder.model, input_per_mtok=Decimal(0), effective_from=dt.date(2026, 1, 1)))
    await session.flush()
    return ids
