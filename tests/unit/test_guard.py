"""No internal addresses (PRD 5.1, QA plan G1): each blocked range, and the check at the connection."""

import httpcore2
import httpx2
import pytest

from citemark.ingest.fetch import Fetcher, Scope
from citemark.ingest.guard import BlockedAddress, PublicOnlyBackend, PublicOnlyTransport, is_public

BLOCKED = {
    "127.0.0.1": "loopback",
    "127.255.255.254": "loopback, top of the range",
    "0.0.0.0": "this host",
    "10.1.2.3": "private 10/8",
    "172.16.0.1": "private 172.16/12",
    "172.31.255.254": "private 172.16/12, top of the range",
    "192.168.1.1": "private 192.168/16",
    "169.254.169.254": "link-local: the cloud metadata service",
    "100.64.0.1": "shared address space (carrier-grade NAT)",
    "192.0.0.8": "IETF protocol assignments",
    "198.18.0.1": "benchmarking",
    "192.0.2.1": "documentation",
    "224.0.0.1": "multicast",
    "240.0.0.1": "reserved",
    "255.255.255.255": "broadcast",
    "::1": "IPv6 loopback",
    "::": "IPv6 unspecified",
    "fe80::1": "IPv6 link-local",
    "fc00::1": "IPv6 unique local",
    "fd00:ec2::254": "IPv6 unique local: AWS's metadata service",
    "ff02::1": "IPv6 multicast",
    "2001:db8::1": "IPv6 documentation",
    "::ffff:127.0.0.1": "loopback inside an IPv4-mapped address",
    "::ffff:169.254.169.254": "the metadata service inside an IPv4-mapped address",
    "64:ff9b::a9fe:a9fe": "the metadata service through a NAT64 gateway",
    "2002:7f00:1::": "loopback inside a 6to4 address",
    "not-an-address": "a name, not an address",
}
PUBLIC = ["93.184.215.14", "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"]


@pytest.mark.parametrize("address", BLOCKED, ids=BLOCKED.values())
def test_every_internal_range_is_refused(address):
    assert not is_public(address)


@pytest.mark.parametrize("address", PUBLIC)
def test_public_addresses_are_allowed(address):
    assert is_public(address)


class Wire(httpcore2.AsyncNetworkBackend):
    """Answers every connection with one canned HTTP reply, and records where it connected."""

    def __init__(self, reply: bytes = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok") -> None:
        self.reply = reply
        self.connected: list[str] = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected.append(host)
        return httpcore2.AsyncMockStream([self.reply])

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AssertionError("not used")

    async def sleep(self, seconds):
        pass


def resolving_to(*answers: list[str]):
    """A resolver that gives each answer in turn, as a name changing its address would."""
    queue = list(answers)

    async def resolve(host, port):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return resolve


@pytest.mark.anyio
async def test_a_name_that_resolves_to_a_private_address_is_refused_before_connecting():
    wire = Wire()
    backend = PublicOnlyBackend(resolving_to(["10.0.0.7"]), wire)
    with pytest.raises(BlockedAddress, match=r"docs\.example\.com resolves to 10\.0\.0\.7"):
        await backend.connect_tcp("docs.example.com", 443)
    assert wire.connected == []


@pytest.mark.anyio
async def test_one_private_address_among_public_ones_is_enough_to_refuse():
    backend = PublicOnlyBackend(resolving_to(["93.184.215.14", "127.0.0.1"]), Wire())
    with pytest.raises(BlockedAddress, match=r"127\.0\.0\.1"):
        await backend.connect_tcp("docs.example.com", 443)


@pytest.mark.anyio
async def test_the_connection_goes_to_the_address_that_was_checked():
    wire = Wire()
    await PublicOnlyBackend(resolving_to(["93.184.215.14"]), wire).connect_tcp("docs.example.com", 443)
    assert wire.connected == ["93.184.215.14"]  # not the name, which could resolve differently a second time


@pytest.mark.anyio
@pytest.mark.parametrize("url", ["http://127.0.0.1:9/", "http://localhost:9/", "http://[::1]:9/"])
async def test_the_real_transport_refuses_this_machine(url):
    async with httpx2.AsyncClient(transport=PublicOnlyTransport()) as client:
        with pytest.raises(BlockedAddress):
            await client.get(url)


@pytest.mark.anyio
async def test_a_redirect_is_checked_again_when_the_name_now_resolves_inside():
    """DNS rebinding: public for the first request, private for the redirect's connection."""
    redirect = (
        b"HTTP/1.1 301 Moved Permanently\r\nLocation: /help/new\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"
    )
    wire = Wire(redirect)
    transport = PublicOnlyTransport(resolving_to(["93.184.215.14"], ["169.254.169.254"]), wire)
    async with httpx2.AsyncClient(transport=transport) as client:
        fetcher = Fetcher(client, Scope.of("https://docs.example.com/help/"), agent="CitemarkBot (+test)", interval=0)
        with pytest.raises(BlockedAddress, match=r"169\.254\.169\.254"):
            await fetcher.get("https://docs.example.com/help/old")
    assert wire.connected == ["93.184.215.14"]
