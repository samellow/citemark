"""Check the Claude and Voyage APIs against what the kit assumes (implementation plan T2, PRD 5.3).

Each assumption the answering pipeline rests on gets a live call, on each
answer model, before anything is built on it:
- search-result citations, and their streamed form
- the four decision tools, and whether one can come before any text
- cited text followed by report_gap
- prompt caching
- the judge's structured output
- context windows
- Voyage's embedding and rerank models

The questions use a made-up help center, so nothing here touches the frozen test set.

    uv run --with voyageai python scripts/api_check.py
    uv run --with voyageai python scripts/api_check.py --models claude-haiku-4-5 --skip-voyage

Reads ANTHROPIC_API_KEY and VOYAGE_API_KEY from the environment or `.env`, and
ANTHROPIC_WORKSPACE_ID when the Anthropic key isn't scoped to a workspace. A
full run costs well under a dollar, and the script prints what it cost.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import anthropic
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["claude-haiku-4-5", "claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
JUDGE_MODEL = "claude-opus-5-5"
# Answer calls: Haiku 4.5 has no adaptive thinking or effort. Opus 5.5 can't turn
# thinking off, so effort is its only control, and its default is medium. The 5.5
# models all run at low effort, so they're compared on the same setting. Haiku 5.5
# also runs with thinking off, as the bot will (PRD Q11): with it on, the first text
# took a median 2.47 s over 5 streams, against 0.83 s with it off (2026-10-08).
ANSWER_SETTINGS: dict[str, dict] = {
    "claude-haiku-4-5": {},
    "claude-haiku-5-5": {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}},
    "claude-sonnet-5-5": {"output_config": {"effort": "low"}},
    "claude-opus-5-5": {"output_config": {"effort": "low"}},
}
# USD per million tokens: input, output, 5-minute cache write, cache read (pricing page, 2026-10-08).
# Haiku 5.5's rates are for prompts up to 100K tokens, which every billed call here is; its cache
# rates are assumed at the usual 1.25x and 0.1x of input.
PRICES = {
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
}
# Prompt caching docs. Haiku 5.5 isn't listed there yet.
CACHE_MINIMUM: dict[str, int | None] = {
    "claude-haiku-4-5": 4096,
    "claude-haiku-5-5": None,
    "claude-sonnet-5-5": 512,
    "claude-opus-5-5": 512,
}

ARTICLES = [
    (
        "https://help.acme-notes.example/export",
        "Export your notes",
        [
            "You can export any notebook from Settings > Export.",
            "Choose PDF or Markdown, then click Start export.",
            "Exports run in the background. When one is ready, we email you a download link that works for 24 hours.",
        ],
    ),
    (
        "https://help.acme-notes.example/share",
        "Share a notebook",
        [
            "Open the notebook and click Share in the top right corner.",
            "Enter the person's email address and choose Viewer or Editor.",
            "Only the notebook's owner can change who has access.",
        ],
    ),
    (
        "https://help.acme-notes.example/plans",
        "Plans and limits",
        [
            "The Free plan includes 3 notebooks and 100 MB of storage.",
            "The Pro plan includes unlimited notebooks and 10 GB of storage.",
        ],
    ),
]

SYSTEM = """You answer customers' questions about Acme Notes, using only the search results provided.

