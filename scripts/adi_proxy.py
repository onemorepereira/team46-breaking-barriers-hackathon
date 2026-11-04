"""Serve the sandbox console behind code-server's authenticated /proxy/<port>/ URL."""

from __future__ import annotations

import codecs
import re
from typing import Any


def rewrite(data: bytes, content_type: str, path: str, prefix: str) -> bytes:
    if "javascript" in content_type and path.rsplit("/", 1)[-1] not in (
        "app.js",
        "runs.js",
        "api-docs.js",
        "guidance.js",
        "adb.js",
    ):
        return data
    text = data.decode("utf-8")
    if "text/html" in content_type:
        text = re.sub(r"""((?:href|src|action)=["'])/(?!/)""", lambda m: m[1] + prefix + "/", text)
    elif "javascript" in content_type and path.rsplit("/", 1)[-1] in (
        "app.js",
        "runs.js",
        "api-docs.js",
        "guidance.js",
        "adb.js",
    ):
        text = re.sub(r"""(["'`])/(?!/)(?=[a-z])""", lambda m: m[1] + prefix + "/", text)
    elif "json" in content_type or "text/event-stream" in content_type:
        text = re.sub(
            r"""(?<!\\)("(?:tile_url|events)"\s*:\s*")/(?!/)""", lambda m: m[1] + prefix + "/", text
        )
    return text.encode("utf-8")


REWRITE_TYPES = ("text/html", "javascript", "json", "text/event-stream")


class WorkshopProxy:
    """Rewrites root-relative URLs to sit under /proxy/<port>/.

    Bodies arrive in chunks (FileResponse and StreamingResponse send about 64 KB at a time), so rewriting
    per chunk could split a multi-byte character (UnicodeDecodeError) or a URL pattern (left unrewritten).
    Instead, HTML, JavaScript and JSON bodies are buffered whole and rewritten once; an event stream is
    rewritten one complete event at a time (events end with a blank line), with UTF-8 decoded
    incrementally so a character split across chunks is carried over intact.
    """

    def __init__(self, app: Any, port: int, lgnd_enabled: bool = False):
        self.app = app
        self.notice = (
            '<div role="status" class="alert alert-info m-3">Aditya event sandbox: real AWS Bedrock. '
            + (
                "AWS Open Data and LGND connected."
                if lgnd_enabled
                else (
                    "AWS Open Data connected. LGND imagery is not connected; "
                    "imagery examples need a separate login."
                )
            )
            + "</div>"
        )
        self.prefix = f"/proxy/{port}"

    def _finish(self, body: bytes, content_type: str, path: str) -> bytes:
        body = rewrite(body, content_type, path, self.prefix)
        if "text/html" in content_type and not path.startswith("/workspace"):
            body = re.sub(rb"(<body[^>]*>)", lambda m: m[1] + self.notice.encode(), body, count=1)
        return body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        content_type = ""
        buffered: list[bytes] = []
        decoder = codecs.getincrementaldecoder("utf-8")()
        pending = ""

        async def proxy_send(message):
            nonlocal content_type, pending
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                content_type = next((v.decode() for k, v in headers if k.lower() == b"content-type"), "")
                headers = [(k, v) for k, v in headers if k.lower() not in (b"content-length", b"etag")]
                headers = [
                    (
                        k,
                        (self.prefix + v.decode()).encode()
                        if k.lower() == b"location" and v.startswith(b"/")
                        else v,
                    )
                    for k, v in headers
                ]
                await send({**message, "headers": headers})
                return
            if message["type"] != "http.response.body" or not any(t in content_type for t in REWRITE_TYPES):
                await send(message)
                return
            more = bool(message.get("more_body"))
            chunk = message.get("body", b"")
            if "text/event-stream" in content_type:
                pending += decoder.decode(chunk, final=not more)
                cut = pending.rfind("\n\n") + 2 if more else len(pending)  # whole events only
                ready, pending = pending[:cut], pending[cut:]
                body = self._finish(ready.encode("utf-8"), content_type, scope["path"]) if ready else b""
                await send({**message, "body": body})
                return
            buffered.append(chunk)
            if more:
                return  # send once, whole, when the last chunk arrives
            await send({**message, "body": self._finish(b"".join(buffered), content_type, scope["path"])})

        await self.app(scope, receive, proxy_send)


def serve(cfg: Any, port: int) -> int:
    import uvicorn

    from harness.web.app import create_app

    print(f"Workshop UI: /proxy/{port}/ (uses existing code-server authentication)", flush=True)
    uvicorn.run(
        WorkshopProxy(create_app(cfg), port, bool(cfg.get("lgnd_secret_id"))),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    return 0
