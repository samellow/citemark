"""A network guard for tests (QA plan 3.2): replies come from recordings, so a test may only
reach this machine, where Postgres runs. Anything else fails at once, by name."""

from __future__ import annotations

import ipaddress
import socket
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class NetworkBlocked(RuntimeError):
    pass


def _is_local(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _refuse(host: str) -> None:
    raise NetworkBlocked(
        f"Tests don't use the network, but this one tried to reach {host}. "
        "Replay a recording instead, or make one with --record."
    )


def block_network(patch: pytest.MonkeyPatch) -> None:
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def remote(sock: socket.socket, address) -> bool:
        return sock.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0])

    def guarded_connect(sock, address):
        if remote(sock, address):
            _refuse(address[0])
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        if remote(sock, address):
            _refuse(address[0])
        return connect_ex(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        name = host.decode() if isinstance(host, bytes) else host
        if name is not None and not _is_local(name):
            _refuse(name)
        return getaddrinfo(host, *args, **kwargs)

    patch.setattr(socket.socket, "connect", guarded_connect)
    patch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    patch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
