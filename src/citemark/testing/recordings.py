"""Recorded API replies for tests (QA plan 3.2): no test calls a live model on a commit.

`RecordingTransport` sits under any `httpx2` client, such as the Anthropic SDK's. When
replaying, it answers each request from a file, keyed by a hash of the request's method,
URL and JSON body. Headers aren't part of the key and are never saved, so no API key reaches
a recording. When recording, it sends the request for real and saves the reply.

Each file holds the request body as well as the reply, and a streamed reply is saved one
line per array entry, so a re-recording's diff shows what changed in the bot's output.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import httpx2


class MissingRecording(Exception):
    pass


def _missing(message: str) -> NoReturn:
    raise MissingRecording(message)


def request_key(method: str, url: str, content: bytes) -> tuple[str, Any]:
    """The recording's key, and the request body as saved: parsed JSON where it is JSON."""
    try:
        body = json.loads(content) if content else None
    except ValueError:
        body = content.decode("utf-8", errors="replace")
    canonical = json.dumps({"method": method, "url": url, "body": body}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16], body


class RecordingTransport(httpx2.AsyncBaseTransport):
    def __init__(
        self,
        folder: Path,
        *,
        record: bool = False,
        on_missing: Callable[[str], NoReturn] = _missing,
        upstream: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self.folder = folder
        self.record = record
        self.on_missing = on_missing
        self.upstream = upstream or (httpx2.AsyncHTTPTransport() if record else None)

    def path_for(self, request: httpx2.Request, key: str) -> Path:
        name = request.url.path.strip("/").replace("/", "-") or "root"
        return self.folder / f"{name}-{key}.json"

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        content = await request.aread()
        key, body = request_key(request.method, str(request.url), content)
        path = self.path_for(request, key)
        if self.record:
            assert self.upstream is not None
            live = await self.upstream.handle_async_request(request)
            reply = (await live.aread()).decode("utf-8")  # aread() undoes any gzip
            status, content_type = live.status_code, live.headers.get("content-type", "")
            await live.aclose()
            saved = {
                "request": {"method": request.method, "url": str(request.url), "body": body},
                "response": {"status": status, "content_type": content_type, "body": reply.split("\n")},
            }
            self.folder.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(saved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif path.exists():
            response = json.loads(path.read_text(encoding="utf-8"))["response"]
            status, content_type, reply = response["status"], response["content_type"], "\n".join(response["body"])
        else:
            self.on_missing(f"No recorded reply for {request.method} {request.url.path} ({path.name}).")
        return httpx2.Response(status, headers={"content-type": content_type}, content=reply.encode(), request=request)

    async def aclose(self) -> None:
        if self.upstream is not None:
            await self.upstream.aclose()
