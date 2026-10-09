"""The server's rules for what the visitor sees (PRD 5.3, Q11, Q12), from the model's events.

- A decline, a clarifying question or small talk replaces the answer. If text was shown before
  it, the text is swapped out, and the swap is counted.
- Decisions and small talk show the fixed strings, never the model's words.
- `report_gap` adds the gap line under a cited answer, held until the answer ends.
- The safety net: a reply with no citation and no decision becomes a decline. So does a
  `report_gap` with no cited answer before or after it.
- At most 3 sources, numbered in order of first appearance, one per passage.
- A reply cut off by the token limit is an error, never shown as if complete. A reply the model
  refused to write is declined as off topic.

Thinking never reaches here: the adapter drops it, so the first event is the first block a
visitor could see. Whatever the model did against the rules is kept in `Reply.problems`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from citemark import strings
from citemark.answer import Reply, Segment, Source
from citemark.models import CitationEvent, DecisionEvent, Event, Passage, TextEvent, UsageEvent

REPLACING = ("decline", "ask_clarifying_question", "small_talk")  # decisions shown instead of an answer
MAX_SOURCES = 3
OPTIONS = (2, 3)  # how many options a clarifying question has
OPTION_LENGTH = 40
GAP_LENGTH = 100
REASONS = ("not_covered", "off_topic")
SMALL_TALK = ("greeting", "thanks", "goodbye")


def decide(events: Iterable[Event], *, passages: Sequence[Passage], offered: Sequence[str], company: str) -> Reply:
    texts: dict[int, list[str]] = {}
    cites: dict[int, list[CitationEvent]] = {}
    call_of: dict[int, int] = {}  # text block: the model call it came from
    calls: list[UsageEvent] = []
    gaps: list[DecisionEvent] = []
    problems: list[str] = []
    ending: DecisionEvent | None = None
    shown = False  # text a visitor could read has arrived
    shown_first = False  # ...before the decision that replaces it
    for event in events:
        match event:
            case TextEvent():
                texts.setdefault(event.block, []).append(event.text)
                call_of.setdefault(event.block, len(calls))
                shown = shown or bool(event.text.strip())
            case CitationEvent():
                texts.setdefault(event.block, [])
                call_of.setdefault(event.block, len(calls))
                cites.setdefault(event.block, []).append(event)
            case DecisionEvent() if event.tool not in offered:
                problems.append(f"called {event.tool}, which wasn't offered")
            case DecisionEvent() if event.tool == "report_gap":
                gaps.append(event)
            case DecisionEvent() if event.tool in REPLACING and ending is None:
                ending, shown_first = event, shown
            case DecisionEvent() if ending is not None:
                problems.append(f"called {event.tool} after {ending.tool}")
            case UsageEvent():
                calls.append(event)

    stop = calls[-1].stop_reason if calls else None
    if stop == "max_tokens" and ending is not None:  # the decision came whole; what followed was cut off
        problems.append("ran out of tokens before the reply ended")
    if ending is not None:
        return _decision(ending, swapped=shown_first, company=company, calls=calls, problems=problems)
    if stop == "refusal":
        problems.append("refused to answer")
        return _fixed("decline_off_topic", company, swapped=shown, calls=calls, problems=problems)
    if stop == "max_tokens":
        problems.append("ran out of tokens before the reply ended")
        return Reply("error", "", calls=tuple(calls), problems=_unique(problems))

    segments, sources = _cited(texts, cites, call_of, passages, problems)
    if not sources:  # the safety net
        if gaps:
            problems.append("reported a gap with no cited answer")
        elif shown:
            problems.append("wrote text with no citations")
        else:
            problems.append("wrote nothing")
        return _fixed("decline_not_covered", company, swapped=shown, calls=calls, problems=problems)

    gap = next((found for found in map(_gap, gaps) if found), None)
    if gaps and gap is None:
        problems.append("reported a gap without naming it")
    elif gap and len(gap) > GAP_LENGTH:
        problems.append(f"named a gap over {GAP_LENGTH} characters")
    return Reply(
        "partial" if gaps else "answer",
        "".join(segment.text for segment in segments),
        segments=segments,
        sources=tuple(sources),
        gap=gap,
        calls=tuple(calls),
        problems=_unique(problems),
    )


def _decision(
    event: DecisionEvent, *, swapped: bool, company: str, calls: list[UsageEvent], problems: list[str]
) -> Reply:
    """A decline, a clarifying question or small talk. One with input the visitor can't be shown
    falls to the safety net."""
    if event.tool == "decline":
        reason = event.input.get("reason")
        if reason not in REASONS:
            problems.append(f"declined with the reason {reason!r}")
            reason = "not_covered"
        return _fixed(f"decline_{reason}", company, swapped=swapped, calls=calls, problems=problems)
    if event.tool == "ask_clarifying_question":
        options = _options(event.input.get("options"), problems)
        if len(options) >= OPTIONS[0]:
            text = strings.text("widget", "clarify.question")
            return Reply(
                "clarify",
                text,
                clarify_options=options,
                swapped=swapped,
                calls=tuple(calls),
                problems=_unique(problems),
            )
        problems.append(f"asked a clarifying question with {len(options)} usable options")
    else:
        kind = event.input.get("kind")
        if kind in SMALL_TALK:
            text = strings.text("widget", f"small_talk.{kind}")
            return Reply("small_talk", text, swapped=swapped, calls=tuple(calls), problems=_unique(problems))
        problems.append(f"made small talk of the kind {kind!r}")
    return _fixed("decline_not_covered", company, swapped=swapped, calls=calls, problems=problems)


def _fixed(kind: str, company: str, *, swapped: bool, calls: list[UsageEvent], problems: list[str]) -> Reply:
    key = kind.replace("decline_", "decline.")
    text = strings.text("widget", key, company=company) if kind == "decline_off_topic" else strings.text("widget", key)
    return Reply(kind, text, swapped=swapped, calls=tuple(calls), problems=_unique(problems))


def _cited(
    texts: dict[int, list[str]],
    cites: dict[int, list[CitationEvent]],
    call_of: dict[int, int],
    passages: Sequence[Passage],
    problems: list[str],
) -> tuple[tuple[Segment, ...], list[Source]]:
    """The answer's text blocks with their markers, and the sources they number."""
    markers: dict[int, int] = {}  # passage index: marker
    sources: list[Source] = []
    segments: list[tuple[int, Segment]] = []
    for block in sorted(texts):  # blocks are numbered in the order they started
        found: list[int] = []
        for cite in cites.get(block, []):
            if not 0 <= cite.passage < len(passages):
                problems.append(f"cited passage {cite.passage}, which wasn't sent")
                continue
            passage = passages[cite.passage]
            if not 0 <= cite.start_block < cite.end_block <= len(passage.blocks):
                problems.append(f"cited paragraphs {cite.start_block}-{cite.end_block} of a passage with fewer")
                continue
            if cite.passage not in markers:
                if len(markers) == MAX_SOURCES:  # only 3 sources are shown (PRD 5.3)
                    problems.append(f"cited more than {MAX_SOURCES} passages, so part of the answer shows no source")
                    continue
                markers[cite.passage] = len(markers) + 1
                sources.append(
                    Source(
                        markers[cite.passage],
                        cite.passage,
                        passage.chunk_id,
                        passage.url,
                        passage.title,
                        cite.cited_text,
                        cite.start_block,
                        cite.end_block,
                    )
                )
            if markers[cite.passage] not in found:
                found.append(markers[cite.passage])
        segments.append((call_of[block], Segment("".join(texts[block]), tuple(found))))
    return _joined(segments), sources


