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
