# Developer Guide

How to set up, run, extend and debug the Team Foundry eval harness. For the project's purpose and the decisions behind it, read the [README](../README.md). For contribution rules, see [CONTRIBUTING](../CONTRIBUTING.md). Every other doc is listed in the [docs index](README.md).

## 1. Prerequisites

| Need | For | Notes |
| --- | --- | --- |
| [`uv`](https://docs.astral.sh/uv/) | everything | It installs Python 3.12 and every dependency (`uv sync`). CI pins uv 0.13.6 |
| Nothing else | the test suite, `replay`, `check`, `compare` on local archives, the console over recorded runs | The suite is fully offline |
| AWS credentials for the sandbox account (`us-west-2`) | agent runs, judging, S3 archives | Bedrock model access: Sonnet 5.5, Kimi K3 and the judge models in `harness.yaml` |
| An LGND Geo login | LGND imagery tools | One time: `uv run harness lgnd-login` saves the login to Secrets Manager. Teams are whitelisted for the event |
| Node.js and podman (or Docker) | deploying the AgentCore stack | `cd infra && CDK_DOCKER=podman npx aws-cdk deploy` |

## 2. First run

```sh
uv sync                     # create .venv with Python 3.12
uv run pytest               # the whole suite, offline
uv run harness --help       # the CLI
uv run harness ui           # the console at http://127.0.0.1:8787, over whatever is already archived
```

Then, with AWS credentials in your shell:

```sh
uv run harness run --prompt prompts/tasks/dallas-dc.md --model sonnet --backend local
```

This runs the agent as a local subprocess, archives every span to `archive/runs/<run-id>/`, judges the run (`judging.auto`) and writes `out/<run-id>/report.html`. It also archives the run's result tiles (`tiles.archive`). The console does the same from its prompt box, live.

**Credentials.** The harness uses the standard AWS credential chain (boto3): environment variables, a profile, or SSO. The hackathon sandbox hands out **temporary session credentials that expire after a few hours**. When they do, Bedrock calls fail with `ExpiredTokenException`. Keep them in a file **outside the repo**, `source` it in the shell that runs the harness or the console, and restart the console after refreshing them. A run whose model calls all fail is recorded as **not scored**, not FAILED.

## 3. Architecture in one screen

```
harness (CLI or console) ── plans a run ──▶ agent (local subprocess, or AgentCore Runtime)
   │                                          ├─ Strands agent ─▶ Bedrock model
   │                                          ├─ tools/: RODA MCP (stdio) · LGND Geo MCP (HTTP + OAuth)
   │                                          └─ hooks ─▶ OpenTelemetry harness.* spans ─▶ archive (file:// or s3://)
   └─ reads the archive only ──▶ analysis/ (check, provenance, signals, timeline, judging/measure+dossier)
                              ├─ harness/judge.py ─▶ judge tribunal on Bedrock ─▶ runs/<id>/judgement.json
                              ├─ report (out/<id>/report.html) · runs-table row (out/<id>/row.json)
                              └─ console (harness/web): FastAPI + Tabler + MapLibre, SSE live stream, tile cache
```

The layers (`core` → `tools` → `agent`; `analysis`; `harness`) and their import rules are in the [README code layout](../README.md#code-layout), enforced by `tests/test_layers.py`. The scoring method is in the [judging guide](judging/guide.md).

## 4. Where things are written

**Archive** (`archive_uri` or `local_archive_uri`), one folder per run, `runs/<run-id>/`:

| File | Written by | Holds |
| --- | --- | --- |
| `run.json` | harness, at start | the manifest: model, prompt and its hash, backend, area, config snapshot (prices, limits) |
| `spans-NNNN.jsonl` | agent, as spans end | every OpenTelemetry span, one JSON object per line |
| `tool_results/T<n>.a<attempt>.txt` | agent | the full, raw result of each tool call |
| `result.json` | agent, at end | status, final answer, tool refs |
| `summary.json` | harness (`narrative_model`) | the plain-English narrative |
| `judgement.json` | `harness judge` / auto-judge | every judge's votes, rationales, refs, costs, and the aggregate; or `not_scored` |
| `calibration.json` | `harness calibrate` | planted-defect results |
| `tiles/<index>/<key>.jpg` | report time | the imagery under each result ([tile cache](tile-cache/design.md)) |

**Local output** (`out_dir`, default `out/`, not committed):

| Path | Holds |
| --- | --- |
| `index.json` | run ID → archive URI, suite ID → archive URI |
| `<run-id>/report.html` | the static report |
| `<run-id>/row.json` | the console's runs-table row (`harness/rows.py`) |
| `<run-id>/live.jsonl`, `rejudge.jsonl` | the console's live span stream |
| `<suite-id>/compare.html`, `compare.csv` | `harness compare` |
| `tile-cache/` | cached basemap and result tiles |
| `geo-cache/` | resolved area boundaries (OpenStreetMap, US Census) |
| `ui/` | prompts typed into the console |

## 5. Configuration reference (`harness.yaml`)

Committed, and it holds no secrets. Unset keys take the defaults in `harness/config.py`. Run `--config <path>` to use another file; a `<name>.local.yaml` next to it is merged on top in the same way.

**Your own sandbox:** put account-specific values (`archive_uri`, `lgnd_secret_id`, `runtime_arn`, from your stack's CDK outputs) in `harness.local.yaml` next to `harness.yaml`. It's git-ignored, and it's merged on top key by key, nested blocks included. It can override any value but not remove a key: to drop a judge, for example, set the whole `judging.panel` list. The committed file never needs your changes. See [your own AWS sandbox](factory.md#your-own-aws-sandbox).

| Key | Default | Meaning |
| --- | --- | --- |
| `region` | `us-west-2` | AWS region for Bedrock, S3, Secrets Manager and AgentCore |
| `backend` | `agentcore` (repo file: `local`) | Where `harness run` runs the agent; `--backend` overrides |
| `archive_uri` | `file://./archive` (repo file: the S3 bucket) | Archive for AgentCore runs (`s3://…` or `file://…`) |
| `local_archive_uri` | `file://./archive` | Archive for local runs |
| `local_exporter` | `console` | Span exporter for local runs (OpenTelemetry; swappable by config) |
| `lgnd_secret_id` | none | Secrets Manager ARN holding the LGND Geo login (CDK output `LgndSecretArn`) |
| `runtime_arn` | none | AgentCore runtime (CDK output `RuntimeArn`) |
| `out_dir` | `out` | Local output (see §4) |
| `models.<key>` | none | One entry per model: `id` (Bedrock model or inference-profile ID), `family` (drives judge recusal), `agent` (`false` for judge-only models), `max_tokens`, `request_fields` (passed to Converse, e.g. Claude thinking) |
| `judging.rubric` | none | Rubric YAML, e.g. `rubrics/geo-dataset-v1.yaml` |
| `judging.panel` | none (required to judge) | Seated judges, by model key: an odd number, one per family |
| `judging.reserves` | `[]` | In order: sit for a judge that recuses, or stand in for one that fails |
| `judging.recuse_same_family` | `true` | A judge sharing the agent's family steps down |
| `judging.passes` | `1` | Panel passes per run; `--passes` overrides |
| `judging.auto` | off | Judge every finished run (`harness run`, the console) |
| `tiles.archive` | `false` (repo file: `true`) | Archive result tiles when a report is written |
| `tiles.serve` | `true` | The console serves imagery through its cache; `false` sends the browser straight to the providers |
| `tiles.cache_max_mb` | `1024` | Disk cache cap (least recently used are evicted) |
| `tiles.max_age_days` | `30` | Refetch a cached tile after this long |
| `area_mode` | `enforce` | How the prompt's area applies to LGND searches: `enforce` (searches kept inside), `observe` (recorded only) or `off` |
| `narrative_model` | none | Model key that writes each run's summary, and reads the area from the prompt |
| `max_runs_per_suite` | `8` | A suite with more runs is refused |
| `max_suite_usd` | `50` | A suite whose worst-case cost is higher is refused |
| `prices_per_mtok.<key>` | none | `{in, out}` USD per million tokens, for cost estimates. Each price is sourced in a comment |

Per-run limits (40 steps, 400k input and 200k output tokens, 600 s wall clock, 60 s per tool call) are `DEFAULT_LIMITS` in `harness/invoke.py`, and are recorded in each run's manifest.

**Environment variables** (set by the harness for the agent process; set them yourself only to override):

| Variable | Meaning |
| --- | --- |
| `HARNESS_ARCHIVE_URI` | Where the agent archives spans |
| `HARNESS_EXPORTER`, `HARNESS_CONSOLE_PATH` | The span exporter, and the file the console tails |
| `HARNESS_LGND_URL`, `HARNESS_LGND_SECRET_ID` | LGND Geo endpoint and login secret |
| `HARNESS_PROMPTS_DIR` | Where `core.prompts` loads prompts from (default `prompts/`) |
| `HARNESS_GENERATED_AT` | A fixed report timestamp, for byte-identical replays |
| `HARNESS_TEST_SCRIPT` | Tests only: drive a scripted agent instead of a model |

## 6. CLI reference

`uv run harness [--config PATH] <command>`:

| Command | Does |
| --- | --- |
| `run --prompt FILE [--model KEY] [--backend agentcore\|local]` | Run the agent on a task prompt, then archive, judge and report it |
| `run --suite FILE` | Every prompt × model in a suite (e.g. `suites/dallas-dc-v1.yaml`), within the suite caps |
| `ui [--port 8787]` | The console: run, watch, score, map. Binds to 127.0.0.1. The API reference is at `/api/docs` |
| `judge RUN_ID [--passes N]` | Score an archived run with the judge tribunal |
| `calibrate RUN_ID [--passes N]` | Plant known defects in the run's dossier, and check that the panel lowers the right criterion |
| `agreement [RUN_ID …] [--suite ID] [--all]` | Krippendorff's α between judges across judged runs |
| `check RUN_ID` | Trace checker: is every decision field recorded? |
| `replay RUN_ID` | Rebuild the report (and the runs row and archived tiles) from the archive alone |
| `compare SUITE_ID` | Side-by-side table for a suite (`compare.html`, `compare.csv`) |
| `lgnd-login [--secret ARN] [--device]` | One-time OAuth login to LGND Geo, saved to Secrets Manager |

## 7. Recipes

**Add a task prompt or a suite.**
1. Write the prompt as Markdown in `prompts/tasks/`. Name the place plainly ("in Sylhet Division, Bangladesh"): the area is read from the prompt and resolved to an official boundary.
2. Add a suite file in `suites/` listing prompts × models.
3. To offer it in the console, add a card to `harness/web/static/examples.json`, and check that its area resolves (`harness.area.area_for_prompt`).

**Swap the rubric.** Write it in the shape of `rubrics/geo-dataset-v1.yaml`: criteria with anchors for 0, 1 and 2, dimensions, failure modes, gates, and a `calibration:` map. Point `judging.rubric` at it. No code changes; only the two measured criteria are named in code. Then run `harness calibrate` on a known-good run.

**Change the judges.** Edit `judging.panel` and `judging.reserves` in `harness.yaml`. Keep the panel odd and one judge per `family`. Add the model under `models` with `agent: false`, and give it a sourced price. See the [judging guide](judging/guide.md) for recusal and stand-ins.

**Add an MCP tool server.**
1. Create `tools/<name>/` with:
   - `descriptors.py`: a `SERVER` ID, tool names, which tools read an area, and how dataset IDs appear in arguments;
   - `client.py`: `make_client()`, returning a Strands `MCPClient`;
   - `describe.py`: a plain-English sentence per call;
   - optionally `results.py`, for parsing.
2. Register the client in `tools/registry.py:build`, and the describer in `tools/describe.py` (`_BY_SERVER`, `SERVER_LABELS`).
3. If `analysis/` needs the new descriptors or describers, allow them in `tests/test_layers.py`.
4. Agent-side changes reach AgentCore only after a redeploy.

**Change what the agent is told.** Edit `prompts/agent/*.md`. Never inline prompt text in Python (tests enforce this). Redeploy for AgentCore.

## 8. Using the console
`uv run harness ui` opens http://127.0.0.1:8787. It's dark only.
- **Run:** type a prompt or click an example card, pick the agent model, then **Run & judge**. Steps stream in plain English, then each judge's verdict.
- **The map:** results are outlined cyan inside the requested area and orange outside. Click a result, or a tile in the strip under the map, to open its details in the panel docked inside the map (Esc or × closes it). The mouse wheel scrolls the page; zoom the map with Ctrl or ⌘ plus the wheel, a pinch, or its + and − buttons.
- **Step links** (`T3`, "from T5"): these scroll the "What the agent did" list to that step without moving the page. If the list is off screen, a small "Show" prompt offers the jump.
- **Judge again:** on any finished run, re-scores it from its archived trace. It doesn't re-run the agent.
- **Runs:** every archived run, newest first, 50 at a time.
- **API:** the reference at `/api/docs`. It needs internet access (it loads Scalar from jsDelivr); `/openapi.json` always works offline.

## 9. Testing

- `uv run pytest` runs everything offline. `pytest-socket` blocks the network in the tests that must not reach it.
- **Building runs:** `tests/fixtures/builder.py` (`RunBuilder`, `standard_run`) writes a realistic archived run, so analysis, judging, report and console tests work from real files.
- **Faking judges:** `tests/test_judging.py:FakeBedrock`.
- **Faking tile providers:** `tests/test_tiles.py`.
- **Real end-to-end subprocess runs:** `HARNESS_TEST_SCRIPT` drives the agent with `tools/scripted.py`.
- **Live checks** (real Bedrock, LGND, S3) aren't in CI. Each feature's `handoff.md` records the live runs that proved it.
- **CI** runs ruff (lint and format), mypy, pytest and gitleaks; see [CONTRIBUTING](../CONTRIBUTING.md#before-you-push).

## 10. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Run **not scored**, `ExpiredTokenException` | Sandbox session credentials expired | Refresh the credentials, `source` them, restart the console, run again |
| `LGND Geo unavailable` in the run, only RODA tools listed | No LGND login, or the secret couldn't be read | `uv run harness lgnd-login`; check `lgnd_secret_id` and the credentials |
| Run ends `limit_exceeded` ("step limit 40 reached") | The agent looped without answering. Check the area first: the area line on the run page, and `harness.tool.area_requested` on its tool spans | Make the place unambiguous in the prompt. A wrong area makes every search return nothing |
| "Couldn't resolve the prompt's area … no official boundary" | The place has no administrative boundary (e.g. "Northern California") | Intended: the run goes ahead without an area check. Name a county, state or city to get one |
| A judge shows "failed" | Throttling, model access or a bad reply (retried once) | A reserve stands in. If the reserves run out the run isn't scored; re-judge from the run page |
| Blank map tiles | Provider down and the tile was never cached | Switch basemaps; `harness replay <id>` archives an archived run's result tiles. See the [tile-cache runbook](tile-cache/launch.md) |
| `/api/docs` is blank | No internet: the API reference loads Scalar from jsDelivr | Use `/openapi.json` (always local), or reconnect |
| LGND calls fail mid-run with an auth error | The stored LGND login has no valid refresh token. Tokens themselves refresh automatically every ~4 minutes | `uv run harness lgnd-login` into your own secret (see [your own AWS sandbox](factory.md#your-own-aws-sandbox)) |
| Console shows old behavior after a code change | The console process predates the change | Restart `harness ui` |
| `ruff format --check` fails in CI | Unformatted file | `uv run ruff format .` |