def _joined(segments: list[tuple[int, Segment]]) -> tuple[Segment, ...]:
    """The answer's segments, without the blank space the model leaves before its first word
    and after its last. Blank space between two segments is kept, so paragraphs stay apart. A
    second call's text starts a new paragraph: the model wrote it after a tool result, so it
    doesn't run on from the first call's last sentence."""

    def blank(segment: Segment) -> bool:
        return not segment.text.strip() and not segment.markers

    start, end = 0, len(segments)
    while start < end and blank(segments[start][1]):
        start += 1
    while end > start and blank(segments[end - 1][1]):
        end -= 1
    kept = segments[start:end]
    joined: list[Segment] = []
    for index, (call, segment) in enumerate(kept):
        text = segment.text
        if index == 0:
            text = text.lstrip()
        elif call != kept[index - 1][0]:
            joined[-1] = Segment(joined[-1].text.rstrip(), joined[-1].markers)
            text = "\n\n" + text.lstrip()
        joined.append(Segment(text, segment.markers))
    if joined:
        joined[-1] = Segment(joined[-1].text.rstrip(), joined[-1].markers)
    return tuple(joined)


def _options(raw: object, problems: list[str]) -> tuple[str, ...]:
    options: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        option = " ".join(item.split()) if isinstance(item, str) else ""
        if option and option.casefold() not in {kept.casefold() for kept in options}:
            options.append(option)
    if len(options) > OPTIONS[1]:
        problems.append(f"gave {len(options)} options")
        options = options[: OPTIONS[1]]
    if any(len(option) > OPTION_LENGTH for option in options):
        problems.append(f"gave an option over {OPTION_LENGTH} characters")
    return tuple(options)


def _gap(event: DecisionEvent) -> str | None:
    missing = event.input.get("missing")
    phrase = " ".join(missing.split()).rstrip(".") if isinstance(missing, str) else ""
    return phrase or None


def _unique(problems: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(problems))
