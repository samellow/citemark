"""The judge (PRD 5.4): what it's sent, and its verdicts on recorded Opus 5.5 replies.

The question and answers are written for these tests only, on an article the frozen test set
doesn't use. Re-record with: uv run pytest tests/unit/test_judge.py --record
"""

import anthropic
import httpx2
import pytest

from citemark.evals.judge import EFFORT, MODEL, NOT_PARTIAL, JudgeError, _request, judge

QUESTION = "Can I stop people from seeing when I'm typing?"
FACTS = [
    "Yes: turn off sending typing notifications",
    "Desktop/Web: gear icon, then Personal settings, then Account & privacy",
    "Under Privacy, toggle the settings that let recipients see when you're typing",
]
SOURCES = [
    {
        "url": "https://zulip.com/help/typing-notifications",
        "section": "Disable sending typing notifications",
        "quote": "you can configure Zulip to not send typing notifications",
    }
]
PARTIAL = "How do I stop people seeing that I'm typing? And can I hide it from just one person?"
UNCOVERED = "whether typing can be hidden from one specific person"


async def grade(client, answer: str, *, question: str = QUESTION, qtype: str = "answerable", uncovered=None):
    return await judge(
        client,
        question=question,
        qtype=qtype,
        expected_answer=FACTS,
        sources=SOURCES,
        answer=answer,
        uncovered_part=uncovered,
    )


def test_the_judge_reads_the_rubric_the_question_the_facts_the_quotes_and_the_answer():
    system, [message] = _request(
        question=PARTIAL, qtype="partial", expected_answer=FACTS, sources=SOURCES, answer="Turn it off.",
        uncovered_part=UNCOVERED,
    )  # fmt: skip
    assert system.startswith("You are grading a support bot's answer")
    assert f"say that the help center doesn't cover {UNCOVERED}, and" in system and "{" not in system
    content = message["content"]
    assert content.startswith(f'<question type="partial">\n{PARTIAL}\n</question>')
    assert f"- {FACTS[1]}\n" in content and '- "you can configure Zulip to not send typing notifications"' in content
    assert content.endswith("<answer>\nTurn it off.\n</answer>")


def test_a_question_that_isnt_partial_gets_a_neutral_phrase_in_the_partial_rules():
    system, _ = _request(
        question=QUESTION, qtype="answerable", expected_answer=FACTS, sources=SOURCES, answer="x", uncovered_part=None
    )
    assert NOT_PARTIAL in system and MODEL == "claude-opus-5-5" and EFFORT == "high"  # PRD Q14


@pytest.mark.anyio
async def test_an_answer_with_every_key_fact_is_correct(anthropic_client):
    verdict = await grade(
        anthropic_client,
        "Yes. Turn off typing notifications: click the gear icon in the upper right, select Personal settings, "
        "then Account & privacy. Under Privacy, toggle off Let recipients see when I'm typing direct messages, "
        "and Let recipients see when I'm typing messages in channels.",
    )
    assert verdict.verdict == "correct" and not verdict.missing_facts and not verdict.contradictions
    assert verdict.reason and verdict.output["verdict"] == "correct"
    assert verdict.input_tokens > 0 and verdict.output_tokens > 0


@pytest.mark.anyio
async def test_an_answer_missing_a_key_fact_is_incorrect(anthropic_client):
    verdict = await grade(anthropic_client, "Yes. You can turn off typing notifications.")
    assert verdict.verdict == "incorrect" and verdict.missing_facts


@pytest.mark.anyio
async def test_a_partial_answer_that_claims_the_uncovered_part_is_incorrect(anthropic_client):
    verdict = await grade(
        anthropic_client,
        "Turn off typing notifications: click the gear icon, select Personal settings, then Account & privacy, "
        "and under Privacy toggle off Let recipients see when I'm typing. To hide it from just one person, "
        "mute them first.",
        question=PARTIAL,
        qtype="partial",
        uncovered=UNCOVERED,
    )
    assert verdict.verdict == "incorrect"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "body", "problem"),
    [
        (500, {"type": "error", "error": {"type": "api_error", "message": "x"}}, "The call to the judge failed"),
        (200, {"id": "m", "type": "message", "role": "assistant", "model": MODEL, "stop_reason": "end_turn",
               "content": [{"type": "text", "text": "not json"}], "usage": {"input_tokens": 1, "output_tokens": 1}},
         "wasn't the verdict it was asked for"),
        (200, {"id": "m", "type": "message", "role": "assistant", "model": MODEL, "stop_reason": "max_tokens",
               "content": [{"type": "text", "text": "{"}], "usage": {"input_tokens": 1, "output_tokens": 1}},
         "stopped early"),
    ],
)  # fmt: skip
async def test_a_judge_reply_with_no_usable_verdict_is_an_error(status, body, problem):
    transport = httpx2.MockTransport(lambda request: httpx2.Response(status, json=body))
    http_client = anthropic.DefaultAsyncHttpxClient(transport=transport)
    async with anthropic.AsyncAnthropic(api_key="unused", max_retries=0, http_client=http_client) as client:
        with pytest.raises(JudgeError, match=problem):
            await grade(client, "Turn it off.")
