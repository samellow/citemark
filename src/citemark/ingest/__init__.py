"""Ingestion (PRD 5.1): crawl a help center, keep what a reader sees, split it into passages
and embed them. A re-index adds new passages and retires the old ones, never editing any."""


class IngestError(Exception):
    """A source couldn't be read. The message is one plain sentence, shown as it is."""
