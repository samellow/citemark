"""The Claude adapter (PRD 5.3): passages as `search_result` blocks, decisions as tool calls.

Each passage is a `search_result` block with citations on. Its source is the article's address,
its title the heading path, and each paragraph is its own text block, so a citation names the
paragraphs it quotes. Citations stream as `citations_delta` events, and each is passed on with the
index of the passage it came from. The quoted text is copied by the API, never written by the model.

The four decision tools come from `prompts/tools.v1.json`. When the model reports a gap before any
cited text, the adapter returns a tool result and the model writes the answer in a second call
(PRD Q12). Sonnet 5.5 reported the gap first 6 times of 6 in T2, then answered 3 times of 3 once
given the result.

Caching: the tools and the system prompt are one cached prefix. In full-context mode the whole
help center opens the conversation and is cached too, so each question reads it from the cache.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from citemark import prompts
from citemark.models import (
    HISTORY_TURNS,
    AnswerRequest,
    CitationEvent,
    DecisionEvent,
    Event,
    ModelCallFailed,
    Passage,
    TextEvent,
    UsageEvent,
)
from citemark.models.registry import UnknownModel

PROMPT = "answer.v1"
TOOLS = "tools.v1"
MAX_TOKENS = 4096
CACHED = {"type": "ephemeral"}  # 5 minutes, refreshed by every read
GAP_RESULT = "Recorded."  # the tool result T2 sent after an early report_gap
# Low effort on all three (decided 2026-10-09): the setting T2 timed, at about 0.8-0.9 s to the
# first text. Haiku 5.5 runs with thinking off (PRD Q11). Sonnet 5.5 and Opus 5.5 can't turn
# thinking off, so effort is what keeps it short.
SETTINGS: dict[str, dict[str, Any]] = {
    "claude-haiku-5-5": {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}},
    "claude-sonnet-5-5": {"output_config": {"effort": "low"}},
    "claude-opus-5-5": {"output_config": {"effort": "low"}},
}
SLOT = re.compile(r"\{(\w+)\}")


def _fill(template: str, **slots: str) -> str:
    """The prompt's slots, filled in one pass. A slot without a value is an error."""

    def value(match: re.Match[str]) -> str:
        if match.group(1) not in slots:
            raise KeyError(f"The prompt needs a value for {{{match.group(1)}}}.")
        return slots[match.group(1)]

    return SLOT.sub(value, template)


def _search_results(passages: tuple[Passage, ...], *, cache: bool) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        {
            "type": "search_result",
            "source": passage.url,
            "title": passage.title,
            "content": [{"type": "text", "text": paragraph} for paragraph in passage.blocks],
            "citations": {"enabled": True},
        }
        for passage in passages
    ]
    if cache and blocks:
        blocks[-1]["cache_control"] = CACHED
    return blocks


def _messages(request: AnswerRequest) -> list[dict[str, Any]]:
    """The conversation as Claude reads it.

    Search mode: the earlier turns as text, then the passages with the question. Passages from
    earlier turns aren't sent again (PRD 5.3). Full-context mode: the help center comes first,
    so it's the same cached prefix for every question, then the turns and the question.
    """
    turns: list[tuple[str, list[dict[str, Any]]]] = []
    if request.full_context:
        turns.append(("user", _search_results(request.passages, cache=True)))
    for turn in request.history[-HISTORY_TURNS:]:
        if turn.text.strip():  # the API refuses an empty text block
            turns.append((turn.role, [{"type": "text", "text": turn.text}]))
    passages = [] if request.full_context else _search_results(request.passages, cache=False)
    turns.append(("user", [*passages, {"type": "text", "text": request.question}]))

    messages: list[dict[str, Any]] = []
    for role, content in turns:
        if messages and messages[-1]["role"] == role:  # the API wants the roles to alternate
            messages[-1]["content"].extend(content)
        elif messages or role == "user":  # and the conversation to start with the visitor
            messages.append({"role": role, "content": list(content)})
    return messages


def _replay(block: Any) -> dict[str, Any] | None:
    """A block of the reply, sent back as it came for the second call. Thinking blocks must
    come back unchanged on the 5.5 models. A blank text block is refused by the API."""
    if block.type == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if block.type == "redacted_thinking":
        return {"type": "redacted_thinking", "data": block.data}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    if block.type == "text" and block.text.strip():
        return {"type": "text", "text": block.text}
    return None


