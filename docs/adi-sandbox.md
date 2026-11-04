# Aditya's real Bedrock sandbox copy

This branch is based on Miguel's Team46 application plus `slice/complete-evaluations`. It is not yesterday's separate agent prototype.

Expected workshop account: **952337755619**, assumed role **WSParticipantRole**, region **us-west-2**. Use the supplied Kiro instance identity. No credentials are stored in Git. The example config clears Miguel's secret/runtime and uses local archives instead of his S3 bucket.

```sh
cp harness.adi.example.yaml harness.local.yaml
uv sync
uv run python -m scripts.adi_sandbox check
uv run python -m scripts.adi_sandbox ui --port 8787 --workshop-proxy
```

The launcher refuses personal profiles, wrong account/role/region, another account's runtime/secret, or non-local archives. It does not change IAM or deploy cloud infrastructure.

Run a real task with:

```sh
uv run python -m scripts.adi_sandbox run --prompt out/adi-live-task.md --model sonnet
```

The UI/agent/evaluator processes run on the workshop machine; actual model inference runs in AWS Bedrock. Reports and traces remain under the private working copy's `archive/` and `out/`. This is not a new public AgentCore deployment.

RODA catalog tools are enabled. **LGND imagery tools are not connected in this isolated copy yet.** Physical-site tasks must expose that missing evidence rather than claim verified results. Connecting LGND needs a login secret in this same event account; do not reuse Miguel's secret.

On November 4, actual inference probes succeeded for Sonnet 5.5, Opus 5.5, Kimi K3, Kimi K2.5, Mistral Large 3, DeepSeek V3.2 and Qwen3 235B in this event account. Model availability may change. A real Sonnet dataset-discovery run finished with eight steps, zero tool errors, and three valid judges (Mistral, DeepSeek and Kimi). Detailed run records stay out of Git.

`harness.local.yaml`, credentials, archives and logs are private/ignored. Model calls consume the event budget. Source checks and replay do not prove real-world dataset accuracy.

The optional `--workshop-proxy` adapts application links for code-server’s existing authenticated `/proxy/8787/` route. The server still binds only to localhost. Omit the flag when accessing the app directly on localhost.

## Verified browser run

On November 4, run `230a6437-3e8f-46c8-953a-88d909679989` completed through the workshop browser's **Run & judge** button with real Sonnet/RODA and three valid judges. Six declared values matched their cited source text. The panel marked relevance/completeness lower because Kenya coverage was not confirmed; this is a source-checking result, not a validated dataset answer. Another advanced-spatial run recorded a transient Bedrock ServiceUnavailable error. Retry failed runs; do not treat their scores as successful task completion.

Open `https://d37rt8nwcs1lq3.cloudfront.net/proxy/8787/` while the workshop and server are active. **Runs** opens the saved reports. The event login is required. The app is hosted on the supplied workshop machine, with inference in Bedrock, rather than a new AgentCore Runtime deployment.

## Optional LGND connection

Miguel's integration is included, but his private OAuth login is not copied. LGND is needed for the imagery/site-search example cards, not for the catalog-only Bedrock smoke test. A dedicated empty secret slot `team46-adi-lgnd` was prepared in this event account; login remains unfinished and imagery is not claimed working.

If the team supplies a whitelisted LGND login, run `uv run python -m scripts.adi_lgnd_login` in this copy, open the displayed authenticated workshop link and sign in. The helper uses PKCE, stores the renewable login in that event secret without printing it, updates only ignored `harness.local.yaml`, and enables boundary enforcement. Restart the UI afterwards and verify a real imagery call before claiming the connection is working. The login helper closes after 15 minutes.
