# Example Prompt Cards by Continent: Handoff

**What shipped** (branch `design/eval-harness`, 2026-11-04):
- The run form's four example chips are replaced by 16 example cards, under continent tabs: Asia 10, Africa 1, Europe 1, North America 2, South America 1, Oceania 1, and All.
- Asia opens first. Eight of its cards are in Asian Development Bank developing member countries: India, Bangladesh, Vietnam, Indonesia, Pakistan, the Philippines, Nepal and Mongolia. Laos and Japan are kept from before.
- Each card shows the continent, country, task, place and a development theme with an icon. A click fills the prompt box and doesn't start a run, as before.
- The cards are data, in `harness/web/static/examples.json`.
- Also fixed: at phone width, the map card's basemap switcher overflowed the page. It now wraps.

**Verification** (2026-11-04):
- [x] **AC1, AC6** `test_example_cards_cover_every_continent_with_asia_first_and_are_served` checks the shape, the six continents, Asia ≥ 8 and over half of the cards, unique prompts, and that every icon exists in the vendored Tabler Icons font. 130 tests pass; ruff and mypy are clean.
- [x] **AC2–AC4, AC7** Driven in headless Chromium (Playwright) against the running console, at 1366 px and 390 px:
  - tabs read "Asia 10 … All 16", and Asia is active with `aria-pressed="true"`;
  - clicking a card filled the prompt, marked that card selected and started no run;
  - All shows 16 cards;
  - no horizontal scroll at either width (after the basemap fix).

  Screenshots were reviewed and match the layout the user picked (continent tabs over a grid). The console has no dark mode, so there is no dark theme to check.
- [x] **AC5** Every card's place resolved live through `area.area_for_prompt` to an OSM relation: Jodhpur district 16700652, Sylhet Division 3921222, Ca Mau 1873490, Riau 2390840, Sindh 357981, Ilocos Norte 1504744, Gandaki 10489605, Ömnögovi 270051, Aswan 3061757, Extremadura 349050, Rondônia 325866, West New Britain 3777384, Nagoya 4576938, Khammouane 5831658. Richardson (relation 6577487) and ZIP 75080 (2020 ZCTA) were already verified by today's live runs.
- [x] **AC8** Live console run `a9a69e76` (Sonnet, India solar parks):
  - the area was Jodhpur district; 7 tool calls; 8/8 claims verified and inside the district; 30 of 31 search results inside;
  - scored **87.5, High** (Mistral 93.8 sitting for Opus, DeepSeek 87.5, Kimi 81.2);
  - agent $0.32, judging $0.14, 42 s.

  NAIP has no India coverage, so the agent seeded a Sentinel-2 similarity search at Bhadla and imagery-checked the candidates.

**Exercised live:** yes, the running console at 127.0.0.1:8787 (above).

**Deferred:** the other 15 cards have verified areas but no full run. A card whose feature LGND can't find should be reworded or dropped (spec assumption).
