# T3 Register Audit: Scoring Flagged Records: Spec

**Roadmap:** R11 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** R1 (ADB answer keys, for registers in ADB places), R3 (seeded tasks, for machine-planted errors)
**Size:** about 3 to 4 days, plus one live run (about $0.25)

## Problem
ADB's teams hold asset registers that go out of date. The report's monitoring task, T3, asks which register entries are absent, wrongly placed or stale (Table 6), and the Disaster Risk Analytics Explorer needs data under 3 years old (Table 5) **[ext]**. The harness can only score an inventory (T1) against a reference. It has no dated register, no held-out list of which records are wrong, and no rule for matching a flag to a record. So an agent that flags every record, one that flags none, and one that flags exactly the right ones all look the same, and no T3 result can sit beside the benchmark **[team]**.

## Users
- **Primary:** ADB analysts and the Explorer team, deciding whether a register is still trustworthy and which records go to a person.
- **Secondary:** the LGND/Ode benchmark team, comparing agent and workflow T3 results.

## Goals
- An agent's audit of a dated register is scored, per status, against a held-out truth the agent never sees.
- Matching follows the benchmark: any-touch on 160 m cells for places, and a date match for new builds (Table 7) **[ext]**.
- Results show how much of the register an audit sends to a person.

## Non-goals
- **A rubric change.** T3 metrics sit beside the score, as reference metrics do.
- **New agent tools.** The register reaches the agent in its prompt.
- **Registers over 200 records,** or writing a corrected register.
- **PCRAFI or other ADB-held registers,** until their licence is confirmed.
- **Seeding errors by machine.** That's R3. Here, errors are planted by hand and documented.

## User stories
- As an Explorer analyst, I want to know how many flags are right and how many problems were missed, so I can decide whether an audit replaces a manual review.
- As an ADB analyst, I want a reported new build to count only if the agent saw it after it was built.
- As the benchmark team, I want per-status precision and recall in our units.

## Acceptance criteria
- [ ] **AC1 Format.** A register lives in `registers/<id>/`:
  - **`register.json`** holds `schema_version`, `id`, `concept`, `place`, `area`, `as_of` (an ISO date), `source`, `licence` (the reference-set rule) and `records`. Each record is `{record_id, geometry, recorded_date}`.
  - **`truth.json`** holds `statuses`, one per record: `ok`; `misplaced`, with the true geometry; or `stale`, with a `change_date` and a reason. It also holds `additions`, each `{truth_id, geometry, built_date}`.

  The loader refuses any of these, naming the field:
  - no `as_of`;
  - a record without a date;
  - a duplicate id;
  - a truth entry for an unknown record;
  - more than 200 records;
  - a licence the reference loader refuses.
- [ ] **AC2 Held out.** `harness run --register <id>` appends each record's id, coordinates and recorded date to the task prompt. Before the run starts, it snapshots both files and their sha256 into `runs/<id>/register/`. A test asserts that no truth-only value (a status, `change_date`, `built_date`, or an addition's coordinates) appears in the prompt, manifest or spans.
- [ ] **AC3 Flags.** The T3 task prompt asks for a `flags` list beside `claims` in the answer's JSON block:
  - **misplaced or stale:** `{record_id, status, ref}`, plus an optional corrected `"lat, lon"` for a misplaced record;
  - **missing:** `{status: "missing", value: "lat, lon", observed: "YYYY-MM-DD", ref}`.

  No `flags` key means nothing was flagged. Malformed flags are listed as `unparsed` and never scored.
- [ ] **AC4 Matching.**
  - A misplaced or stale flag is correct when the truth gives its record that status.
  - A correct misplaced flag with a corrected position is also `relocated` if that position shares a 160 m cell with the true geometry, on the reference scorer's grid.
  - A missing flag finds an addition when they share a cell. Each addition counts once.
  - A found addition is `date_matched` when `observed` is on or after its `built_date`.
