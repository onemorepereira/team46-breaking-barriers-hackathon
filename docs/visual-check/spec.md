# Visual check of reported sites — Spec

**Track:** Standard   **Product stage:** Introduction
**Status:** Built   **Last updated:** 2026-11-05

## Problem
Nothing in an evaluation looks at the place a run reports. The judges read the trace and the answer; the measured criteria check that cited values match tool text and that coordinates fall inside the area. So a run can score 100 while its "sites" show something else: run `195ff1d6` ("solar panels within DFW airport") scored 100, and an image of its first search hit is a runway blast pad. Clay's reviewers asked for sharper imagery (Maxar/Vantor, OpenAerialMap) to make evaluations more accurate. Evaluations are worldwide (runs so far: Texas, Tokyo, Nagoya, Laos, Jodhpur), so the fix can't rely on US-only imagery.

## Users
- **Evaluators and reviewers** in the Team Foundry console (primary): they read a run's score and need to know whether the reported sites are real.
- **Clay / ADB** reading reports: they need to see what was and wasn't visually confirmed, at what resolution.

## Goals
- Each reported site is looked at, in the sharpest open image available for that place, by a vision model, and the verdict counts toward the score.
- Reviewers see the image that was checked, its source, resolution and date, and the verdict; a 10 m check is labelled as such.

## Non-goals
- Giving the agent new imagery tools during search (a follow-up: the source lookup is built as its own module so a search tool can reuse it).
- Showing visual verdicts to the judge panel (they'd double-count with the new criterion).
- Commercial imagery (Vantor paid archive, Planet): the sandbox is public data only (docs/Clay-Foundry-Technical-Hackathon.md).
- Checking LGND search hits that the answer didn't report (search footprint stays unscored).
- Multiple votes per site; one archived verdict per site, reused on re-judging.
- The older `maxar-opendata` bucket (different layout; events before 2026).

## User stories
- As a reviewer, I want to see each reported site in the sharpest image available, with a verdict, so I can trust or reject the run without opening another tool.
- As an evaluator, I want a run that reports sites that aren't there to lose score.
- As a reviewer outside the US, I want checks that work worldwide, and to be told when the only image is too coarse to tell.

## Acceptance criteria
- [ ] **AC1 Sites.** Given a judged run, the reported sites are its coordinate claims (the map's numbered sites), de-duplicated by position, first `max_sites` (default 12). A site whose position matches a located LGND chip (same lat/lon to 4 decimals, or the claim cites the chip's node id) uses that chip's footprint and observed date; otherwise a square footprint of `window_m` (default 250 m) centred on the point.
- [ ] **AC2 Image source.** For each site, the image is taken from the first source in `sources` (default `[vantor, oam, naip, s2]`) that has an image covering the footprint centre and reads successfully:
  - `vantor`: an item in the Vantor Open Data STAC catalogue (`s3://vantor-opendata/events/catalog.json`) whose footprint covers the point; its `visual` COG.
  - `oam`: an OpenAerialMap image (`api.openaerialmap.org/meta`) whose footprint covers the point; its licence is the item's `license` field, or CC BY 4.0 (OAM's terms) when absent.
  - `naip`: the most recent NAIP image covering the point (Planetary Computer STAC).
  - `s2`: when the matched chip is a Sentinel-2 chip, the scene of its observed date; otherwise (no chip, a NAIP chip, or no scene that day) the least cloudy scene (< 20% cloud) of the last 90 days.
  - none: the site is recorded `no_image`.
  Each record names the source, its ground resolution (m), the image date, and its licence.
