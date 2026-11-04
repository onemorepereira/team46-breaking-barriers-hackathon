# Console: Dark Theme, Calm Map Interactions, Narrowing and LGND Fixes: Handoff

**What shipped** (branch `design/eval-harness`, 2026-11-04):
- **Dark only:** the console, the runs page and the static reports are all dark.
- **API reference:** `/api/docs` is now Scalar, framed under the console's standard header and in its colors, replacing Swagger.
- **Docked panel:** result details open in a panel docked inside the map, replacing the clipped popups. The page no longer jumps when you open it.
- **Step links:** they scroll the timeline, not the page, or offer a toast. The mouse wheel over the map scrolls the page.
- **Run `fdacf7cf`:** its two root causes are fixed:
  - narrowing never worked through the real payload;
  - the LGND access token (300 s) was never refreshed.
- **Also fixed:** "Failure modes: [object HTMLSpanElement]" on the scorecard.

**Verification:**
- [x] **AC1 Dark only.**
  - `test_console_is_dark_and_map_details_dock_instead_of_popping_up`: every page has `data-bs-theme="dark"` and `color-scheme: dark`, `/api/docs` links the dark sheet, and the report's CSS is dark with no `prefers-color-scheme`.
  - The probe measured body text at 14.2:1 against its background.
  - Screenshots reviewed: console, run (desktop and phone), runs, report and API docs.
  - The cyan text token is `#22d3ee`; button fills are `#0e7490` under white text.
  - All 56 existing reports were regenerated from the archive, so they're dark too.
- [x] **AC2 Docked panel**, **AC3 no page jumps**, **AC5 wheel**, **AC7 accessibility.** `tests/browser/console_probe.py` ran against the live console at 1366×860 and 390×900 and exited 0 (no failures):
  - 6 tile clicks: page moved 0 px each, panel always inside the map, `map.getPadding()` all zeros;
  - focus moved to the close button, then Esc closed the panel, returned focus to the tile and moved the page 0 px;
  - the step link moved the page 0 px and showed the toast (the list was off screen at that size);
  - the wheel over the map scrolled the page 400 px.

  Before the fix, the same measurements found a 381 px popup in a 520 px map with its top clipped, 487 px and 908 px page jumps, and the wheel stolen by the map.
- [x] **AC4 Timeline-only step links.** The probe covers the toast path. CI checks that `app.js` has exactly one `scrollIntoView`, the toast's Show button. Scorecard and claim refs are now `<button>`s with `aria-label`.
- [x] **AC6 Narrowing through the real wiring.** `test_narrowing_works_through_the_real_payload_wiring` fails before the fix (1 failed) and passes after. On the live local re-run `2855dc1a`:
  - 10 circles fully inside Texas were **kept**;
  - the 6 circles crossing the state line (El Paso, Laredo, Rio Grande valley) were correctly widened to the boundary;
  - before the fix, run `fdacf7cf` had 0 of 9 circles kept.
- [x] **AC8 LGND stays signed in.** `test_token_is_refreshed_before_it_expires_and_on_a_401` runs through a real `httpx.Client`; the 3 earlier auth tests were restored alongside it. Live checks:
  - one LGND session made a call every 60 s, and **all 8 succeeded over 426 s**, past the 300-second token;
  - the redeployed AgentCore run `a5670c6b` made its last LGND call at 334 s with **0 errors**.

**Exercised live:**
- **AgentCore** was redeployed with `cd infra && CDK_DOCKER=podman npx aws-cdk deploy`, 84 s, with the runtime updated.
- **The Texas parks prompt on AgentCore** (`a5670c6b`, Kimi) scored **85.4, High**. It had 0 errors in 11 tool calls, 15/15 claims verified, and 8/8 located sites inside Texas. 5 circles were kept and 1 crossing the state line was widened. It cost $0.81 for the agent and $0.31 for judging, in 413 s.
- **Before the fixes:** `fdacf7cf` (local) failed with no answer at $1.50, and `2855dc1a` (local, narrowing fixed, token not) hit the step limit once LGND went dark at 290 s.
- **The console:** the browser probe passes at both widths. Screenshots of `/api/docs` were reviewed at 1280 px:
  - the header is identical to the other pages (brand at x=86, 59 px tall, measured on `/runs` and `/api/docs`);
  - the request client works: "Test Request" then Send showed headers, parameters and the JSON body. Before the frame, Tabler's global styles crushed its response tabs;
  - one navy palette throughout;
  - no hosted upsells;
  - no stuck placeholder;
  - no script errors.

**Root-cause trail for run `fdacf7cf`:**
1. Circles were widened. `invoke.attach_area` drops `geometry` from the agent payload, so the hook had no boundary to check against. Fixed: the hook checks against the `lgnd_area` ring.
2. The re-run (`2855dc1a`) kept the circles, but LGND still failed after a point. Rate limiting was ruled out: 30 parallel calls in three bursts all succeeded. Both runs' last LGND success came at exactly 290 s, and the JWT's lifetime is exactly 300 s. Fixed: `RefreshingBearer`.

**Gate history:**
- **Design:** 3 subagent passes, with 7, 3 and 4 blockers. The 4 left after pass 3 went to the user with proposed fixes, and were approved and applied: keyboard toast focus, ref buttons, re-docking on resize, one map click handler.
- **Build:** probe-driven.
- **Verify:** see above.

**Decisions:**
- Dark only, the docked panel and timeline-only scrolling were the user's calls.
- `httpx` is now a declared dependency.
- The browser probe is committed but not in CI (it needs Playwright and a running console).

**Mistake caught:** while building, I overwrote `tests/test_lgnd_auth.py`, which already held three tests (token rotation, no rotation, empty secret). They were restored from git and the new tests appended; all 5 pass.

**Also found while verifying `/api/docs`:**
- Scalar's bundle auto-mounts an empty second instance on any element with id `api-reference`, so our mount element is `#foundry-api`.
- Scalar puts its `dark-mode` class on `<body>`, which needed the `html body.dark-mode` selector.
- **Mistake:** restarting the console during Verify killed a run the user had just started (`29dcf655`, Ilocos Norte, 0 model calls, no cost). It needs to be run again.

**Follow-ups:**
- `/api/docs` loads Scalar from jsDelivr (4.6 MB), as Swagger did before. Vendor it if the docs page must work offline.
- When a budget limit hits, ask the model for a final answer with no tools, so a run that ran out still reports what it found.
- Keep LGND's MCP error code and data in the trace, not just "Server returned an error response".
