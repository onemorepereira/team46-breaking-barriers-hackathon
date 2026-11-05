# Connected evidence workspace

The React workspace, merged into `main` in PR #12 (branch `integration/foundry-ui`) and extended since; later changes are listed under [Later updates](#later-updates). The supplied `AWS HACK 2.0.zip` was preserved unchanged. Its React/Figma visual language is retained; hardcoded Bangladesh results, scores, timers and prototype state buttons are removed. Figma-specific tooling, deployment metadata and third-party instruction files are not part of this app.

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

In Aditya's event workshop, keep the private `harness.local.yaml` outside Git and use `uv run python -m scripts.adi_sandbox ui --workshop-proxy`. The guard requires the event account (set `event_account_id` in your private `harness.local.yaml`; it isn't in the repo) / WSParticipantRole / us-west-2, and refuses to start without it; it rejects personal profiles and other accounts. Never put AWS keys, LGND tokens, or client secrets in frontend environment variables, browser storage or Git. The UI only uses same-origin authenticated backend APIs. The workshop's existing sign-in protects its `/proxy/<port>/` path; these changes do not create a public deployment or change IAM permissions.

## What works

- Prompt and model selection from the backend's configured models; POST /api/runs starts real work.
- Live progress snapshots (every two seconds, using the same event records as SSE) show area resolution, actual completed steps and judge replies; no invented progress percentages or scores.
- Previous runs load from the real paginated archive; a `?run=<id>` URL opens one directly.
- MapLibre displays the saved boundary, tool-returned image footprints and deduplicated coordinate claims. Selecting a location links to its saved evidence step. Coordinates are not fabricated from place names. The map frames the reported sites and imagery results with the area polygons that contain them, or else the area's largest polygon, so far-flung islands of an administrative area don't zoom the map out ([map fit](../map-fit/handoff.md)).
- When the [visual check](../visual-check/handoff.md) ran, each reported site carries its verdict (✓ seen, ✕ not seen, ? can't tell) and the legend reads "Visually checked: x of y sites seen".
- Final answer, result tiles showing the scene observed on the recorded date ([observed scenes](../observed-scenes/handoff.md)), complete source-value table, request-condition matrix, independent judge rationales, workflow/output scores, trace integrity and cost estimates come directly from the run view.
- The review form posts the reviewer's name, selected judged criterion, agreement or suggested rubric score with reason/refs to the existing feedback API. Missing/invalid inputs remain visible as errors. The review does not change the automated score by itself. A saved current review can be sent to the judges with **Ask judges to reconsider**; the original judgement remains archived. The existing Guidance editor remains available for approving lessons.
- Re-judge uses archived evidence with the configured judge panel (three passes, added to earlier passes on unchanged evidence) and the visual check (earlier verdicts reused); it makes paid model calls. JSON export and static HTML reports preserve detailed evidence.
- Mobile layout, keyboard submission, labelled controls, reduced motion and error/empty/not-scored states are included.

## LGND / ADB usability choices

The LGND/Ode work for ADB values per-asset evaluation, checkable references, analyst effort and cost, uncertainty, transferable workflows and presentation-safe sources and licences ([what it means for us](../adb-alignment/lgnd-ode-brief.md)). Accordingly, the UI separates the panel score from reference metrics, exposes the archived reference/matching rule and licence blockers, and does not label a source-text match as ground truth. When no reference is tied, the page says recall, precision and transfer performance are not established. Existing backend ADB reference/license code is reused; this integration does not invent a full transfer benchmark, analyst-time measurement or scientific validation.

Satellite context uses the backend's cached basemaps (Sentinel-2 cloudless 2023 by EOX, USGS imagery and NAIP), each with its credit. Street tiles are fetched directly from OpenStreetMap by the browser, preserving the existing policy of not proxy-caching OSM tiles. The basemap is context, not the evidence used for the agent's decision; the evidence is in the inspector's images. Licence restrictions still require review before presenting datasets to third parties.

## Validation boundaries

The short-request progress endpoint avoids buffering in authenticated workshop proxies; the original SSE endpoint remains available. Reading before the worker creates its trace file returns an empty event list rather than dropping the connection.

CI builds/typechecks the frontend, runs frontend contract tests, checks built assets are current, runs the Python tests and secret scan. Browser QA and event-cloud smoke results are recorded separately below. Passing these checks establishes software integration, not geospatial truth, rubric calibration or domain-expert agreement.


## Verified event-cloud smoke checks — November 4

The integration runs separately at `https://d37rt8nwcs1lq3.cloudfront.net/proxy/8791/workspace/`, guarded by the supplied workshop login. Private configuration stays on the event host and LGND login stays in the event Secrets Manager secret. No new public endpoint or AWS permissions were created. The existing 8787 console remains available.

- Run `89e4bb9a-568a-4ae5-8e11-c84463b06736`: real Kimi agent, LGND imagery search and image check, three valid judges, three locations, 10/10 declared values matched, all reported locations in the saved Napa County boundary. The agent took 22 seconds; model-based cost estimates were $0.18 agent / $0.07 judging. The archived report replayed in the new UI, with actual image chips and recorded dates.
- Run `fdc0285f-7b12-4414-88e5-0948318b5baa`: started through the new browser form with Kimi; seven actual trace entries appeared via progress snapshots, followed by automatic transition to the finished evaluation. Two successful LGND tool calls, three model calls, zero tool errors, two reported locations, 5/5 declared values matched, three valid judges. Agent runtime 37 seconds; estimated $0.16 agent / $0.07 judging.

The second run was also re-judged through the new UI: all three judges returned usable replies and the browser returned to the updated evaluation automatically. Earlier judgements were preserved.

Both panels scored 100 under the rubric of the time (version 2). These smoke results demonstrate integration, not independent vineyard identification, completeness, expert agreement or calibrated accuracy. Imagery dates are historical (2020–2022); the answers preserve the uncertainty and current-status limitations. Licence blockers remain visible. The UI exposes reference accuracy only when the backend has a tied reference set. No fabricated human review was added to the event archive during QA.

Local checks at the time: 301 Python tests passed, one infrastructure-only test module skipped because it requires the optional CDK group; four frontend contract tests passed; TypeScript build, Python lint/format/type checks passed. GitHub CI also runs the optional infrastructure checks, frontend rebuild consistency and secret scanning. The finished-source ZIP contains tracked source and built assets only, excluding credentials, local configuration, dependencies, traces and private outputs.

Review fixes after PR #12's code review: [review-fixes.md](review-fixes.md).
Map imagery and fast run opening (PR #14; the inspector has since replaced its popup): [handoff](../workspace-map-popups/handoff.md).

## Workspace usability update

Branch `improve/workspace-usability` starts from main at `dc04626` and preserves the PR #12/#13 fixes. It adds:

- A map-side imagery inspector: selecting a reported point shifts the camera into the free space on its left. The agent's image comes only from that point's cited tool step; missing imagery is labelled. Where the visual check ran, the inspector opens on the checked image, with its verdict, reason and checker model, and a switch back to the agent's image. Every image shows a pill naming its source, resolution and date. All four basemaps, overlay controls, independent reference assets/false alarms and trace-to-map zoom remain available.
- A short bottom summary and **Expand summary** opening the right-hand **Summary** tab. It separates what was found, what is missing, how the search ran and what to check next. The saved full narrative remains available on demand.
- Findings, Evaluation, Actions and Summary tabs. Large answers, source tables, score detail, conditions, judge metadata, cost, licences, revisions and exports are collapsed by default. Section and accessibility preferences persist in this browser across runs, re-judges and reloads. Closed sections are unmounted; full reports are not stored in browser preferences.
- A clear **Rubric evaluation score** label. Judge agreement/reliability and independent reference accuracy metrics remain separate.
- Thumbs up/down beside the overall, workflow/output and criterion scores. Either response is saved immediately; thumbs down reveals an optional comment. **Detailed human review and reconsideration** retains authored multi-criterion reviews, measured-check notes, evidence references, original judgement access and explicit reconsideration.
- Judge guidance inside the workspace, including proposal, manual lesson editing, source links, estimate/confirm evaluation, progress, reports, approval/rollback, switch-off and reviewer agreement. These operations retain their existing backend rules. Quick thumbs feedback does not feed guidance or numeric human-score calculations.
- Editable prompt templates, model/verdict archive filters, better header alignment, and saved dyslexia-friendly reading, colour-safe palette, high contrast, larger text and reduced motion choices.

### Quick feedback API and retention

`GET /api/runs/{run_id}/reactions` lists quick responses. `POST` to the same path accepts `judged_at`, `target` (`overall`, a dimension or a criterion ID) and `vote` (`up` or `down`). A stale timestamp or an unscored/live run is rejected. `PUT /api/runs/{run_id}/reactions/{response_id}` saves an optional thumbs-down `comment` (up to 2,000 characters). Records retain the actual normalized score, rubric and original judgement timestamp under the deployment archive's `feedback/reactions/<run_id>/`. A comment added after re-judging stays attached to the original judgement. Responses are anonymous and count responses, not unique people. They make no model calls and do not automatically revise scores. The existing named `/reviews` API is unchanged.

### Feature parity checklist

| Classic console capability | Workspace location |
| --- | --- |
| Start/select model; follow live work; resume after refresh | New run and Actions |
| Archive pagination and model/verdict filters | Previous runs |
| Four context basemaps, boundary, chips, claim locations | Map and inspector |
| Reference found/missed assets and false-alarm cells | Map overlays; Evaluation benchmark |
| Full answer, all values, source links and imagery dates | Findings; map inspector |
| Rubric questions, anchors, every judge reason and evidence ref | Evaluation → Rubric scorecard |
| Every requested condition, gates, failures, recovery, cost/tokens | Evaluation expandable sections |
| Licences, independent benchmark, guidance snapshot, earlier judgement | Evaluation expandable sections |
| Multi-criterion authored review, measured note, saved reviews, reconsideration | Evaluation → Detailed human review |
| Draft/edit/evaluate/approve/rollback/off guidance and agreement | Judge guidance |
| Raw model/tool spans, metadata, step bounds, datasets | Actions |
| Static HTML and JSON evidence exports; API documentation | Evaluation exports; footer API link |

Software checks do not establish geospatial truth or accessibility certification. Verify third-party imagery availability and domain-specific reference validity independently. The synthetic preview deliberately has no real satellite imagery; quick-feedback write tests use an isolated synthetic local archive, never production reviewer data.

## Later updates

- **Per-question review and stable scores** (PR #17, [judging stability](../judging-stability/handoff.md)): Evaluation shows every judge's votes from every pass per rubric question, with *Agree* / *Suggest a different score* drafts collected into one review. The score hero shows passes, votes, ± standard error and the single-pass range. Location, imagery-dot, footprint and thumbnail clicks open the docked result panel.
- **Live panel** (PRs #20, #25): animates while the agent and judges work, and fits without scrolling.
- **Observed-scene tiles** (PR #30, [handoff](../observed-scenes/handoff.md)): result tiles are read from the scene observed on the chip's date, falling back to the mosaic.
- **Visual check** (PR #33, [handoff](../visual-check/handoff.md)): site verdict marks, the legend caption, the checked/agent image switch in the inspector, and "Visual check: x of y sites seen" in the live trail.
- **Evaluation issues** (PR #34, [handoff](../evaluation-issues/handoff.md)): each Evaluation section shows its issue count and each weak rubric question a dot; "Show only sections with issues (N)" hides the rest and is remembered in this browser. With no issues it reads "Nothing needs attention".
- **Map fit** (PR #35, [handoff](../map-fit/handoff.md)) and **an image pill on every inspector image** (PR #36).
