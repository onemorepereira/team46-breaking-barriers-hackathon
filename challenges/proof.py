"""Live judge proof. OAuth secrets stay private on the workshop host."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import boto3

ROOT = Path("out/challenges")


def request(url, payload, headers):
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=payload, headers=headers, method="POST"), timeout=240
        ) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:5000]


def token(state):
    private = json.loads((ROOT / "oauth-client.private.json").read_text())
    basic = base64.b64encode((private["client_id"] + ":" + private["client_secret"]).encode()).decode()
    status, text = request(
        state["oauth_domain"] + "/oauth2/token",
        urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "team46/invoke"}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded", "Authorization": "Basic " + basic},
    )
    if status != 200:
        raise RuntimeError("OAuth token endpoint failed: " + str(status))
    return json.loads(text)["access_token"]


def run():
    state = json.loads((ROOT / "resources.json").read_text())
    ident = boto3.client("sts", region_name="us-west-2").get_caller_identity()
    if ident["Account"] != "952337755619" or ":assumed-role/WSParticipantRole/" not in ident["Arn"]:
        raise RuntimeError("Wrong account")
    br = boto3.client("bedrock-agent", region_name="us-west-2")
    ingestion = br.get_ingestion_job(
        knowledgeBaseId=state["kb_id"],
        dataSourceId=state["data_source"],
        ingestionJobId=state["ingestion_job"],
    )["ingestionJob"]
    if ingestion["status"] != "COMPLETE":
        raise RuntimeError("Knowledge Base ingestion is " + ingestion["status"])
    url = (
        "https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/"
        + urllib.parse.quote(state["runtime_arn"], safe="")
        + "/invocations?qualifier=DEFAULT"
    )
    payload = json.dumps(
        {
            "prompt": (
                "How can Clay change its rubric without changing application code? "
                "What does a source match fail to prove? Cite the source document."
            )
        }
    ).encode()
    base = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "team46-judge-" + uuid.uuid4().hex,
    }
    unauth, _ = request(url, payload, base)
    good, text = request(url, payload, {**base, "Authorization": "Bearer " + token(state)})
    answer = json.loads(text) if good == 200 else {"error": text}
    proof = {
        "event_account": ident["Account"],
        "region": "us-west-2",
        "checked_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        "kb_id": state["kb_id"],
        "ingestion_status": ingestion["status"],
        "ingestion_statistics": ingestion.get("statistics"),
        "gateway_id": state["gateway_id"],
        "runtime_arn": state["runtime_arn"],
        "oauth_issuer": state["discovery_url"],
        "unauthenticated_http_status": unauth,
        "authenticated_http_status": good,
        "agent_result": answer,
    }
    proof["know_your_stuff_verified"] = (
        good == 200
        and bool(answer.get("sources"))
        and any(x.get("uri", "") in answer.get("answer", "") for x in answer.get("sources", []))
    )
    proof["gateway_builder_verified"] = (
        good == 200
        and len(answer.get("gateway_tools", [])) >= 3
        and answer.get("tool_call_succeeded") is True
    )
    proof["lock_front_door_verified"] = unauth in [401, 403] and good == 200
    (ROOT / "proof.json").write_text(json.dumps(proof, indent=2, default=str))
    return proof


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
