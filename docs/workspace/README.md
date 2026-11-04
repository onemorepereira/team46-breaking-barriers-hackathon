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
- The review form posts the reviewer's name, selected judged criterion, agreement or suggested rubric score with reason/refs to the existing feedback API. Missing/invalid inputs remain visible as errors. The review does not change the automated score by itself. The existing Guidance/classic-console workflow remains available for reconsideration and approving lessons.
- Re-judge uses archived evidence with the configured judge panel; it makes paid model calls. JSON export and static HTML reports preserve detailed evidence.
- Mobile layout, keyboard submission, labelled controls, reduced motion and error/empty/not-scored states are included.

## LGND / ADB usability choices

The supplied **LGND GeoAI Evals Inception Report, Draft V1 (Oct 20), pages 2, 5–8** emphasizes per-asset evaluation, checkable references, analyst effort/cost, uncertainty, transferable workflows and presentation-safe sources/licences. Accordingly, the UI separates the panel score from reference metrics, exposes the archived reference/matching rule and licence blockers, and does not label a source-text match as ground truth. When no reference is tied, the page says recall, precision and transfer performance are not established. Existing backend ADB reference/license code is reused; this integration does not invent a full transfer benchmark, analyst-time measurement or scientific validation.

Satellite context uses the backend's Sentinel-2/EOX cached basemap with attribution. Street tiles are fetched directly from OpenStreetMap by the browser, preserving the existing policy of not proxy-caching OSM tiles. The UI's basemap is context, not the evidence used for the agent's decision. Licence restrictions still require review before presenting datasets to third parties.

## Validation boundaries

The short-request progress endpoint avoids buffering in authenticated workshop proxies; the original SSE endpoint remains available. Reading before the worker creates its trace file returns an empty event list rather than dropping the connection.

CI builds/typechecks the frontend, runs frontend contract tests, checks built assets are current, runs the Python tests and secret scan. Browser QA and event-cloud smoke results are recorded separately below. Passing these checks establishes software integration, not geospatial truth, rubric calibration or domain-expert agreement.
