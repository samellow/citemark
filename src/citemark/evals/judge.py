"""The judge (PRD 5.4): Claude Opus 5.5 grades an answer against the rubric in
`prompts/judge.v1.md` (content spec 4.4), with structured output: a verdict, the missing key
facts, the contradictions and a one-sentence reason.

It reads the question (marked with its type, so the rubric's partial rules apply), the expected
key facts, the quoted help-center text of the expected sources, and the answer as the visitor
saw it, gap line included. It runs at high effort (PRD Q14), the setting T2 checked.

Only answers are judged. A decline, a clarifying question or an error isn't sent: whether it
was right is scored mechanically, so the judge's agreement with human grading is measured on
answers alone.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import anthropic

from citemark import prompts

MODEL = "claude-opus-5-5"
RUBRIC = "judge.v1"
EFFORT = "high"  # PRD Q14
MAX_TOKENS = 16_000  # room for thinking at high effort; the SDK refuses unstreamed calls much over 21K
NOT_PARTIAL = "the part of the question it doesn't cover"  # fills {uncovered_part} when the rule doesn't apply
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["correct", "incorrect"]},
        "missing_facts": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "missing_facts", "contradictions", "reason"],
    "additionalProperties": False,
}


class JudgeError(Exception):
    """The judge gave no usable verdict. The message is one plain sentence. A reply that came
    back unusable was still billed, so it carries its tokens."""

    def __init__(self, message: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens, self.output_tokens = input_tokens, output_tokens


@dataclass(frozen=True)
class Verdict:
    verdict: str  # correct or incorrect
    missing_facts: list[str]
    contradictions: list[str]
    reason: str
    input_tokens: int = 0
    output_tokens: int = 0
    output: dict[str, Any] = field(default_factory=dict)  # the judge's whole reply, as stored


def _request(
    *,
    question: str,
    qtype: str,
    expected_answer: Sequence[str],
    sources: Sequence[Mapping[str, str]],
    answer: str,
    uncovered_part: str | None,
) -> tuple[str, list[dict[str, str]]]:
    rubric = prompts.load(RUBRIC).replace("{uncovered_part}", uncovered_part or NOT_PARTIAL)
    facts = "\n".join(f"- {fact}" for fact in expected_answer)
    quotes = "\n".join(f'- "{source["quote"]}" ({source["url"]}, {source["section"]})' for source in sources)
    content = (
        f'<question type="{qtype}">\n{question}\n</question>\n\n'
        f"<expected_answer>\n{facts}\n</expected_answer>\n\n"
        f"<help_center_quotes>\n{quotes}\n</help_center_quotes>\n\n"
        f"<answer>\n{answer}\n</answer>"
    )
    return rubric, [{"role": "user", "content": content}]


async def judge(
    client: anthropic.AsyncAnthropic,
    *,
    question: str,
    qtype: str,
    expected_answer: Sequence[str],
    sources: Sequence[Mapping[str, str]],
    answer: str,
    uncovered_part: str | None = None,
) -> Verdict:
    system, messages = _request(
        question=question,
        qtype=qtype,
        expected_answer=expected_answer,
        sources=sources,
        answer=answer,
        uncovered_part=uncovered_part,
    )
    try:
        reply = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except anthropic.APIError as exc:
        raise JudgeError(f"The call to the judge failed ({type(exc).__name__}).") from exc
    billed = (reply.usage.input_tokens, reply.usage.output_tokens)
    if reply.stop_reason != "end_turn":
        raise JudgeError(f"The judge stopped early ({reply.stop_reason}).", *billed)
    text = "".join(block.text for block in reply.content if block.type == "text")
    try:
        output = json.loads(text)
        verdict = Verdict(
            output["verdict"],
            list(output["missing_facts"]),
            list(output["contradictions"]),
            output["reason"],
            reply.usage.input_tokens,
            reply.usage.output_tokens,
            output,
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise JudgeError("The judge's reply wasn't the verdict it was asked for.", *billed) from exc
    if verdict.verdict not in ("correct", "incorrect"):
        raise JudgeError(f"The judge's verdict was {verdict.verdict!r}.", *billed)
    return verdict
