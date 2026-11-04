# Console: Dark Theme, Calm Map Interactions, Narrowing Fix: Spec

**Status:** Built

## Problem
Three problems affect the people demoing and reading runs in the Team Foundry console:
1. The console is light, and the user wants a dark UI.
2. Map interactions misbehave, all measured in headless Chromium on run `a9a69e76`:
   - a result popup is 381 px tall in a 520 px map, so its top gets clipped;
   - the first click on a tile scrolled the page 487 px, because MapLibre focuses the popup's close button on open and the browser scrolls to it;
   - a "from T5" step link scrolled the whole page 908 px.
3. Run `fdacf7cf` (Kimi, "data centers within 10 miles of national or state parks in texas") ended without an answer, at $1.50. The agent narrowed its searches to 16 km circles around parks inside Texas. Every one was widened to all of Texas, because the agent's payload carries no `geometry` (`invoke.attach_area` drops the 45,740-point boundary). The narrowing check in `agent/hooks.py` therefore never had a boundary to check against. The searches all returned the same statewide results, and the run exhausted its 400k input-token budget. LGND also rejected every search after a point (`Server returned an error response`). **Found in Verify:** the LGND access token lives exactly 300 s (JWT `exp − iat`), and `tools/lgnd/client.py` fetched it once at startup and sent the same header for the whole run. In both this run and its re-run (`2855dc1a`), the last successful LGND call came at 290 s, and everything after it failed. It wasn't transient, as first assumed. Every run longer than about 5 minutes lost LGND.

## Acceptance criteria
- [x] **AC1 Dark only.** Every console page (console, run, runs), the static run report and `/api/docs` render dark, with no theme toggle (the user's call). Text and badges keep readable contrast (WCAG AA ≥ 4.5:1 for body text), and the brand cyan and orange stay the accents.
- [x] **AC2 Docked detail panel.** Clicking a result on the map, or a tile in the strip, opens its details in a panel docked inside the map's right edge, at the map's full height, scrolling internally if needed. It's never clipped. The map eases so the result stays visible beside the panel. The panel closes with its × button or Esc. At phone width it docks to the bottom half of the map. MapLibre popups are no longer used for results.
- [x] **AC3 No page jumps from the map.** Opening, changing or closing the panel never scrolls the page (measured: `scrollY` unchanged).
- [x] **AC4 Step links scroll the timeline only.** "from T5", scorecard refs and claim refs scroll only the "What the agent did" list to the step, and flash it, without moving the page when the step will land on screen after the list scrolls. Otherwise (the list off screen, or the step would land below or above the fold) a small toast ("Step T5 is in the timeline", with a "Show" button) offers the jump; the page moves only if the user clicks it.
- [x] **AC7 Accessible.** The panel is a labelled region (`role="region"`, `aria-label="Result details"`). Opening it moves focus to its close button without scrolling, and closing it (× or Esc, while the panel is open) returns focus to the element that opened it, also without scrolling. The toast is `role="status"` with `aria-live="polite"`, stays 8 s, and pauses while hovered or focused, so its Show button is reachable by keyboard.
- [x] **AC5 The wheel scrolls the page.** Wheel over the map scrolls the page. The map zooms with Ctrl/⌘ + wheel, pinch or its buttons (MapLibre `cooperativeGestures`). On touch screens this means two-finger pan, which is accepted: one finger scrolls the page.
- [x] **AC6 Narrowing works for real.** A narrower area that the agent sends inside the boundary is kept when built through the real `area.payload_area` → `invoke.attach_area` → hook path, judged against the agent's simplified LGND ring. A test fails before the fix (done: `test_narrowing_works_through_the_real_payload_wiring`). A live re-run of the `fdacf7cf` prompt shows **circles fully inside the ring kept** (`harness.tool.area_requested` absent on those calls). Circles crossing the state line (e.g. around Big Bend on the Rio Grande) are still correctly widened to the boundary.

- [x] **AC8 LGND stays signed in for the whole run.** The LGND client refreshes its access token before it expires (60 s margin) and retries once on a 401 (`tools.lgnd.auth.RefreshingBearer`, an `httpx.Auth` passed as `MCPClient(auth_provider=…)`). Checked by a test through a real `httpx.Client`, and live by one LGND session that keeps succeeding past 300 s.

## Non-goals
- A light theme or a theme toggle.
- Retrying other LGND server errors inside the harness. The trace keeps only LGND's generic MCP message; recorded as a follow-up.
- A graceful "wrap up" answer when a budget limit hits. It's a separate change, recorded as a follow-up.

## Assumptions
- Tabler 1.7.3's built-in `data-bs-theme="dark"` (it ships `[data-bs-theme=dark]` rules, confirmed in the vendored CSS) covers all Tabler components; our own CSS overrides are the rest. Owner: build. Default: verified by screenshots.
- MapLibre 5.24.0 supports `cooperativeGestures` (present in the vendored build, with its `maplibregl-cooperative-gesture-screen` CSS). Owner: build.
