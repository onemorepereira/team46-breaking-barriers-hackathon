"""The CDK stack follows AWS's documented practice (docs/aws-hardening/spec.md AC1-AC6), checked on the
synthesized template. Needs the `infra` group: `uv run --group infra pytest tests/test_infra.py`."""

import importlib.util
import json
import re
from pathlib import Path

import pytest

cdk = pytest.importorskip("aws_cdk")
from aws_cdk import assertions  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def template():
    spec = importlib.util.spec_from_file_location("infra_app", REPO / "infra/app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # the __main__ guard keeps it from synthesizing on import
    ctx = json.loads((REPO / "infra/cdk.json").read_text())["context"]  # the same feature flags as cdk deploy
    app = cdk.App(context={**ctx, "aws:cdk:bundling-stacks": []})
    stack = mod.build(app)
    return assertions.Template.from_stack(stack)


def role_statements(t):
    """The agent role's statements only (CDK's log-retention Lambda has its own role and policy)."""
    return [s for p in t.find_resources("AWS::IAM::Policy").values()
            if any(r.get("Ref", "").startswith("AgentRole") for r in p["Properties"]["Roles"])
            for s in p["Properties"]["PolicyDocument"]["Statement"]]  # fmt: skip


def as_list(x):
    return x if isinstance(x, list) else [x]


def test_trust_policy_has_confused_deputy_conditions(template):  # AC1
    roles = template.find_resources("AWS::IAM::Role")
    agent = next(r for k, r in roles.items() if k.startswith("AgentRole"))
    (stmt,) = agent["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    assert stmt["Principal"] == {"Service": "bedrock-agentcore.amazonaws.com"}
    assert "aws:SourceAccount" in stmt["Condition"]["StringEquals"]
    assert "aws:SourceArn" in stmt["Condition"]["ArnLike"]


def test_no_logs_action_on_star_and_metrics_are_namespaced(template):  # AC2
    for s in role_statements(template):
        actions = as_list(s["Action"])
        if any(a.startswith("logs:") for a in actions):
            assert s["Resource"] != "*" and "*" not in as_list(s["Resource"]), s
            text = json.dumps(s["Resource"])
            if "logs:DescribeLogGroups" not in actions:
                assert "/aws/bedrock-agentcore/runtimes/*" in text, s
        if "cloudwatch:PutMetricData" in actions:
            assert s["Condition"]["StringEquals"]["cloudwatch:namespace"] == "bedrock-agentcore"


def test_open_data_reads_exclude_this_accounts_buckets(template):  # AC3
    (stmt,) = [s for s in role_statements(template) if s.get("Resource") == "arn:aws:s3:::*"]
    assert set(as_list(stmt["Action"])) == {"s3:GetObject", "s3:ListBucket"}
    assert "aws:ResourceAccount" in stmt["Condition"]["StringNotEquals"]


def test_archive_is_versioned_logged_and_never_expires_current_objects(template):  # AC4
    buckets = template.find_resources("AWS::S3::Bucket")
    archive = buckets["ArchiveDA4CB258"]["Properties"]  # deployed logical ID: no replacement
    logsb = next(b for k, b in buckets.items() if k.startswith("ArchiveAccessLogs"))
    assert archive["VersioningConfiguration"] == {"Status": "Enabled"}
    assert archive["LoggingConfiguration"]["LogFilePrefix"] == "archive/"
    (rule,) = archive["LifecycleConfiguration"]["Rules"]
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7
    assert "ExpirationInDays" not in rule
    assert logsb["DeletionPolicy"] == "Retain"
    p = logsb["Properties"]
    assert p["PublicAccessBlockConfiguration"]["BlockPublicPolicy"] is True
    assert p["LifecycleConfiguration"]["Rules"][0]["ExpirationInDays"] == 90


def test_runtime_logs_expire_after_30_days(template):  # AC5
    (r,) = template.find_resources("Custom::LogRetention").values()
    assert r["Properties"]["RetentionInDays"] == 30
    assert "/aws/bedrock-agentcore/runtimes/" in json.dumps(r["Properties"]["LogGroupName"])


def test_images_are_scanned_on_push(template):  # AC6
    (r,) = template.find_resources("AWS::ECR::RegistryScanningConfiguration").values()
    (rule,) = r["Properties"]["Rules"]
    assert rule["ScanFrequency"] == "SCAN_ON_PUSH"
    assert rule["RepositoryFilters"] == [{"Filter": "cdk-*-container-assets-*", "FilterType": "WILDCARD"}]


def test_container_runs_as_non_root_with_pinned_tracing():  # AC6
    text = (REPO / "Dockerfile").read_text()
    users = re.findall(r"^USER (\S+)", text, re.M)
    assert users and users[-1] not in ("root", "0")
    assert re.search(r'aws-opentelemetry-distro==\d+\.\d+\.\d+"', text)
