# Connected evidence workspace

Branch `integration/foundry-ui`, based on `main` at d5752e2. The supplied `AWS HACK 2.0.zip` was preserved unchanged. Its React/Figma visual language is retained; hardcoded Bangladesh results, scores, timers and prototype state buttons are removed. Figma-specific tooling, deployment metadata and third-party instruction files are not part of this app.

## Open or run

The new UI is at **`/workspace/` on the existing backend origin**. The classic console, API, guidance editor and reports remain available. No separate frontend host or CORS configuration is needed.

```sh
uv sync
uv run harness ui
# Open http://127.0.0.1:8787/workspace/
```

Built frontend assets are committed in `harness/web/static/workspace/`, so Python deployments do not need Node. To edit and rebuild (Node 22.12+ and pnpm 11):

```sh
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm --dir frontend test
pnpm --dir frontend build
```

For a read-only synthetic preview, `uv run python -m scripts.demo_evals`, then open `http://127.0.0.1:8789/workspace/?run=run-0001`. That preview intentionally has no real imagery and rejects writes. It is not a live AWS test. For Vite hot reload, run the backend at 8787 and `pnpm --dir frontend dev`; Vite proxies the API to localhost.

In Aditya's event workshop, keep the private `harness.local.yaml` outside Git and use `uv run python -m scripts.adi_sandbox ui --workshop-proxy`. The guard requires account 952337755619 / WSParticipantRole / us-west-2; it rejects personal profiles and other accounts. Never put AWS keys, LGND tokens, or client secrets in frontend environment variables, browser storage or Git. The UI only uses same-origin authenticated backend APIs. The workshop's existing sign-in protects its `/proxy/<port>/` path; these changes do not create a public deployment or change IAM permissions.

## What works

- Prompt and model selection from the backend's configured models; POST /api/runs starts real work.
- Live progress snapshots (every two seconds, using the same event records as SSE) show area resolution, actual completed steps and judge replies; no invented progress percentages or scores.
- Previous runs load from the real paginated archive; a `?run=<id>` URL opens one directly.
- MapLibre displays the saved boundary, tool-returned image footprints and deduplicated coordinate claims. Selecting a location links to its saved evidence step. Coordinates are not fabricated from place names.
- Final answer, imagery chips with recorded dates, complete source-value table, request-condition matrix, independent judge rationales, workflow/output scores, trace integrity and cost estimates come directly from the run view.
- The review form posts the reviewer's name, selected judged criterion, agreement or suggested rubric score with reason/refs to the existing feedback API. Missing/invalid inputs remain visible as errors. The review does not change the automated score by itself. A saved current review can be sent to the judges with **Ask judges to reconsider**; the original judgement remains archived. The existing Guidance editor remains available for approving lessons.
- Re-judge uses archived evidence with the configured judge panel; it makes paid model calls. JSON export and static HTML reports preserve detailed evidence.
- Mobile layout, keyboard submission, labelled controls, reduced motion and error/empty/not-scored states are included.

## LGND / ADB usability choices

The supplied **LGND GeoAI Evals Inception Report, Draft V1 (Oct 20), pages 2, 5–8** emphasizes per-asset evaluation, checkable references, analyst effort/cost, uncertainty, transferable workflows and presentation-safe sources/licences. Accordingly, the UI separates the panel score from reference metrics, exposes the archived reference/matching rule and licence blockers, and does not label a source-text match as ground truth. When no reference is tied, the page says recall, precision and transfer performance are not established. Existing backend ADB reference/license code is reused; this integration does not invent a full transfer benchmark, analyst-time measurement or scientific validation.

Satellite context uses the backend's Sentinel-2/EOX cached basemap with attribution. Street tiles are fetched directly from OpenStreetMap by the browser, preserving the existing policy of not proxy-caching OSM tiles. The UI's basemap is context, not the evidence used for the agent's decision. Licence restrictions still require review before presenting datasets to third parties.

## Validation boundaries

The short-request progress endpoint avoids buffering in authenticated workshop proxies; the original SSE endpoint remains available. Reading before the worker creates its trace file returns an empty event list rather than dropping the connection.

CI builds/typechecks the frontend, runs frontend contract tests, checks built assets are current, runs the Python tests and secret scan. Browser QA and event-cloud smoke results are recorded separately below. Passing these checks establishes software integration, not geospatial truth, rubric calibration or domain-expert agreement.


## Verified event-cloud smoke checks — November 4

The integration runs separately at `https://d37rt8nwcs1lq3.cloudfront.net/proxy/8791/workspace/`, guarded by the supplied workshop login. Private configuration stays on the event host and LGND login stays in the event Secrets Manager secret. No new public endpoint or AWS permissions were created. The existing 8787 console remains available.

- Run `89e4bb9a-568a-4ae5-8e11-c84463b06736`: real Kimi agent, LGND imagery search and image check, three valid judges, three locations, 10/10 declared values matched, all reported locations in the saved Napa County boundary. The agent took 22 seconds; model-based cost estimates were $0.18 agent / $0.07 judging. The archived report replayed in the new UI, with actual image chips and recorded dates.
- Run `fdc0285f-7b12-4414-88e5-0948318b5baa`: started through the new browser form with Kimi; seven actual trace entries appeared via progress snapshots, followed by automatic transition to the finished evaluation. Two successful LGND tool calls, three model calls, zero tool errors, two reported locations, 5/5 declared values matched, three valid judges. Agent runtime 37 seconds; estimated $0.16 agent / $0.07 judging.

The second run was also re-judged through the new UI: all three judges returned usable replies and the browser returned to the updated evaluation automatically. Earlier judgements were preserved.

Both panels scored 100 under the current starting rubric. These smoke results demonstrate integration, not independent vineyard identification, completeness, expert agreement or calibrated accuracy. Imagery dates are historical (2020–2022); the answers preserve the uncertainty and current-status limitations. Licence blockers remain visible. The UI exposes reference accuracy only when the backend has a tied reference set. No fabricated human review was added to the event archive during QA.

Local checks: 301 Python tests passed, one infrastructure-only test module skipped because it requires the optional CDK group; four frontend contract tests passed; TypeScript build, Python lint/format/type checks passed. GitHub CI also runs the optional infrastructure checks, frontend rebuild consistency and secret scanning. The finished-source ZIP contains tracked source and built assets only, excluding credentials, local configuration, dependencies, traces and private outputs.

Review fixes after PR #12's code review: [review-fixes.md](review-fixes.md).
