import pytest

from scripts.adi_sandbox import check_identity

GOOD = {"Account": "952337755619", "Arn": "arn:aws:sts::952337755619:assumed-role/WSParticipantRole/i-test"}
CFG = {"region": "us-west-2", "archive_uri": "file://./archive", "local_archive_uri": "file://./archive"}


def test_guard_accepts_workshop_and_refuses_wrong_identity(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    check_identity(GOOD, CFG)
    with pytest.raises(ValueError):
        check_identity({**GOOD, "Account": "000000000000"}, CFG)
    with pytest.raises(ValueError):
        check_identity({**GOOD, "Arn": "arn:aws:iam::952337755619:user/personal"}, CFG)


def test_guard_refuses_inherited_resources_and_profile(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for extra in [
        {"region": "us-east-1"},
        {"archive_uri": "s3://miguel"},
        {"lgnd_secret_id": "arn:aws:secretsmanager:us-west-2:892605951158:secret:other"},
    ]:
        with pytest.raises(ValueError):
            check_identity(GOOD, {**CFG, **extra})
    monkeypatch.setenv("AWS_PROFILE", "personal")
    with pytest.raises(ValueError):
        check_identity(GOOD, CFG)


def test_workshop_proxy_rewrites_application_urls_not_external_or_escaped_evidence():
    from scripts.adi_proxy import rewrite

    assert (
        rewrite(b'<script src="/static/app.js"></script>', "text/html", "/", "/proxy/8787")
        == b'<script src="/proxy/8787/static/app.js"></script>'
    )
    assert (
        rewrite(b"fetch(`/api/runs`)", "javascript", "/static/app.js", "/proxy/8787")
        == b"fetch(`/proxy/8787/api/runs`)"
    )
    assert (
        rewrite(b'{"tile_url":"/tiles/a"}', "application/json", "/api/runs", "/proxy/8787")
        == b'{"tile_url":"/proxy/8787/tiles/a"}'
    )
    raw = rb'{"text":"\"tile_url\":\"/original\""}'
    assert rewrite(raw, "application/json", "/api/runs", "/proxy/8787") == raw
    assert (
        rewrite(b"https://example.com/", "javascript", "/static/app.js", "/proxy/8787")
        == b"https://example.com/"
    )


def _run_proxy(content_type: str, chunks: list[bytes], path: str = "/x") -> bytes:
    import asyncio

    from scripts.adi_proxy import WorkshopProxy

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", content_type.encode()), (b"content-length", b"999")],
            }
        )
        for i, c in enumerate(chunks):
            await send({"type": "http.response.body", "body": c, "more_body": i < len(chunks) - 1})

    sent: list[dict] = []

    async def send(m):
        sent.append(m)

    asyncio.run(WorkshopProxy(app, 8787)({"type": "http", "path": path}, None, send))
    return b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


def test_proxy_rewrites_across_chunk_boundaries_and_split_utf8():
    html = 'São Paulo — <a href="/runs">runs</a>'.encode()
    split = html.index("—".encode()) + 1  # inside the 3-byte em dash
    cut = html.index(b'href="/') + 4  # inside the URL pattern
    out = _run_proxy("text/html; charset=utf-8", [html[:split], html[split:cut], html[cut:]]).decode()
    assert "São Paulo — " in out and 'href="/proxy/8787/runs"' in out


def test_proxy_rewrites_event_streams_one_whole_event_at_a_time():
    ev1 = 'data: {"events": "/api/runs/1/events", "label": "Nîmes"}\n\n'.encode()
    ev2 = b'data: {"tile_url": "/tiles/chip/1/x.jpg"}\n\n'
    body = ev1 + ev2
    mid = ev1.index("î".encode()) + 1  # inside the 2-byte character
    pieces = [body[:20], body[20:mid], body[mid : len(ev1) + 15], body[len(ev1) + 15 :]]
    out = _run_proxy("text/event-stream", pieces).decode()
    assert '"events": "/proxy/8787/api/runs/1/events"' in out and "Nîmes" in out
    assert '"tile_url": "/proxy/8787/tiles/chip/1/x.jpg"' in out
