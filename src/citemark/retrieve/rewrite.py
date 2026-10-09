"""Follow-up questions, rewritten to stand alone before searching (PRD 5.2).

"How do I undo it?" finds nothing on its own, so when there's earlier conversation, Claude
Haiku 4.5 rewrites it from the last 3 exchanges with `prompts/rewrite.v1.md` (content spec
4.3): "How do I undo deleting a message?". A first message is searched as it is, with no call.

If the call fails, the message is searched as it is: a weaker search beats no answer. The log
records that it failed, never what was asked (PRD 5.11).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import anthropic
import structlog

from citemark import prompts

log = structlog.get_logger()

MODEL = "claude-haiku-4-5"
PROMPT = "rewrite.v1"
EXCHANGES = 3  # a question and its answer make one
MAX_TOKENS = 200
SPEAKERS = {"user": "Customer", "assistant": "Support bot"}


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class Rewritten:
    question: str
    called: bool  # whether the model was asked; False for a first message or a failed call
    input_tokens: int = 0
    output_tokens: int = 0


def _request(history: Sequence[Turn], message: str) -> list[dict]:
    transcript = "\n".join(f"{SPEAKERS[turn.role]}: {turn.text}" for turn in history[-2 * EXCHANGES :])
    content = f"<conversation>\n{transcript}\n</conversation>\n\n<latest_message>\n{message}\n</latest_message>"
    return [{"role": "user", "content": content}]


async def rewrite(client: anthropic.AsyncAnthropic, history: Sequence[Turn], message: str) -> Rewritten:
    if not history:
        return Rewritten(message, called=False)
    try:
        reply = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,  # anthropic 1.x takes no temperature: the model's default is used
            system=prompts.load(PROMPT),
            messages=_request(list(history), message),
        )
    except anthropic.APIError as exc:
        log.warning("rewrite_failed", model=MODEL, error=type(exc).__name__)
        return Rewritten(message, called=False)
    text = " ".join(block.text for block in reply.content if block.type == "text").strip().strip('"')
    question = text if text and reply.stop_reason == "end_turn" else message
    return Rewritten(question, True, reply.usage.input_tokens, reply.usage.output_tokens)
