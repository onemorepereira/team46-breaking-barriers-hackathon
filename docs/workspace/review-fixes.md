# Workspace UI: Review Fixes

**What shipped:** fixes for the ten findings of the code review of PR #12, the Foundry workspace UI. Each finding was first confirmed against the PR's code.

| # | Finding | Fix | Proven by |
| --- | --- | --- | --- |
| 1 | The evidence map crashes on a feature with no geometry, and markers drift from the location list | Markers come from `candidatesOf`, the same filtered list the location panel uses, so marker *i* is always candidate *i*. The bounds code guards missing and non-finite coordinates | `candidates skip features with no geometry…` (node test); live: 14 markers for 14 distinct sites on run `6d5e9d6b`, with no console errors |
| 2 | `adi_proxy` rewrote each body chunk on its own: a split multi-byte character raised, and a split URL went unrewritten | HTML, JS and JSON bodies are buffered whole and rewritten once. An event stream is rewritten one complete event at a time, with incremental UTF-8 decoding | `test_proxy_rewrites_across_chunk_boundaries_and_split_utf8`, `test_proxy_rewrites_event_streams_one_whole_event_at_a_time`; smoke test through `WorkshopProxy` on `/static/app.js`, `/`, `/workspace/` and a 487 KB run view (valid UTF-8, no un-prefixed URLs) |
| 3 | `/progress` could report `done` while missing the last events | `done` is read **before** the events, so a `done: true` reply has every event written before the run ended | `test_progress_reads_done_before_events` (worker races between the reads) |
| 4 | Opening `?run=` during a live run 404'd and never resumed | `load()` resumes following when the run is still `running`, or exists only as a live run | Live: run `54ab922a` opened two seconds after it started was followed through searching, agent finished and judging to the end |
| 5 | A `load()` still in flight could overwrite a run just started | `start()` bumps the request ticket and closes the old stream | Code path; covered by the same ticket check `load()` uses |
| 6 | An empty or non-numeric suggested score saved as 0 or null, and there was a dead branch | A disagreement needs an integer score; the dead branch is removed | `a suggested score must be a number…` (node test) |
| 7 | The CI freshness check ignored untracked build output | `git status --porcelain` must be empty for `harness/web/static/workspace` | CI |
| 8 | Each 2-second poll re-read the whole trace and resent everything | `/progress?cursor=` returns only new events and a next `cursor`; the client appends | `test_progress_cursor_returns_only_new_events_and_done_means_drained`; live: 21 polls, every one after the first carried a cursor |
| 9 | `basePath` used the first `/workspace` in the path | It uses the last `/workspace` segment | `the base path is the part before the last /workspace segment` (node test) |
| 10 | A second Markdown renderer (`markdown-it`) beside the console's marked + DOMPurify | The workspace loads the vendored `marked` + DOMPurify, as it loads MapLibre, with plain text until they load. `markdown-it` is removed | Live: answers render (HTML, no plain fallbacks); the bundle shrank from 363 KB to 260 KB |

**Checks:** pytest, ruff, the formatter, mypy, the frontend node tests (7) and `pnpm build` (TypeScript) all pass. The built assets in `harness/web/static/workspace` are rebuilt and committed.

**Exercised live:** a console on this branch (port 8788) against the real archive. In Chromium, the workspace was opened on Pecos run `6d5e9d6b`, and on live run `54ab922a` mid-run.
