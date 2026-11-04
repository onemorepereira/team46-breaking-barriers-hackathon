"""LGND login through the event Kiro's authenticated proxy; no token is printed."""

from __future__ import annotations

import base64
import hashlib
import html
import http.server
import secrets
import threading
import urllib.parse

import boto3

from harness.config import load
from scripts.adi_sandbox import check_identity
from tools.lgnd.auth import LGND_RESOURCE, post_form
from tools.lgnd.descriptors import RESOURCE_METADATA
from tools.lgnd.login import SCOPES, _get_json, _post_json, _save

PORT = 8765
CALLBACK = "https://d37rt8nwcs1lq3.cloudfront.net/proxy/8765/callback"
SECRET_NAME = "team46-adi-lgnd"


def main() -> int:
    cfg = load()
    check_identity(boto3.client("sts", region_name="us-west-2").get_caller_identity(), cfg)
    sm = boto3.client("secretsmanager", region_name="us-west-2")
    try:
        arn = sm.describe_secret(SecretId=SECRET_NAME)["ARN"]
    except sm.exceptions.ResourceNotFoundException:
        arn = sm.create_secret(Name=SECRET_NAME, Description="Aditya Team46 event LGND OAuth login")["ARN"]
    issuer = _get_json(RESOURCE_METADATA)["authorization_servers"][0].rstrip("/")
    meta = _get_json(issuer + "/.well-known/oauth-authorization-server")
    client = _post_json(
        meta["registration_endpoint"],
        {
            "client_name": "team46-adi-event-sandbox",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "redirect_uris": [CALLBACK],
        },
    )
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(32)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client["client_id"],
            "redirect_uri": CALLBACK,
            "scope": SCOPES,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": LGND_RESOURCE,
        }
    )
    auth_url = meta["authorization_endpoint"] + "?" + query
    finished = threading.Event()
    result = {"ok": False}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urllib.parse.urlparse(self.path)
            if path.path == "/":
                body = (
                    "<!doctype html><title>Connect LGND to Aditya event sandbox</title>"
                    "<h1>Connect LGND Geo</h1><p>This stores your LGND login only in event AWS account "
                    "952337755619, in the team46-adi-lgnd secret. No AWS keys are requested.</p>"
                    '<p><a href="' + html.escape(auth_url, quote=True) + '">Sign in to LGND Geo</a></p>'
                )
            elif path.path == "/callback":
                values = dict(urllib.parse.parse_qsl(path.query))
                if values.get("state") != state or not values.get("code"):
                    self.send_error(400, "Login state invalid or authorization declined")
                    return
                try:
                    tok = post_form(
                        meta["token_endpoint"],
                        {
                            "grant_type": "authorization_code",
                            "code": values["code"],
                            "redirect_uri": CALLBACK,
                            "client_id": client["client_id"],
                            "code_verifier": verifier,
                            "resource": LGND_RESOURCE,
                        },
                    )
                    if _save(arn, "us-west-2", client["client_id"], tok, meta["token_endpoint"]):
                        raise RuntimeError("No refresh token issued")
                    from pathlib import Path

                    import yaml

                    p = Path("harness.local.yaml")
                    config = yaml.safe_load(p.read_text())
                    config["lgnd_secret_id"] = arn
                    p.write_text(yaml.safe_dump(config, sort_keys=False))
                    result["ok"] = True
                    body = (
                        "<h1>LGND connected</h1>"
                        "<p>Login saved in your event sandbox. You can close this tab.</p>"
                    )
                except Exception as e:
                    print("LGND login failed:", type(e).__name__, flush=True)
                    body = (
                        "<h1>LGND login failed</h1>"
                        "<p>Check the workshop terminal. No credentials were displayed.</p>"
                    )
                finished.set()
            else:
                self.send_error(404)
                return
            encoded = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *args):
            pass  # Never log callback codes or query parameters.

    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("Open https://d37rt8nwcs1lq3.cloudfront.net/proxy/8765/ to connect LGND.", flush=True)
    try:
        finished.wait(900)
    finally:
        server.shutdown()
        server.server_close()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
