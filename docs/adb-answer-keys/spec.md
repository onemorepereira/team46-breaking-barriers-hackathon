# Answer Keys for ADB's Test Places — Spec

**Roadmap:** R1 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none
**Size:** M (about 3–4 days; most of it the PLATEAU extraction)
**Background:** [what the LGND/Ode inception report means for Track 1](../adb-alignment/lgnd-ode-brief.md)

## Problem
Recall can be measured for one place only: Pecos County solar, a US training region the benchmark never tests in. The six other entries in the ADB T1 suite (Nagoya and Gifu warehouses, Nagoya tanks, Manila bridges, Kathmandu substations, Jodhpur solar) have no answer key. Their runs get a judged score but no recall, precision or count ratio, so nobody can tell whether a 52/100 Gifu run found half the warehouses or none. The cross-city transfer gap (Nagoya → Gifu), which the benchmark treats as a headline result, can't be computed for any agent run. The report says recall is defined only against a complete reference (§7.2.1) and names complete sources for some of these places (Table 14, Table 18) **[ext]**. None of them is in the repo.

## Users
- **Evaluators** running `suites/adb-t1-v1.yaml` (primary): they need recall and transfer gap per concept.
- **LGND/Ode benchmark team:** they want agent numbers in their units beside their workflow numbers (Appendix B, Table 19) **[ext]**.
- **ADB reviewers,** who need every reference source's licence on record (Table 1, reference data rules) **[ext]**.

## Goals
- Warehouse runs in Nagoya and Gifu are scored against a complete, licence-clean answer key, so the warehouse transfer gap appears in `harness compare`.
- Every candidate answer key the report names has a recorded status: shipped, or blocked with its reason, owner and next step.

## Non-goals
- **Shipping the DPWH (Manila bridges) or PCRAFI (Port Vila) sets** while their licences are unresolved. The report says DPWH has no formal licence and the PCRAFI layers are non-commercial (§7.4, Table 16) **[ext]**. The loader already refuses both (analysis/reference.py:87-92). We record them as blocked and don't build them **[team]**.
- **Fuel tanks, substations and Jodhpur solar.** No complete open register exists. They need hand-labelled blocks (R2) or LGND's own labels.
- **Adding Port Vila to the suite.** It has no prompt yet, and its only complete source is PCRAFI.
- **Changing the matching rule, the grid or the metrics** (R4 adds ranking metrics).
- **Matching LGND's exact grid origin.** That is still an open request to LGND (docs/adb-alignment/handoff.md, Follow-ups).

## User stories
- As an evaluator, I want the Gifu warehouse run scored against Gifu's register so that I can see what share of its warehouses the agent found.
- As an evaluator, I want the Nagoya → Gifu transfer gap for an agent so that I can compare it with the benchmark's finding that transfer roughly halves recall (Appendix B) **[ext]**.
- As an ADB reviewer, I want each blocked source listed with its licence problem so that I know what permission would unlock it.

## Acceptance criteria
- [ ] **AC1 PLATEAU builder.** `uv run harness reference build-plateau --city <nagoya|gifu> --id <id>` writes `references/<id>/` (reference.json, features.geojson, BUILD.md) from the city's PLATEAU building data. It keeps buildings in the register's warehouse use class with a footprint of at least 1,600 m² (Appendix B **[ext]**). Each feature is the building's footprint Polygon, with `ref_id` set to the PLATEAU building id, plus its use code and footprint area. The download is cached outside the repo (`out/cache/plateau/`), so a second build makes no network call. `ref_mod.load` validates the result, as `build_uspvdb` does (harness/reference.py:194).
- [ ] **AC2 Two shipped sets.** `references/plateau-nagoya-warehouse-v1/` and `references/plateau-gifu-warehouse-v1/` exist. Each has `completeness: complete` and a `completeness_note` naming the use class, the 1,600 m² threshold and the PLATEAU edition, plus `licence.commercial_use_ok: true` with the licence URL. The area is the city boundary from a non-share-alike source, recorded in `area_source` and `area_licence`. The asset counts are within ±5% of the report's 403 (Nagoya) and 63 (Gifu) (Appendix B **[ext]**), or BUILD.md explains the difference.
- [ ] **AC3 Tied in the suite.** In `suites/adb-t1-v1.yaml`, the `nagoya-warehouses.md` entry gains `reference: plateau-nagoya-warehouse-v1` and the `gifu-warehouses.md` entry gains `reference: plateau-gifu-warehouse-v1`. When the suite file is checked (harness/cli.py:242-247), both load without error. The other five entries are unchanged.
- [ ] **AC4 Retro-tie.** Given archived run `5e9c2e11` (Gifu warehouses, 2026-11-05), when `harness reference tie 5e9c2e11-8e6f-43af-bdc6-0a108258bb47 plateau-gifu-warehouse-v1` runs, the run page's "Against the reference" card shows site recall and count ratio, and cell precision unless no claim falls in the area. `GET /api/runs/{id}` returns them under `reference`. The handoff records the numbers.
- [ ] **AC5 Transfer gap.** Given a suite run with one Nagoya and one Gifu warehouse run on the same model, `harness compare <suite>` shows a warehouse transfer row with `site_recall` home minus transfer (analysis/report.py:217-240) that is not null.
- [ ] **AC6 Blocked candidates recorded.** `references/README.md` gains a "Candidates" table. It lists PLATEAU Nagoya and Gifu (shipped); DPWH Metro Manila bridges (blocked: no formal licence; 303 bridges, national roads only, tollways absent, per Table 14 **[ext]**); and PCRAFI Port Vila storage and industrial buildings (blocked: non-commercial; needs ADB legal, per Table 16 **[ext]**). Each row has the source, completeness class, licence status, owner and the date it was checked.
- [ ] **AC7 Tests.** The builder has a test on fixture bytes: three buildings, one below 1,600 m² and one outside the use class, so exactly one feature is kept. A second test checks that a set built with `commercial_use_ok: false` is refused by `harness reference tie`.

