# ADB Deployment Profile — Spec

**Roadmap:** R9 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none · **Size:** S–M (about 3–4 days)
**Background:** [what the LGND/Ode inception report means for Track 1](../adb-alignment/lgnd-ode-brief.md)

## Problem
A Team Foundry deployment can be cleared for ADB use only by auditing it by hand, and nothing stops a slip. Licence status is shown as a label: a run that used non-commercial material still produces a report, an export and console views, with an amber "check before sharing" note. Three such sources are on by default today:
- The visual check reaches for Vantor Open Data first. Vantor is CC BY-NC 4.0.
- The console's default context basemap is EOX Sentinel-2 cloudless 2023, which the licence list doesn't record at all.
- The LGND service has unknown terms, so every LGND run is "check before sharing", and the label stops meaning anything.

An analyst who presents a run to a government can end up showing imagery that ADB may not use. The benchmark rules out non-commercial and academic-only data in ADB's outputs (Table 1; §7.4; §7.5, where Maxar Open Data is listed as not usable for ADB datasets) **[ext]**. It also asks that every evaluation record whether its sources permit presentation to governments and third parties (§4.2, requirement 6) **[ext]**.

## Users
- **Primary:** whoever operates the deployment for ADB (Clay, or ADB staff), and ADB analysts who present its results.
- **Secondary:** the team, which keeps the open default for research.

## Goals
- One setting makes a deployment ADB-ready. Only licence-cleared sources are used, shown or counted, and a run that isn't cleared can't leave the console as a shareable output.
- With the setting off, behaviour is exactly as today.

## Non-goals
- **Per-run waivers** or "I accept the risk" overrides.
- **Legal judgement:** the profile enforces the licence table. Clearing a source means adding a sourced fact to that table.
- **Removing Vantor from the open default.** That decision belongs to the visual-check spec's open question.
- **Gating the agent's own tools during a run.** The agent's LGND and RODA data are what is being evaluated; the gate applies to outputs.
- **Watermarking or redacting images.**

## User stories
- As a deployment operator, I want one switch that makes the console ADB-safe, so that I don't audit sources by hand.
- As an ADB analyst, I want an output I can't share to be blocked, with the reason, so that I never present it by mistake.
- As the team, I want the open default unchanged, so that research runs keep their sharpest imagery.

## Acceptance criteria
- [ ] **AC1 Switch.** `profile: adb | open` is read from `harness.yaml` or `harness.local.yaml` (default `open`). The profile in force is recorded in each run's `run.json` snapshot at plan time and in each judgement. The console header shows "ADB profile" when it's on. An unknown value fails config load, naming the field.
- [ ] **AC2 Cleared licences.** A source is **cleared** when its licence-table entry has `presentable: true`. An item-level licence (OAM's `license` field, or a visual record's `licence`) is cleared when it matches one of CC BY (any version, including -SA), CC0, public domain, ODbL or the Copernicus Sentinel notice, and contains no NC, ND, non-commercial or academic token. The token rule is the one `analysis/reference.py:23-25` uses. Anything else, including unknown, is not cleared.
- [ ] **AC3 Visual-check sources.** Under `adb`, `vantor` is dropped from `visual_check.sources` whatever the config says, and config load prints one line naming it. An OAM candidate whose licence isn't cleared is skipped and the next candidate is tried, and the skip is recorded in the site's `tried` list. With sources `[vantor, oam, naip, s2]`, a Spokane point that resolved to Vantor under `open` resolves to NAIP or Sentinel-2.
- [ ] **AC4 Archived verdicts.** Under `adb`, a visual record whose licence isn't cleared, such as one made earlier on Vantor, is excluded from `visual_confirmation`. The site shows "Excluded by ADB profile (CC BY-NC 4.0)", and `GET /api/runs/{id}/visual/{site_id}.jpg` returns 451 with that reason. Switching back to `open` restores both. The archive isn't modified.
- [ ] **AC5 Basemaps.** EOX Sentinel-2 cloudless 2023 is added to the licence table, with its licence and source. Under `adb`, the console offers only cleared base layers (OSM, USGS imagery, NAIP), and `/tiles/base/s2/...` returns 451.
- [ ] **AC6 References.** Under `adb`, the reference loader also refuses a set whose `area_licence` isn't cleared, in addition to the refusals it already makes. A fixture set with licence name "PCRAFI exposure (non-commercial)" is refused in both profiles.
- [ ] **AC7 The gate.** Under `adb`, a run is **cleared** only when `licences.for_run(...).presentable` is true after AC4's exclusions. For a run that isn't cleared:
  - the run view shows a red "Not cleared for ADB" banner listing `blockers`, in place of the amber note;
  - "Open static report" and "Export evidence JSON" are disabled;
  - `/reports/{id}` and the export endpoint return 409 with the blockers;
  - `harness replay` still writes the report, but prints the blockers and writes `out/<id>/NOT-CLEARED.txt` beside it;
  - `harness compare` leaves the run out of concept and transfer aggregates and lists it under "Not cleared".
