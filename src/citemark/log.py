"""Structured logs: one JSON object per line (implementation plan, conventions).

Log event names, IDs and counts. Never a visitor's question text, and never an IP address
(PRD 5.11).

A traceback keeps each frame's file, line and function, but not its local variables, which is
structlog's default. Locals hold request headers and settings, so they'd put API keys in the
host's logs. That happened on the first live crawl (T6) before this was turned off.
"""

from __future__ import annotations

import logging

import structlog
from structlog.tracebacks import ExceptionDictTransformer

TRACEBACKS = structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False))


def configure(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            TRACEBACKS,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
