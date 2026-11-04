# AWS Hardening: Spec

**Track:** Quick   **Product stage:** Introduction   **Status:** Built ([handoff](handoff.md))   **Last updated:** 2026-11-04

## Problem
The deployed stack (`infra/app.py`) falls short of AWS's documented practice in six places. A read-only check of the sandbox account on 2026-11-04 found:
- the agent role can read every S3 bucket in the account;
- its trust policy has no confused-deputy conditions;
- its CloudWatch Logs permissions are on `*`;
- the evidence archive is unversioned and unlogged, though reviews now overwrite `judgement.json`;
- the AgentCore log group never expires;
- the agent container runs as root, with an unpinned tracing dependency and no image scanning.

## Acceptance criteria
- [x] **AC1 Trust policy.** The agent role's trust policy allows `bedrock-agentcore.amazonaws.com` only with `aws:SourceAccount` set to the stack's account and `aws:SourceArn` matching `arn:aws:bedrock-agentcore:<region>:<account>:*`, as in AWS's [AgentCore Runtime trust policy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-trust-policy).
- [x] **AC2 Logs and metrics scoped.** These match the [documented execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-execution-role):
  - `logs:CreateLogGroup` and `logs:DescribeLogStreams` are on `log-group:/aws/bedrock-agentcore/runtimes/*`;
  - `logs:CreateLogStream` and `logs:PutLogEvents` are on `…/runtimes/*:log-stream:*`;
  - `logs:DescribeLogGroups` is on `log-group:*`;
  - `cloudwatch:PutMetricData` is conditioned on `cloudwatch:namespace = bedrock-agentcore`.

  No logs action remains on `Resource: "*"`. The IAM policy simulator denies `logs:PutLogEvents` on any other log group, and allows it on the runtime's own.
- [x] **AC3 S3 reads limited to other accounts' buckets.** The open-data read statement (`s3:GetObject`, `s3:ListBucket` on `arn:aws:s3:::*`) only applies where `aws:ResourceAccount` is **not** the stack's account ([condition key](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-resourceaccount)). The archive grants (`runs/*`, `suites/*`) are unchanged. The simulator shows:
  - a read of `s3://cdk-hnb659fds-assets-…/x`, in our account, is denied;
  - a read of `runs/x` in the archive is allowed;
  - a read of a public bucket owned by another account is allowed.
- [x] **AC4 Archive bucket protected.**
  - **Versioning** is enabled.
  - **Server access logs** go to a new logs bucket in the stack. That bucket blocks public access, uses SSE-S3, requires TLS, is retained on stack delete, and expires objects after 90 days.
  - **Lifecycle rules:** noncurrent versions expire after 90 days, and incomplete multipart uploads are aborted after 7 days.
  - **Current objects never expire.**

  Per [S3 security best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).
- [x] **AC5 Log retention.** The runtime's log group, `/aws/bedrock-agentcore/runtimes/<runtime id>-DEFAULT`, keeps events for 30 days. This is set in code with CDK `logs.LogRetention`, which creates the group if missing and sets the retention if it exists ([CDK docs](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_logs/LogRetention.html)).
- [x] **AC6 Container.**
  - The image runs as a non-root user, following ECS guidance: "You should run containers as a non-root user" ([ECS container security](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/security-tasks-containers.html)).
  - `aws-opentelemetry-distro` is pinned to an exact version: 0.22.0, the latest on PyPI on 2026-11-04.
  - The registry scans images on push, using basic scanning, for the CDK container-asset repository (`cdk-*-container-assets-*`), set by `aws_ecr.CfnRegistryScanningConfiguration`. The registry had no scanning rules before this change.
- [x] **AC7 It still works.** After `cdk deploy`, one AgentCore run end to end archives to S3, reads RODA open data and LGND, and is judged. The new image is scanned with no CRITICAL findings, or any found are listed in the handoff. `cdk diff` before the deploy shows no stateful resource replaced: the archive bucket and the secret are updated in place.

## Non-goals
- Changing VPC network mode, AgentCore Identity for LGND, Bedrock invocation logging, Object Lock or the budget (items 7–10 of the review).
- Changing the CDK bootstrap stack.
- Pinning the base image by digest. No AWS source requires it, and ECR immutable tags are already on.

## Assumptions and open questions
- **One-way door:** once S3 versioning is enabled, it can only be suspended, never removed. *Default:* ask the user to confirm before the deploy.
- **Assumption:** ECR basic scanning has no charge beyond storage. The [ECR pricing](https://aws.amazon.com/ecr/pricing/) page says "You pay only for the amount of data you store … and for data transfer", and doesn't list scanning.
- **Assumption:** RODA's public open-data buckets are owned by other accounts, so AC3 doesn't block them. AC7 proves this live. If it fails, revert only the AC3 statement.
- **Assumption:** nothing in the container needs root. The `uv` cache and the pre-warmed `uvx` tool cache move under the app user's home. AC7 proves the image boots on AgentCore.
- **Registry scanning is account-wide:** owning it in this stack means deleting the stack resets it. That's acceptable in a per-team sandbox.

## Plan
1. **The role (AC1–AC3):**
   - replace the trust principal with a conditioned one;
   - replace the logs, X-Ray and metrics statement with the documented ones;
   - condition the open-data statement.
2. **The buckets (AC4):** add the logs bucket, plus `versioned`, `server_access_logs_bucket` and `lifecycle_rules` on the archive.
3. **Retention (AC5):** a `LogRetention` on `f"/aws/bedrock-agentcore/runtimes/{runtime.attr_agent_runtime_id}-DEFAULT"`.
4. **The container (AC6):**
   - `Dockerfile`: a `useradd` for uid 10001, `chown /app`, `HOME` and the uv cache set under it, `USER app`, and the ADOT pin;
   - the ECR registry scanning configuration.
5. **Tests:** a synth test (`tests/test_infra.py`) asserting AC1–AC6 on the template; a local podman build checking `id -u` ≠ 0 and that the agent imports.
6. **Verify:**
   - `cdk diff`;
   - ask the user to confirm the versioning door;
   - `cdk deploy`;
   - simulator checks (AC2, AC3);
   - `get-bucket-*`;
   - a log retention check;
   - one AgentCore run;
   - the ECR scan findings.
