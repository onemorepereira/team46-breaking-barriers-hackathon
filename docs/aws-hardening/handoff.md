# AWS Hardening: Handoff

**What shipped:** the deployed stack now follows AWS's documented AgentCore and S3 practice in all six places the 2026-11-04 review found:
- the trust policy is conditioned;
- logs and metrics are scoped as in AWS's documented execution role;
- open-data reads are limited to other accounts' buckets;
- the archive is versioned and access-logged;
- runtime logs expire after 30 days;
- the container runs as non-root, with pinned tracing and scan-on-push.

It's deployed to the sandbox (account 892605951158, us-west-2) and verified live.

**Verification**
- [x] **AC1: trust policy.**
  - Test: `test_trust_policy_has_confused_deputy_conditions`.
  - Deployed: `get-role` shows `StringEquals aws:SourceAccount = 892605951158` and `ArnLike aws:SourceArn = arn:aws:bedrock-agentcore:us-west-2:892605951158:*`.
  - AgentCore still assumes the role: the live run below.
- [x] **AC2: logs and metrics scoped.**
  - Test: `test_no_logs_action_on_star_and_metrics_are_namespaced`.
  - Deployed: the policy statements match AWS's documented execution role exactly.
  - Simulator: `PutLogEvents` on `/aws/lambda/anything` is denied.
  - **Live:** after the deploy, the runtime log group received 71 new events during the run, with no access-denied messages.
  - The IAM simulator also returned `implicitDeny` for the runtime's own stream (`…-DEFAULT:log-stream:x`), and even for a one-statement custom policy with this exact pattern. It returned `allowed` for `…:log-stream:` (no stream name). That's a simulator quirk, since the real writes succeed. So AC2's "allows the runtime's own" is proven by the live run, not by the simulator.
- [x] **AC3: S3 reads limited to other accounts' buckets.**
  - Test: `test_open_data_reads_exclude_this_accounts_buckets`.
  - Simulator, with `aws:ResourceAccount`:
    - `cdk-hnb659fds-assets-…/x` (own account) is **denied**;
    - `hackathon-cloudtrail-logs-…/x` (own account) is **denied**;
    - archive `runs/x` is **allowed**;
    - a bucket owned by another account is **allowed**.
  - **Live:** run `55d2dbd3` made three RODA calls (`search_datasets`, then `preview_dataset` twice), and all succeeded.
- [x] **AC4: archive protected.**
  - Test: `test_archive_is_versioned_logged_and_never_expires_current_objects`.
  - Deployed:
    - versioning is `Enabled`;
    - logging goes to `team46evalharness-archiveaccesslogseb0a12a9-…` under `archive/`;
    - lifecycle: noncurrent versions expire after 90 days, incomplete uploads are aborted after 7 days, and current objects have no expiration.
  - The archive kept its logical ID (`ArchiveDA4CB258`): updated in place, not replaced.
- [x] **AC5: log retention.**
  - Test: `test_runtime_logs_expire_after_30_days`.
  - Deployed: `/aws/bedrock-agentcore/runtimes/team46_eval_harness-VzYWReDy9h-DEFAULT` has a retention of `30`.
- [x] **AC6: container.**
  - Tests: `test_container_runs_as_non_root_with_pinned_tracing`, `test_images_are_scanned_on_push`.
  - Local podman build:
    - `id` is `uid=10001(app)`;
    - the PID-1 `Uid` is 10001;
    - `aws-opentelemetry-distro` is 0.22.0;
    - `/app` and `/tmp` are writable;
    - `/ping` is `Healthy`.
  - Deployed: the registry rule is `SCAN_ON_PUSH` for `cdk-*-container-assets-*`.
- [x] **AC7: it still works.**
  - `cdk diff` showed no replacement: the archive, role, policy and runtime were all modified in place, and the secret wasn't touched.
  - `cdk deploy` succeeded with unchanged outputs.
  - Live AgentCore run `55d2dbd3-e31c-4d11-a68e-fc52cd2be2a3`: 7 steps, 0 errors, 3/3 claims matched, archived to S3, judged at 77.5.
  - The image scan found **0 critical, 3 high, 9 medium and 3 low**. The highs are all base-image OS packages: zlib CVE-2026-85091, and glibc CVE-2026-5435 and CVE-2026-19499. Debian 13 (trixie) had no upgraded packages on 2026-11-04 (`apt list --upgradable` was empty), so there was nothing to apply.

The suite is 7 new infrastructure tests plus the full suite, all green, with ruff and the formatter clean. CI now also runs `uv run --group infra pytest tests/test_infra.py`.

**Exercised live:**
- `cdk diff` and `cdk deploy` (podman) to the sandbox;
- the IAM simulator;
- `get-bucket-versioning`, `get-bucket-logging` and `get-bucket-lifecycle-configuration`;
- `describe-log-groups`;
- `get-registry-scanning-configuration`;
- one AgentCore run through `harness run --backend agentcore`;
- an ECR image scan.

**Security scans:**
- gitleaks: no leaks (run before the commit).
- ECR basic scan of the deployed image: as above.

**Gate history:**
- **Define:** self-review. The ACs are testable and the one-way door (versioning) has a default.
- **The user confirmed the deploy,** versioning included.
- **Verify:** self-review against each AC, with live evidence.

**Specialists consulted:**
- **Infrastructure Engineer:** the reviewed `cdk diff`, with no stateful replacement; tags unchanged.
- **Application Security:** least privilege per AWS's documented role, and confused-deputy conditions.

**Decisions and deviations**
- **Access logs use a bucket policy.** CDK's default grants log delivery with the legacy `LogDeliveryWrite` ACL, which can't be combined with ACLs disabled (`BUCKET_OWNER_ENFORCED`). The feature flag `@aws-cdk/aws-s3:serverAccessLogsUseBucketPolicy` in `infra/cdk.json` grants `logging.s3.amazonaws.com` through a bucket policy instead, conditioned on the archive's ARN and the account.
- **`LogRetention` adds a small CDK-managed Lambda** and its role. Its policy has `logs:PutRetentionPolicy`/`DeleteRetentionPolicy` on `*`: that's CDK's own construct, not the agent role.
- **The registry scanning configuration is account-wide.** This stack now owns it (it had no rules before). Deleting the stack resets it.
- **`infra/app.py` gained a `build()` and a `__main__` guard,** so tests can synthesize it without deploying. `cdk.json` runs `python app.py`, so behavior is unchanged.

**Follow-ups**
- **This image push wasn't scanned.** CDK publishes assets before updating the stack, so it landed before the rule existed; it was scanned manually here. Every later push is scanned automatically.
- **Rebuild when Debian ships the zlib and glibc fixes.** The highs above clear then.
- **Still open from the review:** Bedrock invocation logging, AgentCore Identity for LGND, VPC network mode, Object Lock and the budget (`-c budget_email=…`).
- **Teammates' sandboxes** get the same hardening on their next `cdk deploy`. The versioning there is the same one-way door.

**Risks to watch**
- **A RODA dataset in a bucket this account owns** would now be denied. None exists today, and all of RODA's buckets belong to other accounts.
- **Versioning adds storage for overwritten objects.** It's capped at 90 days of noncurrent versions.
