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

RODA catalog tools and **LGND imagery tools are connected in the active workshop copy**. The LGND OAuth login is stored in this same event account, in the dedicated `team46-adi-lgnd` secret. It was not copied from Miguel. New copies must complete their own login before imagery tools work. The login helper enables geographic boundary enforcement.

On November 4, actual inference probes succeeded for Sonnet 5.5, Opus 5.5, Kimi K3, Kimi K2.5, Mistral Large 3, DeepSeek V3.2 and Qwen3 235B in this event account. Model availability may change. A real Sonnet dataset-discovery run finished with eight steps, zero tool errors, and three valid judges (Mistral, DeepSeek and Kimi). Detailed run records stay out of Git.

`harness.local.yaml`, credentials, archives and logs are private/ignored. Model calls consume the event budget. Source checks and replay do not prove real-world dataset accuracy.

The optional `--workshop-proxy` adapts application links for code-server’s existing authenticated `/proxy/8787/` route. The server still binds only to localhost. Omit the flag when accessing the app directly on localhost.

## Verified browser run

On November 4, run `230a6437-3e8f-46c8-953a-88d909679989` completed through the workshop browser's **Run & judge** button with real Sonnet/RODA and three valid judges. Six declared values matched their cited source text. The panel marked relevance/completeness lower because Kenya coverage was not confirmed; this is a source-checking result, not a validated dataset answer. Another advanced-spatial run recorded a transient Bedrock ServiceUnavailable error. Retry failed runs; do not treat their scores as successful task completion.

Open `https://d37rt8nwcs1lq3.cloudfront.net/proxy/8787/` while the workshop and server are active. **Runs** opens the saved reports. The event login is required. The app is hosted on the supplied workshop machine, with inference in Bedrock, rather than a new AgentCore Runtime deployment.

## Optional LGND connection

Miguel's integration is included, but his private OAuth login is not copied. LGND is needed for the imagery/site-search example cards, not for the catalog-only Bedrock smoke test. The user completed the separate LGND login on November 4, and the active copy uses `team46-adi-lgnd` in the event account. A live MCP connection listed all 18 tools.

If the team supplies a whitelisted LGND login, run `uv run python -m scripts.adi_lgnd_login` in this copy, open the displayed authenticated workshop link and sign in. The helper uses PKCE, stores the renewable login in that event secret without printing it, updates only ignored `harness.local.yaml`, and enables boundary enforcement. Restart the UI afterwards and verify a real imagery call before claiming the connection is working. The login helper closes after 15 minutes.

## Verified LGND imagery run

Run `a6d3001c-5768-446c-9f33-c93b2e866c6c` completed via the browser with real Sonnet, `search_place_find` and `reasoning_imagery_check`, followed by three valid judges (Mistral, DeepSeek and Kimi). One NAIP search returned five candidates within the enforced Napa County boundary; the answer reported three locations. Both tool calls succeeded with zero errors. Eight declared values matched their cited sources, and all three reported locations were inside the saved county geometry. The agent runtime was 36 seconds; the app estimated $0.15 for the agent and $0.06 for judging, not an AWS billing statement.

The panel score was 100 under the current starting rubric. This is not independent ground truth: the answer explicitly warns that row patterns cannot establish vineyard identity versus other row crops. Clay can change the rubric and review the evidence; see [Clay: change the rubric](clay-rubric.md).

Reproduce the small task with `uv run python -m scripts.adi_sandbox run --prompt prompts/tasks/adi-napa-smoke.md --model sonnet`, or paste the task into the console. It uses public NAIP imagery through LGND. The report and raw traces stay in the ignored workshop archive.

## Constraint test and model availability

Sonnet run `457f0fed-31d3-46bf-a36c-691754379770` encountered Bedrock ServiceUnavailable before any model call succeeded. It was recorded as **not scored**, with its partial trace preserved.

The same protected-area/ZIP request then completed with Kimi in run `d0bfb674-ac6c-4058-bfc8-fa92bccfd224`: seven successful tool calls, zero errors, 40 seconds of agent runtime, and three valid judges (Opus, DeepSeek and Mistral; Kimi recused). The first panel result was 75 overall / 50 output / Medium confidence. The protected-natural-area designation had no adequate located evidence, so distance compliance remained unverified and capped the output score. This demonstrates the missing-evidence protection, not independent facility verification.

This live run also revealed a false-negative source-check bug for LGND's per-place answer tables. Matcher version 3 fixes it; see [the value-matching handoff](value-matching/handoff.md#live-lgnd-follow-up-matcher-version-3). Earlier judgements remain archived when reports are refreshed. The active sandbox now uses Kimi for area/condition extraction and summaries; the console still offers Sonnet and Kimi as worker models. Bedrock availability errors can still happen.

Remaining validation for Clay: choose its desired rubric, review examples against independent reference data, and test planted-defect calibration/human agreement. None of those is implied by successful cloud execution.

After the version-3 parser fix, both live runs were re-judged from the existing traces and their summaries regenerated. Napa remained 100/High with 8/8 source values matched. ZIP 75082 became 68.8/Medium with 14/14 source values matched and output still capped at 50 for unverified protected-area proximity. This is a new judgement, not a rerun of the agent. All three judges were valid on both refreshed reports. The earlier judgements and pre-fix summaries were preserved.

The constraint task is available in `prompts/tasks/adi-zip-spatial-smoke.md`; use `--model kimi` with the event template's Kimi narrative setting to reproduce the tested configuration.
