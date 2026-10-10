"""The ask box's limits and counts (PRD 8.2, 5.11; onboarding plan 7): ten questions an hour per
visitor, kept in memory as salted hashes, and daily counts that never name a person."""

import datetime as dt

import pytest

from citemark.web import counts
from citemark.web.limits import RateLimiter, client_address

VISITOR, OTHER, PROXY = "203.0.113.7", "203.0.113.8", "10.0.0.9"


def limiter(now: list[float], **given) -> RateLimiter:
    return RateLimiter(clock=lambda: now[0], **given)


def test_ten_questions_an_hour_then_the_minutes_until_the_oldest_drops_out():
    now = [0.0]
    limits = limiter(now)
    for minute in range(10):
        now[0] = minute * 60.0
        assert limits.ask(VISITOR) is None
    now[0] = 600.0
    assert limits.ask(VISITOR) == 50  # the first, at 0, drops out at 3,600
    now[0] = 3_600.0
    assert limits.ask(VISITOR) is None


def test_the_wait_is_rounded_up_and_never_none_while_refused():
    now = [0.0]
    limits = limiter(now)
    for _ in range(10):
        limits.ask(VISITOR)
    now[0] = 3_599.5
    assert limits.ask(VISITOR) == 1
    now[0] = 3_540.0 - 0.5
    assert limits.ask(VISITOR) == 2  # 60.5 seconds left


def test_a_refused_question_doesnt_count():
    now = [0.0]
    limits = limiter(now)
    for _ in range(10):
        limits.ask(VISITOR)
    now[0] = 1_800.0  # refused half an hour later: counted, they'd still hold the hour at 3,600
    for _ in range(5):
        assert limits.ask(VISITOR) == 30
    now[0] = 3_600.0
    assert all(limits.ask(VISITOR) is None for _ in range(10))


def test_each_visitor_has_their_own_hour():
    now = [0.0]
    limits = limiter(now)
    for _ in range(10):
        limits.ask(VISITOR)
    assert limits.ask(VISITOR) is not None
    assert limits.ask(OTHER) is None


def test_a_new_day_draws_a_new_salt_and_forgets_everyone():
    now, day = [0.0], [dt.date(2026, 10, 10)]
    limits = RateLimiter(clock=lambda: now[0], today=lambda: day[0])
    for _ in range(10):
        limits.ask(VISITOR)
    salt = limits._salt
    day[0] = dt.date(2026, 10, 11)
    assert limits.ask(VISITOR) is None
    assert limits._salt != salt and limits.remembered() == 1


def test_it_keeps_salted_digests_never_addresses():
    limits = RateLimiter()
    limits.ask(VISITOR)
    assert all(isinstance(key, bytes) and len(key) == 16 for key in limits._asked)
    assert VISITOR not in repr(limits._asked) and VISITOR.encode() not in b"".join(limits._asked)
    again = RateLimiter()
    again.ask(VISITOR)
    assert set(again._asked) != set(limits._asked)  # each limiter draws its own salt


def test_past_its_size_the_longest_idle_visitor_is_forgotten():
    now = [0.0]
    limits = limiter(now, limit=1, visitors=2)
    limits.ask("192.0.2.1")
    limits.ask("192.0.2.2")
    assert limits.ask("192.0.2.1") == 60  # seen again, so now the most recent
    limits.ask("192.0.2.3")
    assert limits.remembered() == 2
    assert limits.ask("192.0.2.2") is None  # forgotten, so counted afresh
    assert limits.ask("192.0.2.1") is None  # forgotten when 192.0.2.2 came back


@pytest.mark.parametrize(
    ("headers", "header", "expected"),
    [
        ({"CF-Connecting-IP": VISITOR}, "CF-Connecting-IP", VISITOR),
        ({"CF-Connecting-IP": " 2001:DB8::1 "}, "CF-Connecting-IP", "2001:db8::/64"),
        ({"CF-Connecting-IP": "2001:db8::1:2:3:4"}, "CF-Connecting-IP", "2001:db8::/64"),  # the same /64
        ({"CF-Connecting-IP": "::ffff:203.0.113.7"}, "CF-Connecting-IP", VISITOR),
        ({}, "CF-Connecting-IP", PROXY),  # not through the proxy as expected: its own address
        ({"CF-Connecting-IP": "not an address"}, "CF-Connecting-IP", PROXY),
        ({"CF-Connecting-IP": VISITOR}, None, PROXY),  # no header set: the header isn't trusted
        ({"X-Forwarded-For": f"{OTHER}, {VISITOR}"}, "CF-Connecting-IP", PROXY),  # never read
    ],
)
def test_the_visitor_is_read_from_the_proxys_header_only(headers, header, expected):
    assert client_address(headers, PROXY, header) == expected


def test_an_ipv6_visitor_cant_get_a_new_hour_by_changing_address_within_their_64():
    now = [0.0]
    limits = limiter(now)

    def asks(address: str) -> int | None:
        return limits.ask(client_address({"CF-Connecting-IP": address}, PROXY, "CF-Connecting-IP"))

    for host in range(10):
        assert asks(f"2001:db8::{host + 1:x}") is None
    assert asks("2001:db8::ffff") == 60
    assert asks("2001:db8:0:1::1") is None  # the next /64 is someone else


def test_only_the_two_pitches_are_counted_as_variants():
    assert [counts.variant(v) for v in ("accuracy", "build", "", None, "made-up", "ACCURACY")] == [
        "accuracy",
        "build",
        "",
        "",
        "",
        "",
    ]


@pytest.mark.parametrize(
    ("user_agent", "person"),
    [
        ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", True),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Safari/604.1", True),
        ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", False),
        ("Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)", False),
        ("facebookexternalhit/1.1", False),
        ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 HeadlessChrome/141.0 Safari/537.36", False),
        ("curl/8.5.0", False),
        ("python-httpx/0.28.1", False),
        ("", False),
        (None, False),
    ],
)
def test_crawlers_previews_and_scripts_arent_counted(user_agent, person):
    assert counts.is_person(user_agent) is person


@pytest.mark.anyio
async def test_an_event_that_isnt_counted_is_refused():
    with pytest.raises(ValueError, match="isn't a counted event"):
        await counts.count(None, "visitor_email", "", day=dt.date(2026, 10, 10))
