"""CDK app: archive bucket, agent image, role, one AgentCore runtime, budget, tags (design ADR-4).

Hardening (docs/aws-hardening/spec.md): the role follows AWS's documented AgentCore execution role; the archive
is versioned and access-logged; runtime logs expire; images are scanned on push."""

from __future__ import annotations

import os
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

REPO = Path(__file__).resolve().parents[1]


class HarnessStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, **kw: object) -> None:
        super().__init__(scope, cid, **kw)  # type: ignore[arg-type]
        # AC4: server access logs for the archive (S3 security best practices), kept 90 days
        access_logs = s3.Bucket(
            self,
            "ArchiveAccessLogs",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            lifecycle_rules=[s3.LifecycleRule(expiration=cdk.Duration.days(90))],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        bucket = s3.Bucket(
            self,
            "Archive",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,  # recorded runs survive cdk destroy
            # AC4: reviews and re-judging overwrite judgement.json; versions keep every earlier copy
            versioned=True,
            server_access_logs_bucket=access_logs,
            server_access_logs_prefix="archive/",
            lifecycle_rules=[
                s3.LifecycleRule(
                    noncurrent_version_expiration=cdk.Duration.days(90),
                    abort_incomplete_multipart_upload_after=cdk.Duration.days(7),
                )
            ],  # current objects never expire: the archive is the evidence
        )
        image = ecr_assets.DockerImageAsset(
            self, "AgentImage", directory=str(REPO), platform=ecr_assets.Platform.LINUX_ARM64
        )
        # AC1: confused-deputy conditions, as in AWS's AgentCore Runtime trust policy
        # (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
        role = iam.Role(
            self,
            "AgentRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com").with_conditions(
                {
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"},
                }
            ),
        )
        image.repository.grant_pull(role)
        role.add_to_policy(iam.PolicyStatement(actions=["ecr:GetAuthorizationToken"], resources=["*"]))
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*anthropic.claude-*",
                    "arn:aws:bedrock:*::foundation-model/moonshotai.kimi-*",
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*moonshotai.kimi-*",
                ],
            )
        )
        bucket.grant_put(role, "runs/*")
        bucket.grant_put(role, "suites/*")
        bucket.grant_read(role, "runs/*")
        # AC3: read-only, so RODA's signed reads of public open-data buckets work, but only for buckets other
        # accounts own: never another bucket in this account (the archive has its own grants above)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=["arn:aws:s3:::*"],
                conditions={"StringNotEquals": {"aws:ResourceAccount": self.account}},
            )
        )
        # AC2: logs, traces and metrics exactly as AWS's documented AgentCore Runtime execution role
        runtimes = f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogStreams", "logs:CreateLogGroup"], resources=[runtimes]
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:DescribeLogGroups"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"], resources=[f"{runtimes}:log-stream:*"]
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],  # X-Ray has no resource-level permissions for these (as in AWS's policy)
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            )
        )
        lgnd_secret = secretsmanager.Secret(
            self, "LgndGeoLogin", description="LGND Geo OAuth refresh token; set by `harness lgnd-login`"
        )
        lgnd_secret.grant_read(role)
        lgnd_secret.grant_write(role)  # the agent saves rotated refresh tokens
        runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name="team46_eval_harness",
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            protocol_configuration="HTTP",
            role_arn=role.role_arn,
            environment_variables={
                "HARNESS_EXPORTER": "adot",
                "HARNESS_ARCHIVE_URI": f"s3://{bucket.bucket_name}",
                "AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT": "true",
                "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental,gen_ai_tool_definitions",
                "OTEL_TRACES_SAMPLER": "always_on",
                "HARNESS_LGND_URL": "https://geo.lgnd.ai/mcp",
                "HARNESS_LGND_SECRET_ID": lgnd_secret.secret_arn,
            },
        )
        runtime.node.add_dependency(role)
        # AC5: the runtime's log group (created by AgentCore) keeps events 30 days, not forever
        logs.LogRetention(
            self,
            "RuntimeLogRetention",
            log_group_name=f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-DEFAULT",
            retention=logs.RetentionDays.ONE_MONTH,
        )
        # AC6: scan images on push (basic scanning) in the CDK container-asset repository. The registry has one
        # scanning configuration per account and Region; this stack owns it (it had no rules before).
        ecr.CfnRegistryScanningConfiguration(
            self,
            "ImageScanning",
            scan_type="BASIC",
            rules=[
                ecr.CfnRegistryScanningConfiguration.ScanningRuleProperty(
                    scan_frequency="SCAN_ON_PUSH",
                    repository_filters=[
                        ecr.CfnRegistryScanningConfiguration.RepositoryFilterProperty(
                            filter="cdk-*-container-assets-*", filter_type="WILDCARD"
                        )
                    ],
                )
            ],
        )
        email = self.node.try_get_context("budget_email") or os.environ.get("BUDGET_EMAIL")
        if email:
            budgets.CfnBudget(
                self,
                "Budget",
                budget=budgets.CfnBudget.BudgetDataProperty(
                    budget_type="COST", time_unit="MONTHLY",
                    budget_limit=budgets.CfnBudget.SpendProperty(amount=250, unit="USD"),
                ),
                notifications_with_subscribers=[
                    budgets.CfnBudget.NotificationWithSubscribersProperty(
                        notification=budgets.CfnBudget.NotificationProperty(
                            notification_type=kind, comparison_operator="GREATER_THAN", threshold=pct,
                            threshold_type="PERCENTAGE",
                        ),
                        subscribers=[budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email)],
                    )
                    for kind, pct in (("ACTUAL", 40), ("FORECASTED", 100))
                ],
            )  # fmt: skip
        cdk.CfnOutput(self, "ArchiveUri", value=f"s3://{bucket.bucket_name}")
        cdk.CfnOutput(self, "RuntimeArn", value=runtime.attr_agent_runtime_arn)
        cdk.CfnOutput(self, "LgndSecretArn", value=lgnd_secret.secret_arn)


def build(app: cdk.App) -> HarnessStack:
    stack = HarnessStack(app, "Team46EvalHarness", env=cdk.Environment(region="us-west-2"))
    for k, v in {
        "Project": "team46-eval-harness",
        "Owner": "team46",
        "CostCenter": "hackathon-sandbox",
    }.items():
        cdk.Tags.of(app).add(k, v)
    return stack


if __name__ == "__main__":  # `cdk synth` / `cdk deploy` (cdk.json); tests import build() instead
    app = cdk.App()
    build(app)
    app.synth()
