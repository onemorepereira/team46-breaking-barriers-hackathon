# Track 1 against the briefs: what we cover, and what's missing

**As of:** 2026-11-04, branch `design/eval-harness`. References like (T114) or (V108) are line numbers in the [Technical](../Clay-Foundry-Technical-Hackathon.md) and [Vision](../Clay-Foundry-Vision-Hackathon.md) briefs. **[team]** marks our own assessment.

## MVP success criteria and Definition of Done

| Brief item | Status | Where |
| --- | --- | --- |
| An LLM harness performs the task by calling geospatial tools via MCP over public data (V108, V162) | **Done** | Strands on AgentCore, using RODA and LGND Geo MCP (`agent/`, `tools/`) |
| Traces captured and summarized into a human-readable view (V109, T114–T115) | **Done** | `harness.*` OpenTelemetry spans archived to S3. Plain-language timeline in the console (`analysis/timeline.py`). Narrative generated from the trace (`harness/narrative.py`) |
| Scored on two dimensions: workflow signals from the traces, and output quality against a rubric (V110, T116–T118, V163) | **Done** | Rubric `rubrics/geo-dataset-v1.yaml`: 4 workflow criteria and 6 output criteria, scored by measured checks plus a three-judge tribunal ([guide](guide.md)) |
| A per-run evaluation report (V112, T119) | **Done** | `out/<run>/report.html` (static), plus the console run page |
| Tracing tool and model swappable, behind an abstraction (V113, V164, T10) | **Done** | OpenTelemetry exporter-swap CI test (AC4). Models are config keys (`harness.yaml`). Judges are config keys too |
| Recorded traces replay through scoring (V114, V165, T121) | **Done** | `harness replay` re-grades and re-aggregates archived judgements without calling a model. The console renders archived runs offline (vendored assets) |
| Code in an open-source repo (V166), Apache-2.0 (V33) | **Done** | Public GitHub repo, with `LICENSE` added on 2026-11-04 |
| Trust and provenance first-class: every scored run keeps its traces, inputs and the rubric it was judged against (V34) | **Done** | `run.json` snapshots the prompt, prices and search area. `judgement.json` snapshots the rubric (with its sha256), seats, every vote and every rationale |

## Features in scope

| Feature (V118–V130) | Priority | Status |
| --- | --- | --- |
| LLM harness over MCP tools | Must | Done |
| Trace capture | Must | Done |
| Trace summarization | Must | Done: the narrative, plus a plain-language step for every span |
| Scoring against rubric/reference | Must | **Done against our generalized rubric**; ADB's rubric isn't available yet (see gaps) |
| Evaluation report | Must | Done |
| Swappable tracing tool + model | Must | Done |
| Recorded-trace replay | Must | Done |
| Minimal UI to launch a run and read the report | Should | **Done, beyond minimal**: the Team Foundry console on FastAPI (T99) |
| Second task, multi-agent traces | Exploratory | Not done |

## Technology table

| Brief row | Status |
| --- | --- |
| Python 3.12+ (T71) | Done |
| TypeScript / JavaScript thin UI (T72) | Done in plain JavaScript (no build step). The Tabler, MapLibre, marked and DOMPurify libraries are vendored |
| Agent framework kept swappable (T86) | Done: Strands; the harness only sees OpenTelemetry spans |
| MCP SDK + geospatial MCP servers (T87) | Done: RODA and LGND Geo. **Gap:** none from Clay's geoMCP shortlist (V189–V190), which we never received |
| Tracing tool, OpenTelemetry default (T88) | Done |
| boto3 (T90) | Done |
| FastAPI, the thin API behind the UI (T99) | **Done** (it was the stdlib `http.server` until 2026-11-04) |
| Geospatial stack: rasterio / GDAL / xarray / pystac (T89) | **Not used.** The agent reaches imagery through LGND Geo's MCP tools, and the harness only does point-in-polygon and simplification (`core/geometry.py`, stdlib). Adding pystac is worth it once a task reads STAC assets directly |
| scikit-learn / numpy for scoring metrics (T97) | **Not used.** Our metrics (medians, MAD, Krippendorff's α, bootstrap) are small and stdlib-only, and α is checked against Krippendorff's published example. numpy would only matter at corpus scale |
| SQL as a lightweight trace/metadata store (T77, T167) | Not used: a JSONL archive in S3, plus `out/index.json`. That's adequate at hackathon scale |

## Real gaps (what we'd do next)

1. **ADB's own rubric, task and input dataset (V191, T31).** These never arrived. Our rubric is a generalized stand-in for agentic geospatial dataset builds, and the code only names the measured criteria, so ADB's rubric drops in as a YAML file. **Owner:** Clay/ADB.
2. **[Started 2026-11-04: [ADB alignment](../adb-alignment/spec.md).** Reference sets and recall, precision and count ratio under the LGND/Ode benchmark's rule now exist, with a first set from USPVDB, Pecos County, TX. Sets for ADB places (Nagoya, Manila) need LGND's prepared data.] **A reference answer key for output correctness (V62: "known task + known input + a reference").** We score process and grounding, and we check claims against tool outputs, not against the world. The paper makes the same point: "process alignment rather than outcome correctness" (GRA §6). The cheapest strong fix:
   - switch to a target with an open answer key, such as solar farms checked against USGS USPVDB or Global Renewables Watch (V96, V194–V195);
   - add a measured **recall/precision vs answer key** criterion.

   Our Dallas data-center answer key (spike S6, from OSM) was blocked because both Overpass mirrors were down.
3. **Human expert calibration of the panel.** We measure judge-to-judge agreement and sensitivity to planted defects. We have not yet measured agreement with domain experts, which the paper did (α ≈ 0.57). **The machinery now exists** ([judge feedback](../judge-feedback/spec.md)): reviews in the console, `harness agreement --human`, and guidance evaluated against reviewers. What's missing is the reviews themselves, from ADB or Clay experts, which the team can't supply.
4. **Input dataset in the loop.** Track 1 lists "input dataset + harness(es) under test" (T31). Our agent discovers data through tools, and no fixed input dataset is handed to it. A dataset-conditioned prompt suite would match the brief more literally.
5. **Several harnesses under test (V70: "an agent (or set of agentic harnesses)").** We swap models inside one harness. Evaluating a second, different harness, for example a non-Strands agent emitting OpenTelemetry, would exercise the claim that the eval is harness-agnostic.
6. **Stretch goals not done:**
   - multi-agent traces;
   - dynamic MCP discovery across Clay's catalog (T187–T188);
   - a second task (T186).

   Sensitivity analysis (T190) is **partly** done: suites vary model and prompt, `harness compare` shows them side by side with corpus α, and `--passes` measures judge variance.
7. **Clay's existing evaluation harness (T23).** The trace and report formats haven't been aligned with Clay's own. That's an open question for Clay.