- [ ] **AC8 Open unchanged.** With `profile: open` or no key, every existing test passes unchanged, and a sample run's view, report and compare output are byte-identical to before the change.
- [ ] **AC9 Live proof.** With `profile: adb` set in `harness.local.yaml`, a new Pecos solar run is checked on NAIP and has no Vantor or EOX entries. It is blocked by "LGND Geo service" alone, until LGND's terms are recorded. The handoff shows the banner.

## Success signals
- **Metric (non-cleared exposure):** under `adb`, over every archived run:
  - numerator: outputs served (report, export, image, tile) that contain a non-cleared source;
  - denominator: outputs served;
  - target: 0%. It is measured with the browser probe and an endpoint sweep at verification.
- **Metric (open-mode regressions):** tests changed to pass under `open`. The target is 0.

## Constraints
- Vantor Open Data is CC BY-NC 4.0 (`s3://vantor-opendata/LICENSE.TXT`; see `docs/visual-check/spec.md`, Constraints). The report treats Maxar Open Data as not usable for ADB datasets (§7.5, Table 17) **[ext]**.
- The PCRAFI and Pacific Data Hub layers carry non-commercial terms, which await a ruling from ADB legal (§7.4, Table 16) **[ext]**.
- EOX's Sentinel-2 cloudless releases after 2016 are published under CC BY-NC-SA 4.0 (s2maps.eu). The exact terms for the 2023 layer are to be confirmed in Design.
- OpenAerialMap items carry their own licences (Appendix references) **[ext]**; see also `docs/visual-check/spec.md`.
- LGND Geo has no public terms (`analysis/licences.py:63`).

## What exists today
- Licence facts are in a sourced table: `Source.commercial_use_ok`, `presentable` and `fact_source` (`analysis/licences.py:20-95`). LGND is recorded as unknown (`:55-64`).
- `for_run` lists data, service, boundary, model, visual and reference items. It returns `presentable` and `blockers` (`analysis/licences.py:201-294`, blockers at `:293-294`).
- Visual sources take their licence from each record. An NC licence gives `commercial_use_ok: false` and presentable unknown (`analysis/licences.py:144-184`, `_commercial` at `:159-166`).
- The visual check uses `sources: [vantor, oam, naip, s2]`, with Vantor first (`harness.yaml:67-73`; `harness/sharp.py:32, 265-297`). OAM keeps each item's `license` (`harness/sharp.py:185-202`).
- The reference loader refuses `commercial_use_ok` other than true, and NC, ND or academic tokens (`analysis/reference.py:23-25, 87-92`).
- The console shows an amber note when `presentable === false` and a licence panel (`frontend/src/Evaluation.tsx:127-129, 531-555`). Exports are always enabled (`frontend/src/Evaluation.tsx:623-640`). Archived visual images are served at `harness/web/app.py:542-546`.
- The default basemap is EOX s2cloudless 2023 (`frontend/src/Map.tsx:122-125, 182-184`; `harness/imagery.py:61-62`). It isn't in the licence table.
- `harness.local.yaml` overrides `harness.yaml` (`harness/config.py:61-62`).

## Assumptions and open questions
- Assumption: "presentable" follows "commercial use OK", as `analysis/licences.py:181` already does. ADB legal may draw the line elsewhere; the table is where that's changed.
- **Open (blocking for a usable ADB deployment):** LGND Geo's terms of service. Until they're recorded, every LGND run is blocked under `adb` — owner: user, ask Clay/LGND; default: blocked.
- Open: should HTTP 451 or 403 signal a licence block? — owner: team; default: 451 (unavailable for legal reasons).
- Open: should the profile also set `visual_check.models` or judges? — owner: team; default: no, because Bedrock models are covered by the AWS Service Terms (`analysis/licences.py:85-94`).