class ClaudeAnswerer:
    """Answers with one Claude model, for one company's help center."""

    def __init__(
        self, client: anthropic.AsyncAnthropic, model: str, *, company: str, bot_name: str | None = None
    ) -> None:
        if model not in SETTINGS:
            known = ", ".join(SETTINGS)
            raise UnknownModel(f"{model} isn't an answer model. The answer models are {known}.")
        self.client = client
        self.model = model
        self.company = company
        self.prompt_version = f"{PROMPT}+{TOOLS}"
        bot_name = bot_name or f"{company} Help"  # content spec 10
        self.system = _fill(prompts.load(PROMPT), bot_name=bot_name, company=company)
        self.tools = [
            {**tool, "description": _fill(tool["description"], company=company)} for tool in prompts.load_tools(TOOLS)
        ]

    def request(self, request: AnswerRequest) -> dict[str, Any]:
        """The first call's parameters. Removing a tool changes the cached prefix, which only
        happens after a clarifying question."""
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": self.system, "cache_control": CACHED}],
            "tools": [tool for tool in self.tools if tool["name"] in request.tools],
            "messages": _messages(request),
            **SETTINGS[self.model],
        }

    async def count_tokens(self, request: AnswerRequest) -> int:
        """The first call's input tokens, from Anthropic's counting endpoint, which costs nothing.
        Full-context mode checks the window with it, not with the passages' estimates (PRD 5.2)."""
        params = self.request(request)
        try:
            counted = await self.client.messages.count_tokens(
                model=params["model"], system=params["system"], tools=params["tools"], messages=params["messages"]
            )
        except anthropic.APIError as exc:
            raise ModelCallFailed(f"Counting tokens for {self.model} failed ({type(exc).__name__}).") from exc
        return counted.input_tokens

    async def stream(self, request: AnswerRequest) -> AsyncIterator[Event]:
        params = self.request(request)
        blocks = 0  # text blocks so far, across both calls
        cited = False
        for call in (1, 2):
            began: Any = None  # the call's usage as it began, so a call that fails partway still counts
            written = 0
            try:
                async with self.client.messages.stream(**params) as stream:
                    numbers: dict[int, int] = {}  # this call's block index: the reply's text block number
                    async for event in stream:
                        if event.type == "message_start":
                            began = event.message.usage
                        elif event.type == "message_delta" and event.usage.output_tokens is not None:
                            written = event.usage.output_tokens
                        elif event.type == "content_block_start" and event.content_block.type == "text":
                            numbers[event.index] = blocks
                            blocks += 1
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta" and delta.text:
                                yield TextEvent(numbers[event.index], delta.text)
                            elif delta.type == "citations_delta" and delta.citation.type == "search_result_location":
                                cited = True
                                found = delta.citation
                                yield CitationEvent(
                                    numbers[event.index],
                                    found.search_result_index,
                                    found.cited_text,
                                    found.start_block_index,
                                    found.end_block_index,
                                )
                        elif event.type == "content_block_stop" and event.content_block.type == "tool_use":
                            yield DecisionEvent(event.content_block.name, dict(event.content_block.input))
                    message = await stream.get_final_message()
            except anthropic.APIError as exc:
                if began is not None:  # the tokens read before the failure are billed all the same
                    yield UsageEvent(
                        self.model,
                        began.input_tokens,
                        written or began.output_tokens,
                        began.cache_read_input_tokens or 0,
                        began.cache_creation_input_tokens or 0,
                        None,
                    )
                raise ModelCallFailed(f"The call to {self.model} failed ({type(exc).__name__}).") from exc

            usage = message.usage
            yield UsageEvent(
                self.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.cache_read_input_tokens or 0,
                usage.cache_creation_input_tokens or 0,
                message.stop_reason,
            )
            called = [block for block in message.content if block.type == "tool_use"]
            gap_first = message.stop_reason == "tool_use" and {block.name for block in called} == {"report_gap"}
            if call == 2 or cited or not gap_first:
                return
            replayed = [block for block in map(_replay, message.content) if block is not None]
            results = [{"type": "tool_result", "tool_use_id": block.id, "content": GAP_RESULT} for block in called]
            params = {
                **params,
                "messages": [
                    *params["messages"],
                    {"role": "assistant", "content": replayed},
                    {"role": "user", "content": results},
                ],
            }
