# Transfer Intervals — Spec

**Roadmap:** R7 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none to ship; recall intervals in transfer places need R1 (ADB answer keys) · **Size:** S–M (about 3 days, plus one 20-run suite, about $11)
**Background:** [ADB alignment handoff](../adb-alignment/handoff.md) (AC8, AC9)

## Problem
A transfer gap is the drop in a workflow's score when it moves to a new place. ADB uses it to judge whether a workflow can be reused, but ours come from one run per side, so nobody can tell a real drop from noise. Suite `adb-t1-v1-20261105T1103` shows a 27.3-point gap for warehouses (Nagoya to Gifu) and 16.0 for solar (Pecos to Jodhpur). Agents vary from run to run, and judges vary from pass to pass, so either figure could shrink or double on a rerun. An analyst who acts on the 27.3 might drop a workflow that transfers fine, or keep one that doesn't. The benchmark names small samples as a risk and answers it by reporting intervals (§3.2, Table 4) **[ext]**. It also separates transfer to a nearby city in the same country from transfer across countries (§5.6, Table 10) **[ext]**. Our output mixes both kinds under one concept row and doesn't say which is which.

## Users
- **Primary:** ADB analysts and the LGND/Ode benchmark team, comparing an agent's transfer drop with the benchmark's (T5, Table 6) **[ext]**.
- **Secondary:** the team, deciding how many repeats a claim needs.

## Goals
- Every transfer gap comes with a 95% interval and the number of runs behind each side.
- Gaps are reported per pair of places, labelled by transfer level: same city, same country, or across countries.
- An interval that includes zero is called out, so a drop that might be noise isn't read as a real drop.

## Non-goals
- **Separating agent variance from judge variance:** the judge panel already runs 3 passes (`harness.yaml:60`). Splitting the two is a later study.
- **Significance tests other than the bootstrap**, and corrections for multiple comparisons.
- **Within-city test blocks.** The level is supported, but it needs labelled blocks (R2).
- **Before/after-event and coastal/inland transfer** (Table 7 variants) **[ext]**.
- **Raising committed suite limits by default** (see the open questions).

## User stories
- As an ADB analyst, I want an interval on each transfer gap, so that I know whether the drop is real.
- As the benchmark team, I want gaps labelled by transfer level, so that they line up with Table 10.
- As an evaluator, I want to repeat each suite entry n times in one command, so that I can buy precision where it matters.

## Acceptance criteria
- [ ] **AC1 Repeats.** A suite file may set `repeats: n` at the top level (default 1) and per entry (overrides the top level). Runs = Σ over entries (repeats × models). `max_runs_per_suite` and `max_suite_usd` apply to that total, with the existing messages (`harness/cli.py:250-265`). Runs execute repeat-major: every entry once, then every entry again, so a slow afternoon of LGND isn't confounded with one place. Each run's `suite_meta` records `repeat` (1..n).
- [ ] **AC2 Place pairs and level.** A `place` must end in ", XX", a two-letter ISO 3166 country code. Otherwise the suite is refused with "place must end with a country code, e.g. 'Gifu, JP'". `harness compare` makes one transfer row per (concept, model, home place, transfer place), pairing each home place of a concept with each of its transfer places. `level` is derived: `within_city` when the two places are identical, `cross_city` when the country codes match, and `cross_country` otherwise.
- [ ] **AC3 Bootstrap.** For each transfer row and each statistic (`score` and `site_recall`), runs with a null value are dropped. Each side's runs are then resampled with replacement, independently, 2,000 times, using `numpy.random.default_rng(46)`. The statistic is mean(home) − mean(transfer). The interval is the 2.5th and 97.5th percentiles, to 1 decimal for score and 3 for recall. Each side's mean gets its own interval the same way. The interval is computed only when both sides have n ≥ 3; otherwise its columns are empty and `note` says "n<3".
- [ ] **AC4 Output.** `concepts.csv` transfer rows gain `home_place`, `transfer_place`, `level`, `score_gap_lo`, `score_gap_hi`, `score_home_lo`, `score_home_hi`, `score_transfer_lo`, `score_transfer_hi`, `recall_gap_lo`, `recall_gap_hi` and `note`. Existing columns keep their meaning. `compare.html` shows each gap as "27.3 (95% CI 12.1 to 40.8; n = 5 / 5)". When the interval includes 0, it adds "not distinguishable from no drop".
- [ ] **AC5 Backward compatible.** Running `harness compare adb-t1-v1-20261105T1103` after the change gives a warehouse row (Nagoya, JP → Gifu, JP, `cross_city`) with gap 27.3, and a solar row (Pecos County, TX, US → Jodhpur, IN, `cross_country`) with gap 16.0. Both have empty intervals and the note "n<3". Concept rows are unchanged.
- [ ] **AC6 Transfer suite.** `suites/adb-transfer-v1.yaml` holds the 4 home and transfer entries of `suites/adb-t1-v1.yaml` (Nagoya and Gifu warehouses, Pecos and Jodhpur solar), with `repeats: 5`: 20 runs. Pecos stays tied to `uspvdb-tx-pecos-v4`.
- [ ] **AC7 Live proof.** That suite is run once on AgentCore (Sonnet). Its `concepts.csv` has both transfer rows with intervals (n = 5 / 5, or fewer where runs failed, as long as both sides have n ≥ 3). The handoff reports both gaps with intervals, next to the one-run gaps of 27.3 and 16.0.
- [ ] **AC8 Docs.** The developer guide's suite format documents `repeats`, the country-code rule and the transfer columns.