- If the question isn't about Acme Notes, call decline with reason off_topic before writing any text.
- If the search results don't answer it, call decline with reason not_covered before writing any text.
- If it could mean several things the results cover differently, call ask_clarifying_question before writing any text.
- For a greeting, thanks or goodbye, call small_talk before writing any text.
- If the results answer only part of the question, answer that part, then call report_gap naming what they don't cover.
- Otherwise answer briefly, using only the search results."""


def _object(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TOOLS = [
    {
        "name": "decline",
        "description": "Say that the help center can't answer this question.",
        "input_schema": _object({"reason": {"type": "string", "enum": ["not_covered", "off_topic"]}}),
    },
    {
        "name": "ask_clarifying_question",
        "description": "Ask which of 2 or 3 meanings the customer has in mind.",
        "input_schema": _object(
            {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}}
        ),
    },
    {
        "name": "report_gap",
        "description": "After answering part of the question, name the part the help center doesn't cover.",
        "input_schema": _object({"missing": {"type": "string"}}),
    },
    {
        "name": "small_talk",
        "description": "Reply to a greeting, thanks or goodbye.",
        "input_schema": _object({"kind": {"type": "string", "enum": ["greeting", "thanks", "goodbye"]}}),
    },
]

# question, and the tool the prompt asks for (None: a cited answer)
CASES = {
    "answer": ("How do I export my notes as a PDF?", None),
    "not_covered": ("Can I lock a notebook with a password?", "decline"),
    "off_topic": ("What's the capital of Australia?", "decline"),
    "ambiguous": ("What's the limit?", "ask_clarifying_question"),
    "small_talk": ("thanks, that's everything!", "small_talk"),
}
PARTIAL = "How do I export my notes, and can I schedule an export to run every week?"

JUDGE_SCHEMA = {
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


@dataclass
class Result:
    model: str
    check: str
    status: str  # pass, fail or note
    detail: str


class Check:
    def __init__(self, client: anthropic.Anthropic) -> None:
        self.client = client
        self.results: list[Result] = []
        self.spent: dict[str, float] = {}

    def record(self, model: str, check: str, status: str, detail: str) -> None:
        self.results.append(Result(model, check, status, detail))
        print(f"  {status:<4}  {model:<18} {check:<26} {detail}", flush=True)

    def bill(self, model: str, usage) -> None:
        price_in, price_out, price_write, price_read = PRICES[model]
        written = usage.cache_creation_input_tokens or 0
        read = usage.cache_read_input_tokens or 0
        tokens = usage.input_tokens * price_in + usage.output_tokens * price_out
        self.spent[model] = self.spent.get(model, 0.0) + (tokens + written * price_write + read * price_read) / 1e6

    def ask(self, model: str, question: str, after: list[dict] | None = None) -> anthropic.types.Message:
        """`after` continues the conversation: an assistant turn, then the tool results for it."""
        question_turn = {"role": "user", "content": [*search_results(), {"type": "text", "text": question}]}
        message = self.client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM,
            tools=TOOLS,
            messages=[question_turn, *(after or [])],
            **ANSWER_SETTINGS[model],
        )
        self.bill(model, message.usage)
        return message


def search_results() -> list[dict]:
    return [
        {
            "type": "search_result",
            "source": source,
            "title": title,
            "content": [{"type": "text", "text": paragraph} for paragraph in paragraphs],
            "citations": {"enabled": True},
        }
        for source, title, paragraphs in ARTICLES
    ]


def shape(content) -> str:
    """The order of the blocks in a response, for example "thinking(empty) text+cite tool:report_gap"."""
    parts = []
    for block in content:
        if block.type == "thinking":
            parts.append(f"thinking({'empty' if not block.thinking else 'text'})")
        elif block.type == "text":
            parts.append("text+cite" if block.citations else "text")
        elif block.type == "tool_use":
            parts.append(f"tool:{block.name}")
        else:
            parts.append(block.type)
    return " ".join(parts)


def visible(content) -> list:
    """The blocks a visitor could see: everything but thinking."""
    return [block for block in content if block.type not in ("thinking", "redacted_thinking")]


def citation_problems(content) -> list[str]:
    problems = []
    for block in content:
        for citation in (block.citations or []) if block.type == "text" else []:
            if citation.type != "search_result_location":
                problems.append(f"citation type {citation.type}")
                continue
            if not 0 <= citation.search_result_index < len(ARTICLES):
                problems.append(f"search_result_index {citation.search_result_index}")
                continue
            paragraphs = ARTICLES[citation.search_result_index][2]
            if not 0 <= citation.start_block_index < citation.end_block_index <= len(paragraphs):
                problems.append(f"block range {citation.start_block_index}-{citation.end_block_index}")
            elif paragraphs[citation.start_block_index] not in citation.cited_text:
                problems.append("cited_text doesn't hold the cited blocks")
    return problems


def check_model_facts(check: Check, model: str) -> int | None:
    info = check.client.models.retrieve(model)
    window = getattr(info, "max_input_tokens", None)
    detail = f"max_input_tokens {window}, max_tokens {info.max_tokens}"
    if info.deprecated_at or info.retires_at:
        detail += f"; deprecated {info.deprecated_at}, retires {info.retires_at}"
    check.record(model, "context window", "note", detail)
    return window


def check_citations(check: Check, model: str) -> None:
    message = check.ask(model, CASES["answer"][0])
    problems = citation_problems(message.content)
    cited = any(block.type == "text" and block.citations for block in message.content)
    status = "pass" if cited and not problems else "fail"
    detail = shape(message.content) + (f"; {problems}" if problems else "" if cited else "; no citations")
    check.record(model, "search_result citations", status, detail)


def check_streaming(check: Check, model: str, streams: int) -> None:
    """Citations arrive as citations_delta. The tools stream eagerly, as the answer pipeline will send them.
    Each stream also times the first text: from this machine, without retrieval."""
    runs = [stream_once(check, model) for _ in range(streams)]
    deltas = [deltas for deltas, _, _ in runs]
    first_blocks = sorted({block for _, _, block in runs})
    detail = f"citations_delta events per stream {deltas}; first visible block {', '.join(first_blocks)}"
    check.record(model, "streamed citations_delta", "pass" if all(deltas) else "fail", detail)
    times = sorted(first_text for _, first_text, _ in runs if first_text is not None)
    if times:
        spread = f"median {statistics.median(times):.2f}s, range {times[0]:.2f}-{times[-1]:.2f}s"
        detail = f"{spread} over {len(times)} stream{'s' if len(times) > 1 else ''}"
    else:
        detail = "no text"
    check.record(model, "time to first text", "note", detail)


def stream_once(check: Check, model: str) -> tuple[int, float | None, str]:
    """citations_delta events, seconds to the first text, and the first visible block's type."""
    started = time.perf_counter()
    first_visible = first_text = None
    citation_deltas = 0
    with check.client.messages.stream(
        model=model,
        max_tokens=4096,
        system=SYSTEM,
        tools=[{**tool, "eager_input_streaming": True} for tool in TOOLS],
        messages=[{"role": "user", "content": [*search_results(), {"type": "text", "text": CASES["answer"][0]}]}],
        **ANSWER_SETTINGS[model],
    ) as stream:
        for event in stream:
            elapsed = time.perf_counter() - started
            if event.type == "content_block_start" and first_visible is None:
                if event.content_block.type not in ("thinking", "redacted_thinking"):
                    first_visible = event.content_block.type
            elif event.type == "content_block_delta":
                if event.delta.type == "citations_delta":
                    citation_deltas += 1
                elif event.delta.type == "text_delta" and first_text is None:
                    first_text = elapsed
        message = stream.get_final_message()
    check.bill(model, message.usage)
    return citation_deltas, first_text, first_visible or "none"