- [ ] **AC5 Metrics.**
  - **Per status:** precision (correct flags ÷ flags with that status) and recall (truth items found ÷ truth items with that status; `null`, with the reason, when there are none).
  - **Review share:** records flagged ÷ records.
  - **Date-matched recall** for additions.
  - **Refresh due:** records dated more than 3 years before `as_of`, computed by code as information.
- [ ] **AC6 Shown.** The run page and the static report show an "Against the register" card with the metrics and the correct, wrong and missed items. `GET /api/runs/{id}` includes `register`, which is `null` when the run isn't tied. The score is unchanged.
- [ ] **AC7 Replay.** `harness replay <id>` recomputes the metrics from `runs/<id>/register/` alone, with no model or network call. A rebuilt repo register flags `stale_snapshot` and changes nothing.
- [ ] **AC8 Compare.** For runs whose `suite_meta.task` is `T3`, `compare.csv` gains the per-status precision and recall, and the review share.
- [ ] **AC9 First register.** A committed script builds `registers/uspvdb-tx-pecos-2021/` from `references/uspvdb-tx-pecos-v4/`:
  - **records:** the 10 facilities with `p_year` ≤ 2021, `as_of` 2021-12-31;
  - **additions:** the facilities from 2022 and 2024;
  - **planted errors, documented in `BUILD.md`:** 2 records moved 1 to 2 km, and 1 record made stale.

  One live AgentCore run is scored against it, and the handoff records the metrics.

## Success signals
- **Metric (control separation):**
  - **numerator:** shipped registers where a scripted "flag every record" answer scores review share 1.0, with precision equal to the truth's error share, and a "flag nothing" answer scores recall 0 on every status;
  - **denominator:** shipped registers;
  - **target:** 100%.
- **Metric (coverage):** T3 runs with a non-null recall for every status in their truth ÷ T3 runs judged. Target: 100%.

## Constraints
- **Licences:** no non-commercial or academic-only data in ADB outputs (report Table 1, §7.4) **[ext]**. No ODbL or share-alike data in the repo (`references/README.md`). USPVDB's metadata lists no access or use constraints, and it's recorded as `commercial_use_ok: true` (`references/uspvdb-tx-pecos-v4/reference.json`).
- **The refresh rule:** under 3 years (report Table 5) **[ext]**.
- **Prompt budget:** 200 records keeps the register to a few thousand tokens.
- **Offline and replayable,** as reference scoring is (docs/adb-alignment/spec.md).

## What exists today
- **Reference sets** have undated records with no `as_of` (`analysis/reference.py:75-120`). The Pecos features keep `p_year` (`harness/reference.py:135`).
- **The licence rule:** `analysis/reference.py:22-24`, `:86-91`.
- **The grid and any-touch matching:** `analysis/reference.py:154-169`, `:246-249`, `:283-332`.
- **Archive snapshots and replay:** `harness/reference.py:48-71`, `analysis/reference.py:343-392`.
- **The answer's JSON block** has only `claims` (`prompts/agent/system.md:9-19`).
- **Suite metadata** already carries `task` (`harness/invoke.py:110-111`). The compare CSVs are written at `harness/cli.py:130-131`.
- **There's no T3 prompt** in `prompts/tasks/adb/`.

## Assumptions and open questions
- **Assumption:** 200 records fit in a prompt. Larger ADB registers need a register tool, a separate effort.
- **Assumption:** `p_year` is close enough to a build date. If it isn't, additions fall back to location-only matching.
- **Open:** is "stale" the truth's status, or the 3-year rule? *Owner:* Clay/ADB. *Default:* both, reported separately, as above.
- **Open:** may PCRAFI or other ADB registers be used (report Table 3, ADB legal)? *Owner:* Miguel, via LGND. *Default:* no.
- **Open:** does the agent system prompt learn `flags`? *Owner:* team. *Default:* no, only the T3 task prompt, so T1 runs keep a byte-identical system prompt.
- **Open:** what distance makes a record misplaced? *Owner:* LGND. *Default:* sharing no 160 m cell with the true geometry.