## Success signals
- **Metric (gaps with an interval):** in the first repeated suite:
  - numerator: transfer rows with both `score_gap_lo` and `score_gap_hi`;
  - denominator: all transfer rows;
  - target: 100%.
- **Metric (claims we'd retract):** the share of single-run gaps from `adb-t1-v1-20261105T1103` whose repeated interval includes 0. This one is recorded, not targeted: it tells us how much to trust past one-run numbers.

## Constraints
- Transfer gap is home score minus new-place score with the same workflow (§5.7, Table 11) **[ext]**. Transfer levels follow §5.6, Table 10 **[ext]**. The benchmark's own labelling-cost runs use 5 seeds (Table 7) **[ext]**, so 5 repeats is the default here **[team]**.
- Cost: the 7-run suite cost $2.30 agent plus $1.57 judging (`out/adb-t1-v1-20261105T1103/compare.csv`), about $0.55 a run, so 20 runs ≈ $11. That is under `max_suite_usd: 50` but over `max_runs_per_suite: 8` (`harness.yaml:85-86`).
- The bootstrap needs no new dependency: `numpy` is already one (`pyproject.toml`).

## What exists today
- Suite entries carry `concept`, `place` and `role` (`home` or `transfer`), which is validated (`harness/cli.py:231-247`). They default to `task: T1` (`harness/cli.py:234-235`) and are stored in `suite_meta`. `suites/adb-t1-v1.yaml:8-15` pairs Nagoya with Gifu, and Pecos with Jodhpur.
- Runs = prompts × models, with no repeats. Run order is prompt-major (`harness/cli.py:249, 281-283`).
- `transfer_rows` groups by (concept, model) only. It pools every home and every transfer place, takes plain means and reports the gap with no interval (`analysis/report.py:217-247`; `_mean` at `:172`). Columns are listed at `analysis/report.py:177-194`.
- `concepts.csv` is written by `harness compare` (`harness/cli.py:131`). Its live content has n_home = n_transfer = 1 for both rows (`out/adb-t1-v1-20261105T1103/concepts.csv`).
- The ADB alignment handoff listed "pair transfer gaps by place" as a follow-up (`docs/adb-alignment/handoff.md`, Follow-ups).

## Assumptions and open questions
- Assumption: with 5 runs a side, a percentile bootstrap gives a usable, if rough, interval. With fewer than 3, it's withheld rather than shown misleadingly narrow.
- Assumption: a run is the unit of resampling. Judge passes within a run are already summarised into its score, so they aren't resampled separately.
- Open: raise `max_runs_per_suite` in the committed `harness.yaml`, or run the 20-run suite with a `harness.local.yaml` override? — owner: user; default: local override, committed limit stays 8.
- Open: should repeats be required (n ≥ 3) for any suite with `role` entries? — owner: team; default: no, but compare marks the intervals as missing.
- Open: Pecos is a US place, and the benchmark keeps the US for training only (Appendix A) **[ext]**. Should an ADB-place home replace it? — owner: Clay/LGND; default: keep Pecos, the only place with a reference set, until R1 provides one.
