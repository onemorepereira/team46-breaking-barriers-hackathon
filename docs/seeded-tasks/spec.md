# Seeded Tasks and the Seed-Budget Curve — Spec

**Roadmap:** R3 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none to build. The curve needs a complete reference (Pecos today; R1 or R2 for ADB places). R4 adds recall@k to it.
**Size:** M (about 3 days)

## Problem
Our T1 tasks give the agent only a concept name. On LGND's Sentinel-2 index that fails: the index refuses text search and asks for a `like` example. The 2026-11-05 `adb-t1-v1` runs for Gifu warehouses (`5e9c2e11`, score 51.9) and Kathmandu substations (`5f830bdc`, score 38.3) found nothing there **[team]**. The benchmark's workflows are built "from a handful of examples": few-shot search and concept vectors (§1, Table 9) **[ext]**. Its cost measure is how many labels a workflow needs to reach a score (Table 7, labelling cost). For example, Clay needed roughly 120 labels to come within 5% of its top warehouse result (Appendix B) **[ext]**. We can't run an agent the way the benchmark runs a workflow, and we can't say how much an agent gains from each example it is given.

## Users
- **Evaluators** comparing agents with the benchmark's workflows (primary).
- **LGND/Ode,** who report labelling cost per workflow and want the agent's equivalent.

## Goals
- A task can give the agent 1 to 3 example locations. The run records exactly which ones it got.
- For one task, a suite produces recall against the number of seeds (0, 1, 2, 3), with spread across draws.

## Non-goals
- **Pre-resolving seeds to LGND node ids.** The agent gets lat/lon and must turn them into nodes itself (`search_chip_lat_lon`, then `like`). That is part of what we evaluate **[team]**.
- **Negative examples,** and more than 3 seeds (the labelling-cost range up to 1,000 labels is the workflow's, R5).
- **Changing the rubric.** Seeds don't change how the judges score.
- **Choosing seeds by hand for places without a reference.** That's allowed, but those seeds are recorded as `source: hand`, and the curve needs a reference.

## User stories
- As an evaluator, I want to give the Gifu warehouse task two known warehouses so that the agent can search the Sentinel-2 index by example.
- As an evaluator, I want recall at 0, 1, 2 and 3 seeds so that I can say how many examples the agent needs, in the benchmark's labelling-cost terms.

## Acceptance criteria
- [ ] **AC1 Seeds in a suite entry.** A `prompts` entry may carry `seeds`, in one of two forms:
  - a list of 1 to 3 `{lat, lon, note?}` (fixed seeds, `source: hand`);
  - or `{from: <reference id>, n: [0,1,2,3], draws: 3, rng: 46}` (seeds drawn from the reference's assets).

  Suite validation (harness/cli.py:231-247) refuses more than 3 seeds, a `from` reference that doesn't load, and an `n` above the reference's asset count. Old entries run unchanged.
- [ ] **AC2 Draws.** A drawn entry expands into one run per (n, draw). n = 0 runs once, with no draws. Draw d for n picks n assets without replacement, using a random generator seeded with `rng`, the entry's file name, n and d. The same suite file always gives the same seeds. The point of a polygon asset is its representative point inside the polygon. The run-count and cost guards (harness/cli.py:249-265) count expanded runs, so `n: [0,1,2,3], draws: 3` is 10 runs.
- [ ] **AC3 What the agent sees.** The seeds are appended to the prompt after a blank line, as "Known examples of this asset type: (lat, lon), …" with 5 decimals, in a fixed order. The appended text is part of the stored prompt and its `prompt_sha256` (harness/invoke.py:99-106).
- [ ] **AC4 Recorded.** The manifest gains `seeds`: `[{lat, lon, source: hand|reference, ref_id?}]`, the `n`, the `draw`, and the `rng`. `GET /api/runs/{id}` and the run page's summary show "Seeds: n (from <ref id>, draw d)".
- [ ] **AC5 Seed uptake (measured, not scored).** For each seeded run, the report shows `seeds_used`: the seeds whose position falls inside the bbox of a chip the agent fetched with `search_chip_lat_lon`, where that chip's node was later passed as `like` to `search_place_find`. A run that never uses a seed shows "seeds not used".
- [ ] **AC6 Fair recall.** When seeds come from a run's tied reference, the seed assets are removed from the recall numerator and denominator, and the card says "excluding n seed assets". Precision is unchanged.
- [ ] **AC7 The curve.** `harness compare <suite>` adds a **seed-budget table** per (concept, place, model): for each n, the runs, the mean and min–max of seed-adjusted site recall, mean cost (USD) and mean tool calls. It also gives **seeds to 95% of best**: the smallest n whose mean recall is at least 95% of the best mean across n. It is written to `compare.html` and `seeds.csv`.
- [ ] **AC8 Proof.** A suite `suites/adb-t1-seeds-v1.yaml` with the Pecos solar prompt, `seeds: {from: uspvdb-tx-pecos-v4, n: [0,1,2,3], draws: 3, rng: 46}` and Sonnet runs live. The handoff records the table and seed uptake.

## Success signals
- **Metric (seeded searches on example-only indexes):** among seeded runs whose agent searched the LGND `s2` index, numerator = runs with `seeds_used ≥ 1`; denominator = all such runs. Target ≥ 80%.
- **Metric (recall gain):** mean seed-adjusted recall at the best n, minus recall at n = 0, on the AC8 suite. It is reported, with no target. A gap within the min–max spread means "no measurable gain".

## Constraints
- **Cost.** About $0.14–$0.36 per agent run, plus about $0.10–$0.22 for judging (out/5f830bdc…/row.json, out/5e9c2e11…/row.json). So AC8 is about $5. `max_runs_per_suite` is 8 (harness.yaml:85). AC8 needs it raised to 10 in the suite's own run, or set in `harness.local.yaml`, not in the repo default.
- **Report method:** labelling cost is scored over label counts with repeated random draws (Table 7, 5 random seeds **[ext]**). We use 3 draws for cost. Note the report's "seeds" are random-number seeds, while ours are example locations. The table header says so.
- **Seed coordinates come from a reference or a hand pick,** never from OSM (ODbL; references/README.md, Rules).

## What exists today
- Suite entries take `file, concept, place, task, reference, role`, stored as `suite_meta`: harness/cli.py:231-247; harness/invoke.py:110-111.
- The prompt is stored with its sha in the run payload and manifest: harness/invoke.py:99-106.
- The LGND tools include `search_chip_lat_lon` (lat/lon to node) and `search_place_find`: tools/lgnd/descriptors.py:16-17. Their results are parsed into chips with node, bbox and similarity: tools/lgnd/results.py:37-74.
- The located chips of a run: analysis/judging/measure.py:93-117.
- Reference recall over found and missed assets: analysis/reference.py:301-315.
- Per-concept rows in compare: analysis/report.py:197-214.

## Assumptions and open questions
- **Assumption:** lat/lon seeds are enough for the agent to use `like`. If uptake (AC5) is low, a follow-up can pre-resolve nodes, as a separate variant, so the two can be compared.
- **Assumption:** removing seed assets from recall (AC6) is the fair comparison with the benchmark, which scores on assets it didn't train on (Table 7, transfer test **[ext]**).
- **Open:** do seeds go in the prompt text or in a separate harness-provided input? — owner: team; default: the prompt text (AC3), so every backend gets them unchanged.
- **Open:** may seeds for a transfer place come from the home place (Nagoya seeds for Gifu)? — owner: team, with LGND; default: yes, as a separate entry with `seeds.from` naming the home reference. That run is a transfer test, recorded with `role: transfer`.
