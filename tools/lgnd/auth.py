"""LGND Geo access token for a headless agent (spike S3): refresh-token grant against LGND's OAuth server.

The refresh token lives in Secrets Manager (written once by `harness lgnd-login`). If the server rotates it,
the new one is written back so the next run can still refresh.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

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
