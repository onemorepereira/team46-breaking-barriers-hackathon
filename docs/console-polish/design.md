# Console: Dark Theme, Calm Map Interactions, Narrowing Fix: Design

**Status:** Current · spec: [spec.md](spec.md) · the user picked the layouts on 2026-11-04 (dark only, docked panel, timeline-only scrolling).

## Components

| Component | Change | ACs |
| --- | --- | --- |
| `harness/web/templates/base.html` | `<html lang="en" data-bs-theme="dark">`: Tabler's color mode for every console page. `<meta name="color-scheme" content="dark">`, so scrollbars and form controls are dark too | AC1 |
| `harness/web/static/app.css` | Dark tokens for our own colors: surfaces from Tabler's `--tblr-bg-surface*`; icon tints and the `step-icon-*` colors raised in lightness for contrast on dark (e.g. model indigo `#a5b4fc`, run slate `#94a3b8`); `.vote-na` and the tile backgrounds; the cyan ink accent `#22d3ee` on dark (the `#0891b2` ink fails contrast on dark surfaces). Plus the `.foundry-detail` panel, the toast and the map gesture-hint styles | AC1, AC2, AC4 |
| `analysis/templates/_style.html` | The report's `:root` holds the dark palette directly (no `prefers-color-scheme`), with `color-scheme: dark` | AC1 |
| `harness/web/app.py`, `templates/api_docs.html`, `static/api-docs.{js,css}` | **Revised during Verify (the user's call, after the recolored Swagger was rejected as looking amateur):** `/api/docs` renders **Scalar API Reference 1.75.0** (pinned, released 2026-10-16, loaded from jsDelivr with Subresource Integrity) under the console's own header. Scalar lives on a separate, Tabler-free page (`/api/reference`, framed full height by `/api/docs`), because Tabler's global styles crushed Scalar's request client (reproduced: the same client renders correctly without Tabler). The frame also keeps `/api/docs` on the shared header template, identical to every page. Settings: dark forced, toggle hidden, `theme: "none"`, `telemetry: false` (Scalar's default is on), developer tools off. Colors live in `api-docs.css` (`html body.dark-mode`: Scalar sets the class on `<body>`). Scalar's hosted upsells (Ask AI, Generate SDKs & MCP), which send the document to scalar.com, are hidden. In 1.75.0, `agent: {disabled: true}` doesn't remove Ask AI on localhost, so a small observer hides it by label. The mount element is `#foundry-api`, **not** `#api-reference`: the bundle auto-mounts a second, empty instance on that id (`getElementById("api-reference")`), which left a stuck loading placeholder at the top | AC1 |
| `harness/web/static/app.js`, map | `new maplibregl.Map({... cooperativeGestures: true})`. Results open in a `#detail` panel (an absolutely positioned child of the map's card body, over the map). `openDetail(p, {move})` fills and shows the panel. **Exactly one camera call per action, and no persistent map padding** (design pass 1):
  - **Map click** (`move: "ease"`): `map.easeTo({center: [lon, lat], offset: [-panelWidth/2, 0], duration: 500})` (on phones `offset: [0, -panelHeight/2]`). `offset` applies to that call only; we never pass `padding` to `easeTo`, which would persist.
  - **Tile strip** (`move: "fit"`): only `fit(bbox, 16)`, whose `fitBounds` padding includes the panel (`pad()` returns `{top: 40, bottom: 40, left: 40, right: panelWidth + 40}`, or bottom on phones). Then `openDetail` with `move: "none"`, so the zoom-to-tile animation isn't cancelled.
  - Every other `fit()` (`fitAll`, timeline step clicks) also uses `pad()`, so results land beside an open panel. Verify asserts `map.getPadding()` stays all zeros.
  - **Docking:** the panel docks at the bottom (55% of the map's height) when the viewport is ≤ 575.98 px **or the map is narrower than 600 px**, so right-side padding can never swallow the map. Otherwise it docks right, at 300 px. `pad()` adds the panel's size only while it is open.
  - **Live run:** while the panel is open, the stream's automatic fits are skipped: on new results (the `step` handler) and on the `area` event's `fitAll()`. so the view doesn't jump away from the result being read. New results still appear on the map.
  - `closeDetail()` hides the panel with no camera move. Esc closes it through a `keydown` listener on `document`, active only while the panel is open.
  - Focus (AC7): on open, `close.focus({preventScroll: true})`; on close, the opener gets `focus({preventScroll: true})`. During a live run, the tile strip is re-rendered as results stream, so the opener may be detached. Its `data-key` is then used to find the re-rendered tile, falling back to the map canvas. The panel is `role="region" aria-label="Result details"`.
  - `maplibregl.Popup` is removed. | AC2, AC3, AC5 |
| `harness/web/static/app.js`, `scrollToStep(ref)` | Compute where the step **will land** in the viewport after the list scrolls (design pass 2): `final = clamp(top, 0, list.scrollHeight - list.clientHeight)` and `landing = stepRect.top - (final - list.scrollTop)`. If the step then lies fully inside the viewport (`0 ≤ landing` and `landing + step.offsetHeight ≤ innerHeight`), scroll the list to it, with a rect-based offset: `top = list.scrollTop + (step.getBoundingClientRect().top - list.getBoundingClientRect().top) - list.clientHeight/2 + step.offsetHeight/2`. Then `list.scrollTo({top, behavior: "smooth"})` and flash the step, never calling `scrollIntoView`. Otherwise show a toast (`role="status" aria-live="polite"`), "Step T5 is in the timeline · Show", for 8 s, paused while hovered or focused. "Show" calls `step.scrollIntoView({block: "nearest", behavior: "smooth"})`, the only page scroll, and only on request | AC4 |
| `harness/web/templates/run.html` | Adds the panel and toast containers | AC2, AC4 |
| `tools/lgnd/auth.py`, `tools/lgnd/client.py` | `RefreshingBearer(httpx.Auth)`: holds the token and its JWT `exp` (or now + 300 s if unreadable). Before each request, it refreshes when within 60 s of expiry, under a lock so parallel tool calls refresh once. On a 401 it refreshes and retries once. `make_client` passes it as `MCPClient(url=…, auth_provider=…)`, so Strands 1.63 hands it to the streamable HTTP transport. httpx 0.28 runs `auth_flow` for async clients too. The refresh is a short blocking call about once every 4 minutes, accepted. `httpx` becomes a declared dependency (it was already installed with `mcp`). Agent-side, so AgentCore needs a redeploy | AC8 |
| `agent/hooks.py`, `tools/lgnd/areas.py` | (Done.) The boundary for the narrowing check is `search_area["geometry"]` or `ring_polygon(search_area["lgnd_area"])`, i.e. the same ring LGND searches when the area is enforced | AC6 |

## Resolved at the design gate's third pass (approved by the user)
1. **Keyboard toast:** when a step link is activated from the keyboard (a click with `event.detail === 0`) and the toast appears, focus moves to its Show button with `preventScroll`.
2. **Step refs are buttons:** scorecard and claim refs are `<button>`s with `aria-label="Show step T5"`, so all three link types work from the keyboard.
3. **Re-docking:** the map's `ResizeObserver` also re-applies right or bottom docking while the panel is open (rotation, resize), so `pad()` and the panel always agree.
4. **One map click handler:** `queryRenderedFeatures` checks the layers in priority order (claims, then result dots, then footprints). The first hit wins, giving one `openDetail` and one camera call per click.

## States
- **Panel:** closed (the map is full width); open (the result shown, × and Esc close it); open while another result is clicked (contents replaced, the map eases to the new one); a result with no tile (text only, with "No imagery tile"); and a tile that fails to load (`onerror` shows "Tile unavailable", and the provider attribution stays).
- **Toast:** hidden, or shown for 8 s (paused while hovered or focused). It's replaced if another link is clicked.
- **Live run:** the panel works during streaming. The data arrives in `data.chips` as before.

## Options considered
- **Dark:** we considered our own palette on top of Tabler's light theme, and Tabler's built-in dark mode. We chose Tabler's built-in mode: it's maintained with the components, with less CSS of our own.
- **Details:** we considered a smarter popup (anchoring and smaller tiles) and a docked panel. The user chose the panel: it never clips, and it has room for a bigger tile.
- **API reference:** we tried a recolored Swagger first (rejected by the user as looking amateur). The options were Scalar (purpose-built, three panes, a live request panel) or our own Tabler page from `/openapi.json`. The user chose Scalar.

## Failure modes
- The vendored Tabler lacks dark styles for a component: our CSS covers it; screenshots in Verify catch any gaps.
- The panel is open when the map resizes: the existing `ResizeObserver` calls `map.resize()`, and the panel is CSS-positioned.
- jsDelivr is unreachable: `/api/docs` shows only the console header. Everything else in the console is vendored, and `/openapi.json` always works.

## Rollback
Revert the commits. There's no data change; the narrowing fix is agent-side and tested. **One-way doors:** none.

## Implementation plan
1. Narrowing fix (done, with a failing-first test). A live re-run comes in Verify.
2. Dark: `base.html`, the `app.css` tokens, the report style, the API reference (Scalar). Screenshots of every page.
3. The panel and gestures in `app.js`/`run.html`/`app.css`; remove the popup.
4. Timeline-only `scrollToStep`, plus the toast.
5. A committed browser probe, `tests/browser/console_probe.py`, run as `uv run --no-project --with playwright python tests/browser/console_probe.py` against a running console. It isn't collected by pytest. It waits on events, not sleeps: `map.once("idle")` exposed through `window.__foundryIdle()`, and `scrollend` or a stable `scrollY` over two animation frames. It measures panel-in-map containment, `scrollY` deltas (tile click, map click, ref link, Esc), `map.getPadding()`, wheel over the map, and focus. Plus a contrast check of the text tokens on their surfaces (WCAG formula).
6. A test in `tests/test_web.py`: pages carry `data-bs-theme="dark"`; `/api/docs` links the dark sheet; `app.js` no longer builds a `maplibregl.Popup` and sets `cooperativeGestures`.
