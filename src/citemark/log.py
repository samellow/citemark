"""Structured logs: one JSON object per line (implementation plan, conventions).

Log event names, IDs and counts. Never a visitor's question text, and never an IP address
(PRD 5.11).
"""

from __future__ import annotations

import logging

import structlog


def configure(level: int = logging.INFO) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
