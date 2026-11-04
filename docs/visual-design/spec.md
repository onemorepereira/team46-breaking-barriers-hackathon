# Slice: Visual Design Pass on the Console

**Status:** Open · **Owner:** unassigned (someone with a good eye) · **Size:** about a day · **Branch:** `slice/visual-design` from `main` · **Merges:** last, after plain language and prompt compliance; rebase and restyle their new cards before your PR
**Read first:** [console polish record](../console-polish/handoff.md) (the dark theme, the result panel and what was measured), the [factory rules for slices](../factory.md#how-to-take-a-slice).

## Problem
The Team Foundry console works and is accessible, but it looks assembled, not designed. Tomorrow it's on a projector in front of judges, so it has to read as a polished product at a glance: clear hierarchy (the score first, then the evidence), consistent type and spacing, and the TF brand (cyan `#01D5F9`, orange `#FD8800`, navy `#0B1220`). Today's sore spots:
- the KPI strip's weight;
- dense scorecard rows;
- the plain timeline;
- uneven card headers;
- the static report looking unrelated to the console.

## What exists today (start here)
- **Pages:**
  - the console home and the run page: `harness/web/templates/run.html`, rendered by `harness/web/static/app.js`;
  - the runs list: `runs.html` and `runs.js`;
  - the shared header: `base.html`;
  - the static report: `analysis/templates/report.html` and `_style.html`;
  - the API reference at `/api/docs`, which is Scalar in a frame, colored by `static/api-docs.css`.
- **Styles:** the Tabler 1.7.3 dark color mode (`data-bs-theme="dark"` on `<html>`) plus our own `harness/web/static/app.css`. Its tokens are at the top: `--foundry-*`, and `--tblr-primary` set to cyan. Everything is vendored under `static/vendor/`, so there's no CDN except Scalar's.
- **Behavior checks to keep green:**
  - `tests/test_web.py` (page structure);
  - `tests/browser/console_probe.py`, run against a live console: no page jumps, the panel stays inside the map, focus and Esc behave, body text contrast.

## Acceptance criteria
- [ ] **AC1 Agree on a direction first.** Before you change CSS, show Miguel 2 or 3 directions, as screenshots or quick mockups of the run page (score card, scorecard, timeline), and get an explicit "go" on one. Record the choice and the mockups in `docs/visual-design/design.md`. **Time-box:** if there's no answer within an hour, go ahead with the direction you recommended, and note that in `design.md`.
- [ ] **AC2 One type scale and spacing system**, as tokens at the top of `app.css` (sizes, weights, line heights, a 4- or 8-px spacing scale, radii). Every card header, label and number uses them. No new one-off pixel values in the page CSS (a grep of the diff is the check).
- [ ] **AC3 Hierarchy at a glance:**
  - the score, verdict and confidence read from 3 m away (projector test: a screenshot at 1920×1080 scaled to 50% stays legible);
  - the KPI strip shows cost, tool calls, claims verified and claims in area with clear labels;
  - the scorecard shows each criterion's score and its votes without crowding.
- [ ] **AC4 Contrast and accessibility hold:**
  - all text at least 4.5:1 against its background, large text (≥ 24 px) at least 3:1;
  - badges and the status colors (good, warning, bad) are never the only signal: an icon or a word goes with them;
  - checked by `console_probe.py <your-run-id>` plus an axe-core run (e.g. `npx @axe-core/cli http://127.0.0.1:8787/runs/<id>`, no serious or critical findings). axe needs Node 18 or newer; if you don't have Node, record the probe's contrast results plus a manual check.
- [ ] **AC5 Every width works**: 390, 768, 1366 and 1920 px, with no horizontal scroll and nothing overlapping. Before and after screenshots of the console home, a run page and the runs list at 1366 and 390 px go in `docs/visual-design/screenshots/`.
- [ ] **AC6 The report matches.** `analysis/templates/_style.html` uses the same palette, type and spacing, so a report looks like part of the same product. (Regenerate one with `uv run harness replay <run-id>`.)
- [ ] **AC7 Behavior unchanged.** `uv run pytest` and `console_probe.py` pass, and the JSON from `/api/*` is unchanged.

## Non-goals and boundaries
- **Visual only.** You may edit `app.css`, `_style.html`, the templates' markup and classes, and `app.js` or `runs.js`, but only for class names and markup. No new features, data, endpoints or behavior.
- Keep Tabler, MapLibre and the vendored assets. No new framework, build step or CDN fonts (vendor a font into `static/vendor/` if you need one, with its license).
- Dark only, as the user decided: no light theme or toggle.
- Don't change map interactions, the result panel's behavior or step scrolling (they were measured and approved), or Scalar's internals (colors in `api-docs.css` are fine).

## How to check your work
```sh
uv run harness ui            # http://127.0.0.1:8787, with archived runs to look at
uv run pytest && uv run ruff check .
uv run --no-project --with playwright python tests/browser/console_probe.py <your-run-id>
```

## When done
Write `docs/visual-design/handoff.md` (the direction picked, the screenshots, contrast and axe results), set Status to `Built`, update [the factory](../factory.md), and open a PR to `main`.
