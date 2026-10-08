"""No internal addresses (PRD 5.1, QA plan G1): the crawler only connects to public hosts.

Whoever runs the admin page types the source address, so without this guard a crawl could
reach the client's internal network, or the cloud host's metadata service at 169.254.169.254.

The check runs where each connection is made, not before the request: the host name is
resolved, every address it resolves to must be public, and the connection goes to an address
that was checked. A redirect opens its connection the same way, so it's checked again. And a
name that resolves to a public address for a check but a private one for the connection
(DNS rebinding) can't get through, since there's no gap between the two.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable

import anyio
import httpcore2
import httpx2

from citemark.ingest import IngestError

Resolver = Callable[[str, int], Awaitable[list[str]]]

NAT64 = ipaddress.ip_network("64:ff9b::/96")  # an IPv4 address in the last 32 bits, reached through a gateway


class BlockedAddress(IngestError):
    def __init__(self, host: str, address: str | None) -> None:
        self.host, self.address = host, address
        where = f"resolves to {address}, which is" if address and address != host else "is"
        super().__init__(
            f"{host} {where} a private, loopback or link-local address, so it isn't crawled. "
            "Citemark only reads public sites."
            if address
            else f"{host} didn't resolve to any address."
        )


def is_public(address: str) -> bool:
    """Whether an address can be reached from the internet. IPv6 addresses that carry an IPv4
    address inside them are judged by that IPv4 address."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public(str(ip.ipv4_mapped))
        if ip in NAT64:
            return is_public(str(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)))
    return ip.is_global and not ip.is_multicast


async def resolve(host: str, port: int) -> list[str]:
    """Every address the name resolves to, in the order the system gives them."""
    found = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(sockaddr[0]) for *_, sockaddr in found))


class PublicOnlyBackend(httpcore2.AsyncNetworkBackend):
    """Opens a connection only to an address that was checked a moment before."""

    def __init__(self, resolver: Resolver = resolve, inner: httpcore2.AsyncNetworkBackend | None = None) -> None:
        self.resolver = resolver
        self.inner = inner or httpcore2.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore2.SOCKET_OPTION] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        with anyio.fail_after(timeout):
            addresses = await self.resolver(host, port)
        refused = next((address for address in addresses if not is_public(address)), None)
        if not addresses or refused:
            raise BlockedAddress(host, refused)
        error: Exception | None = None
        for address in addresses:  # like an ordinary connect, the next address if one doesn't answer
            try:
                return await self.inner.connect_tcp(
                    address, port, timeout=timeout, local_address=local_address, socket_options=socket_options
                )
            except httpcore2.ConnectError as exc:
                error = exc
        assert error is not None
        raise error

    async def connect_unix_socket(self, path: str, *args, **kwargs) -> httpcore2.AsyncNetworkStream:
        raise BlockedAddress(path, path)

    async def sleep(self, seconds: float) -> None:
        await self.inner.sleep(seconds)


class PublicOnlyTransport(httpx2.AsyncHTTPTransport):
    """An `httpx2` transport that never connects to an internal address, and never through a
    proxy from the environment, since the proxy would make the connection unchecked."""

    def __init__(self, resolver: Resolver = resolve, inner: httpcore2.AsyncNetworkBackend | None = None) -> None:
        super().__init__(trust_env=False)
        # The same pool the parent builds, with the guarded backend in place of the default
        self._pool = httpcore2.AsyncConnectionPool(
            ssl_context=httpx2.create_ssl_context(trust_env=False),
            max_connections=10,
            network_backend=PublicOnlyBackend(resolver, inner),
        )