## Success signals
- **Metric (warehouse runs with recall):** numerator = warehouse runs in the suite archive, made after this ships, with a non-null `site_recall`; denominator = all warehouse runs made after this ships. Target 100%.
- **Metric (answer-key coverage of the suite):** numerator = `adb-t1-v1` entries with a `reference`; denominator = the 7 entries. It goes from 1/7 to 3/7. The remaining four are R2's or blocked.

## Constraints
- **Licences.** The loader refuses NC, ND and academic-only sets (analysis/reference.py:22-25, 87-92). Share-alike data is barred from the repo (references/README.md, Rules), so OSM can't supply the city boundary. PLATEAU data is published by MLIT under terms it describes as compatible with CC BY 4.0 (PLATEAU site policy, mlit.go.jp/plateau). Design confirms the exact terms for each city's edition before shipping.
- **Report rules:** record the completeness class and licence of every reference (Table 1, Table 7 **[ext]**). Recall only on complete data (§7.2.1 **[ext]**).
- **Size.** Nagoya's PLATEAU CityGML is multi-gigabyte (docs/adb-alignment/design.md:220). Only the extracted features go in the repo. Target: under 2 MB per `features.geojson`.
- **Scoring cost.** The Nagoya city area is about 326 km², or about 13,000 cells, so scoring stays under the 0.2 s seen on Pecos (docs/adb-alignment/handoff.md, AC2).

## What exists today
- The reference format, loader and licence filter: analysis/reference.py:75-120.
- Matching and metrics (160 m cells, any-touch, recall only when complete): analysis/reference.py:283-335.
- Ties as snapshots in the run's archive: harness/reference.py:48-63. Suite ties: harness/cli.py:285-286.
- One builder, USPVDB plus TIGER, with a generated BUILD.md: harness/reference.py:107-195. CLI: harness/cli.py:509-533, 587-597.
- One set: references/uspvdb-tx-pecos-v4 (12 facilities, complete).
- Suite entries with `concept`, `place` and `role`, and `reference` only on Pecos: suites/adb-t1-v1.yaml:8-15.
- Per-concept and transfer rows: analysis/report.py:197-240.
- PLATEAU was considered for the first set and deferred for its size and because LGND has a prepared set: docs/adb-alignment/design.md:220.

## Assumptions and open questions
- **Assumption:** the report's warehouse key is PLATEAU's use class plus a footprint of at least 1,600 m². If LGND used floor area instead, our counts differ and AC2's ±5% check catches it.
- **Assumption:** a run's enforced area (OSM) and the reference area (city boundary) differ only at the edges. Claims in the slivers count as outside the area, as they do today.
- **Open:** which PLATEAU use code and edition did LGND use? — owner: Miguel (asks LGND); default: the latest edition with the use attribute filled, and the transport-and-warehouse use code.
- **Open:** will LGND hand over its prepared Nagoya warehouse set instead? — owner: Miguel; default: build our own. If theirs arrives, it ships as `-v2` beside ours.
- **Open:** which city-boundary source? — owner: team; default: MLIT National Land Numerical Information N03, if its terms allow commercial use; otherwise the PLATEAU dataset's own city extent.
- **Open (blocking for DPWH/PCRAFI only):** written permission from DPWH and an ADB legal ruling on PCRAFI — owner: ADB legal, via Clay; default: both stay blocked.