- [ ] **AC3 Checker.** The checker is the first model in `models` (default `[opus, kimi, grok]`) whose family differs from the agent's (the panel's recusal rule). It's shown the image, the run's request, and the site's claim text, and replies `present`, `absent` or `unclear` plus one sentence. A reply that doesn't parse is retried once; a second failure, or a call error, records the site `error`. If no listed model is eligible, the whole check is recorded `not_checked` with that reason and the criterion is N/A.
- [ ] **AC4 Archive.** `runs/<id>/visual.json` holds per site: number, claim, lat/lon, footprint, source, resolution, image date, licence, verdict, reason, model id, token usage, cost; plus totals. The checked image is archived at `runs/<id>/visual/<site_id>.jpg`, where `site_id` = the first 12 hex characters of sha256 of "lat,lon" rounded to 4 decimals.
- [ ] **AC5 Scored.** A measured criterion `visual_confirmation` (output dimension) scores `present / (present + absent)`, value shown as "x/y". It is N/A when no site is `present` or `absent`, or when `visual.json` is missing. Judgements made before this change keep their own rubric snapshot, so their scores never change.
- [ ] **AC6 Stable and offline.** Re-judging a run reuses every site already recorded `present`, `absent`, `unclear` or `no_image` without new model or imagery calls; only `error` and `not_checked` sites (or a missing file / run-level error) are checked again. Replay and rescore read only the archive.
- [ ] **AC7 Wall time.** The check runs concurrently with the judge panel. It stops at `deadline_s` (default 60 s) after it starts; sites unfinished then are recorded `not_checked`. Judging waits for the check at most `deadline_s` plus the time to archive its results; nothing is written to the archive after the check returns.
- [ ] **AC8 Shown.** In the run view, each reported site shows its verdict, the checked image, and a line naming source, resolution and date. A check on an image coarser than 2 m is labelled "{gsd} m image: only large assets are visible", with gsd taken from the record and rounded to a whole metre. A `no_image` site says "No open image of this site to check". The map caption reflects the check: "Visually checked: x of y sites seen" instead of "Context map is not independent verification" when a check exists.
- [ ] **AC9 Licences.** The licence table gains Vantor Open Data (CC BY-NC 4.0) and OpenAerialMap (CC BY 4.0); a run's licence list includes each source its checks used.
- [ ] **AC10 Config.** `visual_check` in harness.yaml: `enabled` (on in the repo's harness.yaml; off when the block is absent, so a config without it never reaches imagery services or Bedrock), `sources`, `models`, `max_sites`, `window_m`, `deadline_s`. Disabled: no new checks or calls. The criterion reads the run's archived `visual.json` whenever it's scored. So a v3 judgement made while the check was disabled, or before it finished, picks up verdicts that a later enabled re-judge archives. That's the same as `condition_compliance` (decided by the user on 2026-11-05: scores follow the run's latest verdicts).
- [ ] **AC11 Live proof.** On real runs: a DFW site is checked on NAIP, a Jodhpur site on Sentinel-2, a point in the Spokane Aug-2026 event on Vantor, and a point in Dar es Salaam on OpenAerialMap; each image is visibly the place.

## Success signals
- **Metric (absent-site score drop):** over the runs in the console archive on 2026-11-05 that the check gives ≥1 `absent` site:
  - numerator: the runs whose total, rescored from the same panel passes with and without `visual_confirmation`, is lower with it (this isolates the check from fresh panel noise);
  - denominator: all such runs;
  - target: 100%.

  It's measured once, at verification, over every judged run in the local archive: the check runs on each, then `panel.rescore` runs on the stored judgement with its v2 snapshot and again with the v3 rubric (results in the handoff).
- Reviewers stop needing an outside map to sanity-check a run (qualitative, from the team).

## Constraints
- Bedrock Converse image blocks: JPEG/PNG/GIF/WEBP, per-image size and dimension limits (source: Bedrock `ImageBlock` docs; checked in Design). DeepSeek and Qwen reject image blocks; Opus, Sonnet, Kimi, Grok and Mistral accept them (probed live 2026-11-05).
- Vantor Open Data is CC BY-NC 4.0 (`s3://vantor-opendata/LICENSE.TXT`): non-commercial use only, attribution required.
- OpenAerialMap imagery is CC BY 4.0 by default, but items can carry their own licence (openaerialmap.org/legal; OSM community thread); each item's own licence is recorded and shown.
- No new runtime dependencies beyond those already allowed (rasterio, pillow, numpy, boto3).

## Assumptions and open questions
- Assumption: a single vote per site is stable enough because it is archived and reused (AC6); if reviewers see wrong verdicts, add votes later.
- Assumption: an image from a different date than the observation is still useful; the record shows both dates so a reviewer can judge new construction.
- Open: Is Vantor's CC BY-NC acceptable for Clay's deployment? — owner: user/Clay; default: on in this sandbox (non-commercial evaluation), removable via `sources`.
- Open: Should `visual_confirmation` cap the score like `condition_cap`? — owner: user; default: no cap, a plain measured criterion.
- Open: Mistral described the DFW blast pad as solar panels in the probe; it is excluded from `models` by default — owner: team; default: excluded.
