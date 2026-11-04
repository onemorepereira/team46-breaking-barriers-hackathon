# Example Prompt Cards by Continent: Spec (Quick track)

**Status:** Built

## Problem
The console's run form offers four example prompts. Three are in North America or Japan and one is in Laos. Someone demonstrating the harness to ADB can't show in one click that the scoring works across regions, and in particular in the developing Asian economies ADB lends to **[team]**.

## Acceptance criteria
- [x] **AC1** The run form shows example cards for all six inhabited continents. Asia has at least 8 cards, mostly in ADB developing member countries.
- [x] **AC2** A row of continent tabs filters the grid; Asia is selected on load, and an "All" tab shows every card. Each tab shows its card count.
- [x] **AC3** Clicking a card fills the prompt box and changes nothing else. It doesn't start a run (the user's call: "same as they are now").
- [x] **AC4** Each card shows the continent, the country, the task, the place, and a development theme with an icon.
- [x] **AC5** Every card's place resolves, through the console's area lookup, to an official boundary (an OSM relation or a US Census ZCTA), so the run gets an area check. Verified live, and recorded in the handoff.
- [x] **AC6** The cards are data (`harness/web/static/examples.json`), not code. A test checks the shape, the continent coverage, the Asia count and unique prompts.
- [x] **AC7** The layout works at phone width (no horizontal scroll) and in the console's light theme (it has no dark mode). Cards are keyboard-operable buttons, and the tabs expose `aria-pressed`.
- [x] **AC8** At least one new Asia card is run end to end, then judged, in the console.

## Non-goals
- Auto-running a card on click.
- Checking that LGND imagery actually contains the feature for every card: only the area is verified for all of them, and a full run for AC8.
- New tools, indexes or rubric changes.

## Assumptions and open questions
- The features chosen (solar parks, floods, shrimp ponds, forest clearing, reservoirs, open-pit mines, oil palm) are visible at Sentinel-2's 10 m resolution, so LGND's `s2` index can find them outside the US. NAIP covers the US only. Owner: team. Default: drop a card that fails in a live run.
- "Development interest" means ADB developing member countries and ADB's themes: energy access, climate resilience, food security, livelihoods and land use **[team]**.

## Plan
1. `examples.json` with 15 cards; a test for shape and coverage (AC1, AC6).
2. `run.html` and `app.js`: continent tabs and a card grid in place of the chips, with click-to-fill and a selected state (AC2–AC4).
3. `app.css`: card styling, plus hover and selected states (AC7).
4. Verify: resolve every area live (AC5), screenshots at desktop and phone width (AC7), one live Asia run (AC8).

## Design review
The user picked "continent tabs and grid" from three options (2026-11-04), with clicks behaving as they do now.
