"""Shared test setup: recorded API replies, and a guard that keeps tests off the network.

Tests replay replies recorded from the real APIs, so they're fast, free and repeatable
(QA plan 3.2). Re-recording is deliberate, and it calls the real APIs, which costs money:

    uv run pytest <test> --record

A prompt change re-records the replies it affects in the same commit, so the diff shows
what changed in the bot's output.
"""

from pathlib import Path

import pytest

from citemark.testing.network import block_network
from citemark.testing.recordings import RecordingTransport

RECORDINGS = Path(__file__).parent / "recordings"
ZULIP = Path(__file__).parents[1] / "fixtures" / "zulip"
GET_RAW = (
    "gh release download zulip-v1-frozen -p raw.tar.gz -D fixtures/zulip && "
    "tar -xzf fixtures/zulip/raw.tar.gz -C fixtures/zulip"
)


def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        help="Call the real APIs and save their replies under tests/recordings/. Costs money.",
    )


@pytest.fixture(scope="session")
def recording(pytestconfig) -> bool:
    return pytestconfig.getoption("--record")


@pytest.fixture(autouse=True, scope="session")
def no_network(recording):
    if recording:
        yield
        return
    with pytest.MonkeyPatch.context() as patch:
        block_network(patch)
        yield


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def zulip_raw() -> Path:
    """The snapshot's raw HTML. It's attached to the freeze tag's release rather than committed."""
    raw = ZULIP / "raw"
    if not raw.is_dir():
        pytest.fail(f"The Zulip snapshot's raw HTML isn't in {raw}. Get it with: {GET_RAW}", pytrace=False)
    return raw


@pytest.fixture
def recorded_transport(request, recording):
    """A transport for an `httpx2` client: replies from tests/recordings/, or live with --record."""

    def missing(message):
        pytest.fail(f"{message} Record it with: uv run pytest {request.node.nodeid} --record", pytrace=False)

    return RecordingTransport(RECORDINGS, record=recording, on_missing=missing)


@pytest.fixture
async def anthropic_client(recorded_transport, recording):
    """The Anthropic SDK, answering from recordings. It doesn't retry, so a failure shows at once."""
    import anthropic

    from citemark.settings import get_settings

    if recording:
        key = get_settings().anthropic_api_key
        if key is None:
            pytest.fail("--record needs ANTHROPIC_API_KEY in .env or the environment.", pytrace=False)
        api_key = key.get_secret_value()
    else:
        api_key = "replayed"  # never sent anywhere: the transport answers from files
    http_client = anthropic.DefaultAsyncHttpxClient(transport=recorded_transport)
    async with anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, http_client=http_client) as client:
        yield client