def check_decisions(check: Check, model: str) -> None:
    """A decision tool can be the first block a visitor would see, with no text before it."""
    for case, (question, tool) in CASES.items():
        if tool is None:
            continue
        message = check.ask(model, question)
        seen = visible(message.content)
        called = [block.name for block in seen if block.type == "tool_use"]
        if seen and seen[0].type == "tool_use":
            status, why = ("pass", "tool first") if seen[0].name == tool else ("note", f"called {seen[0].name}")
        elif tool in called:
            at = next(i for i, block in enumerate(seen) if block.type == "tool_use")
            said = " ".join(" ".join(block.text.split()) for block in seen[:at] if block.type == "text")
            status, why = "fail", f"text came before the tool call: {said[:100]!r}"
        else:
            status, why = "note", f"no {tool} call: the prompt, not the API, decides this"
        check.record(model, f"decision first: {case}", status, f"{why}; {shape(message.content)}")


def check_report_gap(check: Check, model: str, repeats: int) -> None:
    """Cited text, then report_gap. On some models, text written right before a tool call comes
    back as an empty thinking block instead, which would lose the answer and its citations."""
    for attempt in range(1, repeats + 1):
        message = check.ask(model, PARTIAL)
        seen = visible(message.content)
        gap_at = next((i for i, b in enumerate(seen) if b.type == "tool_use" and b.name == "report_gap"), None)
        cited_before = gap_at is not None and any(b.type == "text" and b.citations for b in seen[:gap_at])
        if gap_at is None:
            status, why = "note", "no report_gap call"
        elif cited_before:
            status, why = "pass", "cited text, then report_gap"
        else:
            status, why = "fail", "report_gap without cited text before it"
        check.record(model, f"text then report_gap #{attempt}", status, f"{why}; {shape(message.content)}")
        if status == "fail":
            check_answer_after_gap(check, model, message, attempt)


def check_answer_after_gap(check: Check, model: str, message: anthropic.types.Message, attempt: int) -> None:
    """The other order: report_gap first, then the cited answer once the tool result comes back."""
    results = [
        {"type": "tool_result", "tool_use_id": block.id, "content": "Recorded."}
        for block in message.content
        if block.type == "tool_use"
    ]
    follow = check.ask(
        model, PARTIAL, after=[{"role": "assistant", "content": message.content}, {"role": "user", "content": results}]
    )
    cited = any(block.type == "text" and block.citations for block in visible(follow.content))
    why = "cited answer after the tool result" if cited else "no cited answer after the tool result"
    check.record(
        model, f"answer after report_gap #{attempt}", "pass" if cited else "fail", f"{why}; {shape(follow.content)}"
    )


