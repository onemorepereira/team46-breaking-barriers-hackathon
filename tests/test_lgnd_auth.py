"""Spike S3 wiring: refresh-token exchange, rotation write-back, and the 'not logged in' path."""

import json

from tools.lgnd import auth as lgnd_auth


class FakeSecrets:
    def __init__(self, value):
        self.value = value
        self.writes = []

    def get_secret_value(self, SecretId):  # noqa: N803 - boto3 API
        return {"SecretString": self.value}

    def put_secret_value(self, SecretId, SecretString):  # noqa: N803
        self.writes.append(json.loads(SecretString))


CREDS = {"client_id": "c1", "refresh_token": "r1", "token_endpoint": "https://as.example/token",
         "resource": "https://geo.lgnd.ai/mcp"}  # fmt: skip


def test_refresh_returns_access_token_and_saves_rotated_refresh(monkeypatch):
    calls = []

    def fake_post(url, fields):
        calls.append((url, fields))
        return {"access_token": "a1", "refresh_token": "r2"}

    monkeypatch.setattr(lgnd_auth, "post_form", fake_post)
    sm = FakeSecrets(json.dumps(CREDS))
    assert lgnd_auth.access_token("arn:secret", "us-west-2", client=sm) == "a1"
    assert (
        calls[0][1]["grant_type"] == "refresh_token" and calls[0][1]["resource"] == "https://geo.lgnd.ai/mcp"
    )
    assert sm.writes == [{**CREDS, "refresh_token": "r2"}]


def test_no_rotation_no_write(monkeypatch):
    monkeypatch.setattr(lgnd_auth, "post_form", lambda u, f: {"access_token": "a1"})
    sm = FakeSecrets(json.dumps(CREDS))
    assert lgnd_auth.access_token("s", "us-west-2", client=sm) == "a1" and sm.writes == []


def test_empty_secret_means_not_logged_in(monkeypatch):
    monkeypatch.setattr(lgnd_auth, "post_form", lambda u, f: (_ for _ in ()).throw(AssertionError("no call")))
    assert lgnd_auth.access_token("s", "us-west-2", client=FakeSecrets("")) is None
    assert (
        lgnd_auth.access_token("s", "us-west-2", client=FakeSecrets(json.dumps({"client_id": "c"}))) is None
    )


# ---------- RefreshingBearer (docs/console-polish AC8): LGND tokens live 300 s ----------
import base64  # noqa: E402

import httpx  # noqa: E402

from tools.lgnd.auth import RefreshingBearer, token_expiry  # noqa: E402


def jwt(exp: int) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"iat": exp - 300, "exp": exp}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


def test_token_is_refreshed_before_it_expires_and_on_a_401():
    clock = [1000.0]
    issued = iter([jwt(1600), jwt(1900), jwt(2200)])
    fetches = []

    def fetch():
        fetches.append(clock[0])
        return next(issued)

    seen = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(401 if request.headers["authorization"] == f"Bearer {jwt(1600)}" else 200)

    auth = RefreshingBearer(fetch, jwt(1300), clock=lambda: clock[0])
    with httpx.Client(transport=httpx.MockTransport(server), auth=auth) as client:
        assert client.get("https://geo.example/mcp").status_code == 200  # fresh enough: no refresh
        assert seen == [f"Bearer {jwt(1300)}"] and fetches == []
        clock[0] = 1250.0  # within 60 s of expiry: refreshed before sending
        assert client.get("https://geo.example/mcp").status_code == 200  # 401 on jwt(1600), retried once
        assert seen[1:] == [f"Bearer {jwt(1600)}", f"Bearer {jwt(1900)}"] and len(fetches) == 2


def test_unreadable_token_assumes_lgnds_300_second_lifetime():
    assert token_expiry("opaque-token", now=50.0) == 350.0
    assert token_expiry(jwt(1234), now=0) == 1234.0
