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

from agent.lgnd_auth import HTTP_TIMEOUT_S, LGND_RESOURCE, USER_AGENT, post_form

RESOURCE_METADATA = "https://geo.lgnd.ai/.well-known/oauth-protected-resource/mcp"
SCOPES = "openid profile email offline_access"


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 - fixed https endpoints
        result: dict[str, Any] = json.loads(resp.read())
        return result


def _post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "user-agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310
        result: dict[str, Any] = json.loads(resp.read())
        return result


def _save(secret_id: str, region: str, client_id: str, tok: dict[str, Any], token_endpoint: str) -> int:
    if not tok.get("refresh_token"):
        print(
            "LGND login succeeded but no refresh token was issued (offline_access not granted).", flush=True
        )
        return 1
    import boto3

    boto3.client("secretsmanager", region_name=region).put_secret_value(
        SecretId=secret_id,
        SecretString=json.dumps(
            {
                "client_id": client_id,
                "refresh_token": tok["refresh_token"],
                "token_endpoint": token_endpoint,
                "resource": LGND_RESOURCE,
            }
        ),
    )
    print(f"LGND Geo login saved to {secret_id}. The agent will use it on its next run.", flush=True)
    return 0


def login_browser(secret_id: str, region: str, port: int = 8765, wait_s: int = 600) -> int:
    """Authorization code + PKCE with a one-shot localhost callback (the flow MCP clients use)."""
    import base64
    import hashlib
    import http.server
    import secrets
    import threading
    import urllib.parse
    import webbrowser

    issuer = _get_json(RESOURCE_METADATA)["authorization_servers"][0].rstrip("/")
    meta = _get_json(f"{issuer}/.well-known/oauth-authorization-server")
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    client = _post_json(
        meta["registration_endpoint"],
        {
            "client_name": "team46-eval-harness",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "redirect_uris": [redirect_uri],
        },
    )
    client_id = client["client_id"]
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": LGND_RESOURCE,
        }
    )
    got: dict[str, str] = {}
    done = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if urllib.parse.urlparse(self.path).path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            got.update(params)
            ok = params.get("state") == state and "code" in params
            self.send_response(200)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.end_headers()
            msg = "LGND login received. You can close this tab." if ok else f"LGND login failed: {params}"
            self.wfile.write(msg.encode())
            done.set()

        def log_message(self, *args: Any) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", port), Callback)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"{meta['authorization_endpoint']}?{query}"
    print(f"Opening your browser to sign in to LGND Geo. If it doesn't open, visit:\n{url}", flush=True)
    webbrowser.open(url)
    try:
        if not done.wait(wait_s):
            print("LGND login timed out; run `harness lgnd-login` again.", flush=True)
            return 1
    finally:
        server.shutdown()
    if got.get("state") != state or "code" not in got:
        print(f"LGND login failed: {got.get('error_description') or got.get('error') or got}", flush=True)
        return 1
    try:
        tok = post_form(
            meta["token_endpoint"],
            {
                "grant_type": "authorization_code",
                "code": got["code"],
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": verifier,
                "resource": LGND_RESOURCE,
            },
        )
    except urllib.error.HTTPError as e:
        print(f"LGND token exchange failed: HTTP {e.code} {(e.read() or b'')[:300].decode(errors='replace')}")
        return 1
    return _save(secret_id, region, client_id, tok, meta["token_endpoint"])


def login_device(secret_id: str, region: str, wait_s: int = 600) -> int:
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
    print(f"Open {url} and confirm the code {dev['user_code']} to sign in to LGND Geo.", flush=True)
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
