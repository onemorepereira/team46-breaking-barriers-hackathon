"""LGND Geo access token for a headless agent (spike S3): refresh-token grant against LGND's OAuth server.

The refresh token lives in Secrets Manager (written once by `harness lgnd-login`). If the server rotates it,
the new one is written back so the next run can still refresh.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Generator
from typing import Any

import httpx

log = logging.getLogger("harness.lgnd")
from tools.lgnd.descriptors import RESOURCE as LGND_RESOURCE  # noqa: E402

HTTP_TIMEOUT_S = 10
# Cloudflare in front of LGND's OAuth server rejects Python's default urllib User-Agent (error 1010).
USER_AGENT = "team46-eval-harness/0.1"


def post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded", "user-agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 - fixed https endpoints
        result: dict[str, Any] = json.loads(resp.read())
        return result


def access_token(secret_id: str, region: str, client: Any = None) -> str | None:
    """Return a fresh access token, or None (LGND is then skipped and recorded as unavailable)."""
    import boto3
    from botocore.config import Config

    sm = client or boto3.client(
        "secretsmanager", region_name=region, config=Config(connect_timeout=5, read_timeout=10)
    )
    raw = sm.get_secret_value(SecretId=secret_id).get("SecretString") or ""
    try:
        creds = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LGND secret %s is empty or not JSON; run `harness lgnd-login`", secret_id)
        return None
    if not creds.get("refresh_token"):
        log.warning("LGND secret %s has no refresh_token; run `harness lgnd-login`", secret_id)
        return None
    tok = post_form(
        creds["token_endpoint"],
        {
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["client_id"],
            "resource": creds.get("resource", LGND_RESOURCE),
        },
    )
    if tok.get("refresh_token") and tok["refresh_token"] != creds["refresh_token"]:
        sm.put_secret_value(
            SecretId=secret_id, SecretString=json.dumps({**creds, "refresh_token": tok["refresh_token"]})
        )
    token = tok.get("access_token")
    return str(token) if token else None


def token_expiry(token: str, now: float) -> float:
    """When a JWT access token expires (its `exp`), or now + 300 s if it can't be read (LGND's lifetime)."""
    import base64

    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return now + 300


class RefreshingBearer(httpx.Auth):
    """An `httpx.Auth` that keeps LGND's bearer token fresh for the whole run.

    LGND access tokens live 300 s (measured 2026-11-04: JWT exp - iat = 300). A token fetched once at
    startup made every LGND call fail after about 5 minutes (runs fdacf7cf, 2855dc1a). This refreshes the
    token REFRESH_MARGIN_S before it expires, and once more on a 401, retrying that request. httpx runs
    `auth_flow` for sync and async clients alike. The refresh is a short blocking HTTPS call (about once
    every 4 minutes), under a lock so that parallel tool calls refresh once.
    """

    REFRESH_MARGIN_S = 60

    def __init__(self, fetch: Any, first_token: str, clock: Any = None) -> None:
        self._fetch, self._clock = fetch, clock or time.time
        self._lock = threading.Lock()
        self._token, self._expires = first_token, token_expiry(first_token, self._clock())

    def _current(self, force: bool = False) -> str:
        with self._lock:
            if force or self._clock() >= self._expires - self.REFRESH_MARGIN_S:
                fresh = self._fetch()
                if fresh:
                    self._token, self._expires = fresh, token_expiry(fresh, self._clock())
                else:
                    log.warning("LGND token refresh failed; keeping the current token")
            return self._token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["authorization"] = f"Bearer {self._current()}"
        response = yield request
        if response.status_code == 401:
            request.headers["authorization"] = f"Bearer {self._current(force=True)}"
            yield request
