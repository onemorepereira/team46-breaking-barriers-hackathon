# Hazard Tools for the Agent: Spec

**Roadmap:** H2 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H1](../site-risk-sources/spec.md) (every source a tool reads has a registry entry).
**Size:** about 6 to 8 days

## Problem
To judge whether a place is too risky for an investment, an agent needs values at that place: how deep a 100-year flood would be, how strong a 50-year wind, how often the ground has shaken, and how many people and buildings are exposed. Our agent has two tool servers, RODA (open-data discovery) and LGND Geo (imagery search) (`tools/registry.py`), and neither returns hazard values **[team]**. Asked a site-risk question today, it could only guess, and an evaluator can't check a guess against anything.

## Users
- **Primary:** the agent, answering a site-screening task ([H3](../site-screening-task/spec.md)).
- **Secondary:** the evaluator ([H4](../site-risk-scoring/spec.md)), which checks each number in an answer against the tool output that produced it.

## Goals
- The agent can ask, for a point or an area, the hazard level for each main hazard, and gets back a value, its units and return period, and the source with its version and licence.
- Every result is recorded in the trace like any other tool result, so the existing claim-provenance check ties answer numbers to it.
- The first release covers flood, cyclone wind, earthquake (historical), landslide and exposure, globally, from commercially clean sources.

## Non-goals
- **Computing losses.** Expected annual loss is [H5](../expected-annual-loss/spec.md).
- **Future climate.** Projected values are [H7](../climate-projections/spec.md). The first release returns present-day values only. Aqueduct's baseline counts as present day.
- **Man-made hazards** (dams, plants, industry, conflict). They're [H6](../man-made-exposure/spec.md).
- **Producing hazard layers.** The tools read published layers; they don't model hazards. The report puts layer production out of scope (§2.2) **[ext]**.
- **Earth Engine.** Several sources are on Earth Engine, but commercial use there needs a paid account. The first release reads files we stage ourselves.

## Acceptance criteria
- [ ] **AC1 Server.** A third MCP server, `tools/hazard/`, follows the RODA and LGND pattern (`client.py`, `descriptors.py`, `describe.py`). `tools/registry.py` builds it when `hazard.enabled` is true in `harness.yaml`. A server that fails to start is recorded as unavailable, as LGND is.
- [ ] **AC2 Point query.** `hazard_at(lat, lon, hazards?)` returns one row per hazard. Each row has:
  - `hazard`, `metric`, `value`, `units`;
  - `return_period_years`, where the metric has one;
  - `source_id` (from the H1 registry), `source_version`;
  - `cell_size_m`: the source's resolution;
  - `note`, for example "outside STORM's cyclone basins: no cyclone hazard modelled".
- [ ] **AC3 Area query.** `hazard_in(area_ref | bbox, hazards?)` returns, per hazard, the share of the area above each level (for example the share of cells with 100-year flood depth over 0.5 m) and the maximum. It also returns the area's exposure: population (GHSL or WorldPop) and built-up area (GHSL). It accepts the run's resolved search area.
- [ ] **AC4 First sources.** All are commercially clean in the [catalog](../site-risk-sources/catalog.md):

  | Hazard | Source | Metric |
  |---|---|---|
  | River and coastal flood | WRI Aqueduct Floods v2 (baseline) | Depth, m, at return periods 10, 100 and 1,000 years |
  | Cyclone wind | STORM wind-speed return periods (present) | Wind speed, m/s, at 10, 50 and 100 years |
  | Cyclone history | IBTrACS | Tracks within 100 km since 1980, by category |
  | Earthquake (historical) | USGS ComCat | Events of magnitude 5 or more within 100 km since 1900, and the largest |
  | Landslide | NASA Global Landslide Catalog | Events within 25 km |
  | Exposure | GHSL population and built-up area | Count and area |

  JRC river flood (90 m) is added only once H1 resolves its licence.
- [ ] **AC5 Staging.** `harness hazard-stage <source>` downloads a source, converts rasters to cloud-optimised GeoTIFFs and point data to GeoParquet, records each file's sha256 and the source version, and writes them to the configured `hazard.store_uri` (S3 or a local folder). The tools read only staged files, so results are reproducible. A run records the store version it read.
- [ ] **AC6 Known answers.** Tests use small fixture rasters and points with known values. They cover:
  - a point inside a flood cell;
  - a point at a cell edge;
  - a point at sea;
  - a point outside the cyclone basins;
  - an area that crosses the antimeridian (Fiji);
  - an empty result.
- [ ] **AC7 Live check.** Point queries at five places return the values the source's own viewer shows, within one cell, recorded in the handoff: Manila, Dhaka, Port Vila, Kathmandu and Houston.
- [ ] **AC8 Traced.** A run that calls the hazard tools archives each result as a tool span. `analysis/provenance.py` matches an answer's hazard numbers to those results, as it does for coordinates today.
- [ ] **AC9 Licences.** Each result carries its `source_id`, and the run's licence list (H1 AC4) includes it.
- [ ] **AC10 Speed.** A point query over every first-release hazard answers within 3 s from the S3 store, measured on the five AC7 places.

## Success signals
- **Metric (grounded numbers):**
  - **numerator:** hazard values in site-risk answers that match a hazard tool result;
  - **denominator:** all hazard values in those answers;
  - **target:** 95% or more.
- **Metric (coverage):** the share of the [H8](../site-risk-validation/spec.md) places where every first-release hazard returns a value or an explicit "not modelled here" note. **Target:** 100%.

## Constraints
- **Licences:** only `public_domain`, `cc0` and `cc_by` sources in the first release. Share-alike sources may be staged privately but not published (`references/README.md`).
- **Agent image:** the tools run in the AgentCore image. Rasterio is already there (PR #32). Store reads go through the agent's IAM role, scoped to the hazard bucket (the AWS hardening pattern).
- **Cost:** staging the first sources is about tens of gigabytes. Aqueduct and STORM are global grids at about 1 km and 10 km. The exact size is recorded at staging.

## What exists today
- **Tool servers:** `tools/registry.py` builds RODA and LGND as MCP servers, each with `client.py`, `descriptors.py` and `describe.py`.
- **Windowed raster reads** with an allow-list: `harness/visual.py` (the visual check).
- **Claim provenance:** `analysis/provenance.py` ties answer values to tool results.
- **Search areas:** `harness/area.py` resolves the run's area.

## Assumptions and open questions
- **Open:** how should earthquake hazard be given outside the US? No commercially clean global hazard map exists. GEM's map is CC BY-NC-SA ([catalog](../site-risk-sources/catalog.md#earthquake-landslide-volcano-and-tsunami)). *Owner:* Miguel, who asks ADB whether it holds a GEM commercial licence. *Default:* historical seismicity only, with a note that it is not a hazard probability.
- **Open:** inside the US, is USGS's national seismic hazard model usable for return-period shaking? *Owner:* team, who checks its licence. *Default:* not used until checked.
- **Assumption:** about 1 km (Aqueduct) is fine for screening an area, not for siting a building. The tool returns `cell_size_m` so the answer can say so.