def check_caching(check: Check, model: str) -> None:
    """The system prompt and tools are cached once they pass the model's minimum length."""
    for label, repeat in (("short prefix", 40), ("long prefix", 400)):
        filler = " ".join(["Acme Notes keeps every notebook private until its owner shares it."] * repeat)
        request = {
            "model": model,
            "max_tokens": 1024,
            "system": [{"type": "text", "text": f"{SYSTEM}\n\n{filler}", "cache_control": {"type": "ephemeral"}}],
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "Reply with the word OK."}],
            **ANSWER_SETTINGS[model],
        }
        prefix = check.client.messages.count_tokens(
            model=model, system=request["system"], tools=TOOLS, messages=request["messages"]
        ).input_tokens
        written = []
        for _ in range(2):
            message = check.client.messages.create(**request)
            check.bill(model, message.usage)
            written.append(message.usage.cache_creation_input_tokens or 0)
        read = message.usage.cache_read_input_tokens or 0
        minimum = CACHE_MINIMUM[model]
        if minimum is None:
            status = "note"
        else:
            expected = prefix >= minimum
            # cached exactly when the docs say it should be; caching below the minimum is only a note
            status = "pass" if bool(read) == expected else ("fail" if expected else "note")
        detail = (
            f"about {prefix} tokens (minimum {minimum or 'not documented'}): "
            f"first call wrote {written[0]} to the cache, second read {read}"
        )
        check.record(model, f"cache, {label}", status, detail)


def check_citations_reject_structured_output(check: Check, model: str) -> None:
    try:
        message = check.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": [*search_results(), {"type": "text", "text": "Summarize."}]}],
            output_config={"format": {"type": "json_schema", "schema": _object({"summary": {"type": "string"}})}},
        )
    except anthropic.BadRequestError as exc:
        check.record(model, "citations + structured output", "pass", f"refused: {exc.message[:90]}")
        return
    check.bill(model, message.usage)
    detail = f"accepted, where PRD 5.3 assumes a 400; reply {shape(message.content)}"
    check.record(model, "citations + structured output", "fail", detail)


def check_full_context(check: Check, model: str, window: int | None) -> None:
    """How much of the context window the whole Zulip help center takes in full-context mode."""
    manifest = json.loads((ROOT / "fixtures/zulip/manifest.json").read_text(encoding="utf-8"))
    blocks = []
    for page in manifest["pages"]:
        text = (ROOT / "fixtures/zulip/text" / f"{page['slug']}.md").read_text(encoding="utf-8")
        paragraphs = [{"type": "text", "text": p.strip()} for p in text.split("\n\n") if p.strip()]
        title = page["title"].split(" | ")[0]
        blocks.append(
            {
                "type": "search_result",
                "source": page["url"],
                "title": title,
                "content": paragraphs,
                "citations": {"enabled": True},
            }
        )
    messages = [{"role": "user", "content": [*blocks, {"type": "text", "text": "How do I star a message?"}]}]
    try:
        tokens = check.client.messages.count_tokens(model=model, system=SYSTEM, tools=TOOLS, messages=messages)
    except anthropic.BadRequestError as exc:
        check.record(model, "full help center", "note", f"count refused: {exc.message[:90]}")
        return
    fits = window is None or tokens.input_tokens <= window
    share = f" ({tokens.input_tokens / window:.0%} of the window)" if window else ""
    detail = f"{tokens.input_tokens:,} tokens for {len(blocks)} articles{share}; {'fits' if fits else 'does not fit'}"
    # PRD 5.2 offers full-context mode only on models it fits, so not fitting is a fact, not a failure
    check.record(model, "full help center", "note", detail)


def check_judge(check: Check) -> None:
    """The judge: Opus 5.5 with structured output (PRD 5.4), on an answer missing one key fact."""
    prompt = (
        "Grade the answer against the expected key facts. It is correct only if it contains every key fact "
        "and contradicts none of them.\n\n"
        "Question: How do I export my notes as a PDF?\n"
        "Key facts:\n- Go to Settings > Export\n- Choose PDF, then click Start export\n"
        "- A download link is emailed and works for 24 hours\n\n"
        "Answer: Open Settings > Export, choose PDF and click Start export."
    )
    message = check.client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
    )
    check.bill(JUDGE_MODEL, message.usage)
    text = next((block.text for block in message.content if block.type == "text"), "")
    try:
        verdict = json.loads(text)
    except json.JSONDecodeError:
        check.record(JUDGE_MODEL, "judge structured output", "fail", f"not JSON: {text[:80]!r}")
        return
    caught = verdict.get("verdict") == "incorrect" and verdict.get("missing_facts")
    detail = f"verdict {verdict.get('verdict')}, missing {verdict.get('missing_facts')}"
    check.record(JUDGE_MODEL, "judge structured output", "pass" if caught else "note", detail)


