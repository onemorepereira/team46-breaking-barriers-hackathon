"""`harness lgnd-login`: one-time OAuth device login to LGND Geo (spike S3), refresh token to Secrets Manager.

Discovery follows the server's own metadata: /mcp answers 401 with a resource_metadata URL, which names the
authorization server; its metadata gives the registration, device and token endpoints.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from agent.lgnd_auth import HTTP_TIMEOUT_S, LGND_RESOURCE, post_form

RESOURCE_METADATA = "https://geo.lgnd.ai/.well-known/oauth-protected-resource/mcp"
SCOPES = "openid profile email offline_access"


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 - fixed https endpoints
        result: dict[str, Any] = json.loads(resp.read())
        return result


def _post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"content-type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310
        result: dict[str, Any] = json.loads(resp.read())
        return result


def login(secret_id: str, region: str, wait_s: int = 600) -> int:
    issuer = _get_json(RESOURCE_METADATA)["authorization_servers"][0].rstrip("/")
    meta = _get_json(f"{issuer}/.well-known/oauth-authorization-server")
    client = _post_json(
        meta["registration_endpoint"],
        {
            "client_name": "team46-eval-harness",
            "grant_types": ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"],
            "token_endpoint_auth_method": "none",
            "redirect_uris": ["http://127.0.0.1/callback"],
        },
    )
    client_id = client["client_id"]
    dev = post_form(
        meta["device_authorization_endpoint"],
        {"client_id": client_id, "scope": SCOPES, "resource": LGND_RESOURCE},
    )
    url = dev.get("verification_uri_complete") or dev["verification_uri"]
    print(f"Open {url} and confirm the code {dev['user_code']} to sign in to LGND Geo.")
    interval, deadline = (
        int(dev.get("interval", 5)),
        time.monotonic() + min(wait_s, int(dev.get("expires_in", 600))),
    )
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            tok = post_form(
                meta["token_endpoint"],
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": dev["device_code"],
                    "client_id": client_id,
                    "resource": LGND_RESOURCE,
                },
            )
        except urllib.error.HTTPError as e:
            err = json.loads(e.read() or b"{}").get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            print(f"LGND login failed: {err or e}")
            return 1
        if not tok.get("refresh_token"):
            print("LGND login succeeded but no refresh token was issued (offline_access not granted).")
            return 1
        import boto3

        boto3.client("secretsmanager", region_name=region).put_secret_value(
            SecretId=secret_id,
            SecretString=json.dumps(
                {
                    "client_id": client_id,
                    "refresh_token": tok["refresh_token"],
                    "token_endpoint": meta["token_endpoint"],
                    "resource": LGND_RESOURCE,
                }
            ),
        )
        print(f"LGND Geo login saved to {secret_id}. The agent will use it on its next run.")
        return 0
    print("LGND login timed out; run `harness lgnd-login` again.")
    return 1
