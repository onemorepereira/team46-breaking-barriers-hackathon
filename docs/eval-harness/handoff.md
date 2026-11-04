# Track 1 Evaluation Harness — Handoff

**What shipped:** A Track 1 evaluation harness on branch `design/eval-harness`:
- A Strands agent on Bedrock AgentCore Runtime, using RODA and LGND Geo MCP tools and Claude Sonnet 5.5 or Kimi K3.
- Every model and tool decision is recorded as OpenTelemetry `harness.*` spans and archived as JSONL in S3.
- A local `harness` CLI runs agents and suites, then checks, grades, summarizes, reports, replays and compares runs from the archive alone.
- Infrastructure is CDK (`infra/app.py`), and CI runs ruff, mypy, pytest and gitleaks.

**Verification** (Verify run, 2026-11-04; suite `uv run pytest` gave 63 passed, then 66 after the Unicode fix below; ruff and mypy clean):
- [x] **AC1 Run.** `harness run --prompt prompts/tasks/dallas-dc-strict.md --model sonnet --backend agentcore` exited 0: run `65ab6003-3663-4db4-a2ca-a9ff96d4a20a`, 8 steps, 0 errors. Earlier live runs: `954835ff`, `77151a3e`, `572c67cc`, and suites `dallas-dc-v1-20261104T0359`, `…T0414` and `…T0423`.
- [x] **AC2 Decisions traced.** `tests/test_check.py` (16 passed, using synthetic archives). `harness check 65ab6003…` on the live S3 archive reported 0 missing fields. Every deployed run so far reports 0 missing fields.
- [x] **AC3 OpenTelemetry only.** `tests/test_import_lint.py` (3 passed): a static AST scan plus the reviewed dependency allowlist.
- [x] **AC4 Exporter swap.** `tests/test_exporter_swap.py` (1 passed): two subprocesses through the real `telemetry.py`, one exporting OTLP to an in-process receiver and one to the console. Only the model and tool are scripted. Live: trace `6aeab6e0764434343c0035fe0e452158` showed 47 spans in CloudWatch `aws/spans` (Logs Insights).
- [x] **AC5 Archive.** `tests/test_archive.py` (3 passed; S3 faked with moto). Live: `aws s3 ls …/runs/65ab6003…/` lists `run.json`, `result.json`, `summary.json`, `spans-0001`/`0002.jsonl`, and `tool_results/T1–T5.a0.txt`. Spike S2 showed 100% of decision spans archived (18 of 18).
- [x] **AC6 Claim provenance.** `tests/test_provenance.py` (27 passed after the Unicode fix): matched, mismatch, unsourced, a missing block, retries, the 16 KB+ result, JSON escapes, Unicode, and adversarial injection.
- [x] **AC7 Summary.** `tests/test_report_cli.py -k "trouble or narrative"` (2 passed): every trouble spot is named, and invented span IDs are dropped. Live narratives are in `summary.json` (Sonnet 5.5).
- [x] **AC8 Report.** `tests/test_report_cli.py -k "report or rubric"` (8 passed, including escaping `<script>`). The live `out/65ab6003…/report.html` contains every required section.
- [x] **AC9 Replay.** `tests/test_report_cli.py -k replay` (passes offline, with networking blocked and the current prices ignored). `harness replay 65ab6003…` twice gave reports that differ only in the timestamp line. Replay also re-graded run `2e15c1bf` after a grader fix: 4/1 became 5/0.
- [x] **AC10 Model swap.** `harness.yaml` defines `sonnet` (`us.anthropic.claude-sonnet-5-5`) and `kimi` (`us.moonshotai.kimi-k3`). Suite `…T0423` has runs for both model IDs, with no code change between them.
- [x] **AC11 Suite and compare.** `tests/test_agent_local.py -k suite` (2 passed). `harness compare dallas-dc-v1-20261104T0423` gave 4 rows.

**Edge cases (Verify run):**
- **Pass:**
  - Replaying an unknown run ID.
  - Checking an archive with a deleted tool-result file.
  - An unknown model key in a suite.
  - A suite over the run cap.
  - A run with no prices configured (refused before any model call).
  - Running replay twice (idempotent).