def check_models_list(check: Check) -> None:
    haiku = sorted(model.id for model in check.client.models.list() if "haiku" in model.id)
    check.record("-", "models listed", "note", f"Haiku models: {', '.join(haiku) or 'none'}")


def check_voyage(check: Check, api_key: str | None) -> None:
    try:
        import voyageai
    except ImportError:
        check.record("voyage", "client", "fail", "run with: uv run --with voyageai python scripts/api_check.py")
        return
    client = voyageai.Client(api_key=api_key)
    texts = [" ".join(paragraphs) for _, _, paragraphs in ARTICLES]
    docs = client.embed(texts, model="voyage-4", input_type="document", output_dimension=1024)
    query = client.embed(["export as pdf"], model="voyage-4", input_type="query", output_dimension=1024)
    sizes = {len(vector) for vector in [*docs.embeddings, *query.embeddings]}
    detail = f"dimensions {sorted(sizes)}, {docs.total_tokens + query.total_tokens} tokens"
    check.record("voyage-4", "embeddings", "pass" if sizes == {1024} else "fail", detail)
    for model in ("rerank-2.5", "rerank-3"):
        try:
            ranked = client.rerank("How do I export my notes?", texts, model=model, top_k=3)
        except Exception as exc:  # the SDK raises its own error types; whatever fails is the finding
            check.record(model, "rerank", "fail" if model == "rerank-2.5" else "note", f"{type(exc).__name__}: {exc}")
            continue
        top = ranked.results[0]
        status = "pass" if top.index == 0 else "note"
        check.record(model, "rerank", status, f"top result {top.index} (score {top.relevance_score:.2f})")


def key(name: str) -> str | None:
    return os.environ.get(name) or dotenv_values(ROOT / ".env").get(name) or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=MODELS, choices=MODELS)
    parser.add_argument("--repeats", type=int, default=3, help="Runs of the text-then-report_gap check per model")
    parser.add_argument("--streams", type=int, default=3, help="Streams per model, for the time to first text")
    parser.add_argument("--skip-voyage", action="store_true")
    parser.add_argument("--json", type=Path, help="Also write the results here")
    args = parser.parse_args()

    options: dict = {}
    if anthropic_key := key("ANTHROPIC_API_KEY"):
        options["api_key"] = anthropic_key
    if workspace := key("ANTHROPIC_WORKSPACE_ID"):
        options["default_headers"] = {"anthropic-workspace-id": workspace}
    check = Check(anthropic.Anthropic(**options))
    print(f"  {'':<4}  {'model':<18} {'check':<26} detail")
    try:
        check_models_list(check)
        for model in args.models:
            window = check_model_facts(check, model)
            check_citations(check, model)
            check_streaming(check, model, args.streams)
            check_decisions(check, model)
            check_report_gap(check, model, args.repeats)
            check_caching(check, model)
            check_citations_reject_structured_output(check, model)
            check_full_context(check, model, window)
        if JUDGE_MODEL in args.models:
            check_judge(check)
    except anthropic.AuthenticationError:
        print("The Anthropic API refused the key. Set ANTHROPIC_API_KEY in .env or the environment.", file=sys.stderr)
        return 2
    except anthropic.APIConnectionError:
        print("Couldn't reach the Anthropic API. Check the network connection.", file=sys.stderr)
        return 2
    except anthropic.BadRequestError as exc:
        if "anthropic-workspace-id" not in str(exc):
            raise
        print(
            "The Anthropic key isn't scoped to a workspace. Use a key created inside a workspace,"
            " or set ANTHROPIC_WORKSPACE_ID in .env.",
            file=sys.stderr,
        )
        return 2
    if not args.skip_voyage:
        check_voyage(check, key("VOYAGE_API_KEY"))

    failed = [r for r in check.results if r.status == "fail"]
    cost = sum(check.spent.values())
    print(f"\n{len(check.results)} checks, {len(failed)} failed. Claude calls cost ${cost:.2f} at list prices.")
    if args.json:
        payload = {"results": [asdict(r) for r in check.results], "cost_usd": round(cost, 4)}
        args.json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
