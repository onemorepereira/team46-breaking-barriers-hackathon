"""Serve the sandbox console behind code-server's authenticated /proxy/<port>/ URL."""

from __future__ import annotations

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


class WorkshopProxy:
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

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        content_type = ""

        async def proxy_send(message):
            nonlocal content_type
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
                message = {**message, "headers": headers}
            elif message["type"] == "http.response.body" and message.get("body"):
                if any(t in content_type for t in ("text/html", "javascript", "json", "text/event-stream")):
                    message = {
                        **message,
                        "body": rewrite(message["body"], content_type, scope["path"], self.prefix),
                    }
            if (
                message["type"] == "http.response.body"
                and "text/html" in content_type
                and not scope["path"].startswith("/workspace")
            ):
                message = {
                    **message,
                    "body": re.sub(
                        rb"(<body[^>]*>)",
                        lambda m: m[1] + self.notice.encode(),
                        message.get("body", b""),
                        count=1,
                    ),
                }
            await send(message)

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