- **Fail, then fixed:**
  - **Unicode:** `São Paulo` against a JSON `São Paulo` result, and composed (NFC) against decomposed (NFD) text, both graded mismatch. Matching now decodes `\uXXXX` escapes, normalizes text to NFC and casefolds it; regression tests were added.
- **Known limits, kept as they are:**
  - A value with a unit symbol, like `32.8°`, is classed as text.
  - The `out/index.json` run lookup takes precedence over a different `--config archive_uri`. That's by design (the index records where each run was archived), but it's surprising when you point a temporary config at a copied archive. Use a separate `out_dir` for that.

**Exercised live:** sandbox account 892605951158, us-west-2.
- CDK stack `Team46EvalHarness`: AgentCore runtime `team46_eval_harness-VzYWReDy9h` and archive `s3://team46evalharness-archiveda4cb258-qgbj570ey9mw`.
- More than ten Dallas runs on AgentCore, plus four suites.
- LGND Geo used live: NAIP `search_place_find` within 50 km of Dallas, and `reasoning_imagery_check`.
- CloudWatch Transaction Search enabled (approved by the user).

**Gate history:**
- **Define:** self-review; fixed AC7's untestable "struggled".
- **Design:** 5 subagent passes. The blocking issues per pass went 18, 7, 5, 4, 2. Passes 4 and 5 were approved by the user beyond the 3-pass limit. The user dropped Phoenix and the live swap demo after pass 3.
- **Plan:** self-review, no blocking issues.
- **Verify:** this record, then the subagent gate review.

**Specialists consulted:** ML/AI, AI Safety, QA Automation, Infrastructure, DevOps, SRE, FinOps and Data Engineer. Their questions were part of every design review pass.

**Decisions and deviations:** every one is recorded in `design.md` or `spikes.md`.
- **Corrections from reality during Build:**
  - Strands reads the global tracer provider.
  - The default conversation manager trims history, so `NullConversationManager` is used.
  - `MCPAgentTool.timeout` is the per-call MCP timeout.
  - Strands wraps hook exceptions in `EventLoopException`.
  - A model call blocked by a limit is not recorded.
- **Grader fixes found by live runs or Verify:**
  - JSON `\n` escapes read as line breaks.
  - Unicode `\uXXXX` escapes and NFC normalization.
  - Cached prompt tokens now count as input. Kimi K3 caches automatically, which made the input cap and cost undercount.
- **"Datasets accessed"** counts only datasets opened by ID, not search hits.
- **LGND login:** the device flow was denied by LGND, so login uses the browser flow (authorization code + PKCE). Cloudflare requires a named User-Agent (error 1010).
- **Prompt:** one verbatim value per claim. Compound values were correctly graded mismatch, and with the new rule a suite went from 0/6 to 21/21 matched.
- **User decisions:**
  - Drop Phoenix.
  - Drop Haiku.
  - Add Kimi K3.
  - Use real Sonnet prices ($2 / $10) and Kimi prices from the AWS Price List API ($3.30 / $16.50).

**Follow-ups:**
- **S2 not tested:** a 13-minute synchronous call (the documented fallback is AgentCore background tasks), and a 16 KB attribute in CloudWatch.
- **S6 not done:** the OSM answer-key count, because both Overpass mirrors were unavailable.
- **Open in the spec:** the final prompts. The rubric, scorer and workflow-scoring method shipped on 2026-11-04 in [docs/judging](../judging/handoff.md).
- **Known limits:** matching uses only the claim's value, coordinate parts match independently, and a value with a unit is classed as text.
- **The Sonnet price** comes from the global cross-region table; the `us.` profile may differ slightly.

**Risks to watch:**
- LGND's refresh token: if it expires or is revoked, the agent records LGND as unavailable and continues with RODA. Re-run `harness lgnd-login`.
- Kimi K3 runs take 2–7 minutes. Watch the 10-minute wall clock on larger prompts.
- Transaction Search is account-wide. To undo it after the event: `aws xray update-trace-segment-destination --destination XRay`, then `aws logs delete-resource-policy --policy-name Team46TransactionSearchXRayAccess`.
