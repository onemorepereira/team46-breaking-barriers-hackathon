# Cost per Dataset — Spec

**Roadmap:** R8 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none to ship; "cost per found asset" needs a tied reference (R1 for ADB places) · **Size:** M (about 5 days)

## Problem
The question ADB is paying to answer is whether an AI workflow builds an asset dataset more cheaply than buying imagery and commissioning detectors (§1) **[ext]**. Our console can't answer it for an agent run, because the only costs it shows are model tokens. Four costs are missing:
- the LGND Geo calls the agent made;
- the compute the run occupied;
- the archive it stores;
- the analyst time spent reviewing it.

There is also no per-asset figure that can be set against a vendor's price. The console says as much: its cost card is token-based and notes that analyst time and imagery aren't measured. The benchmark asks for build effort (labels, analyst review), for the monetary cost of each run (imagery, storage, compute), and treats review effort as its main cost measure (§4.2 requirements 4–5; §5.7) **[ext]**. Without these, an analyst compares $0.55 of tokens with a vendor quote and draws the wrong conclusion.

## Users
- **Primary:** ADB analysts and the LGND/Ode benchmark team, comparing the cost of an agent-built dataset with other routes.
- **Secondary:** reviewers in the Team Foundry console, whose time becomes a recorded cost; and the team, budgeting suites.

## Goals
- Each run has a cost breakdown with every component it used. Each component is priced from a recorded, sourced rate, or explicitly marked as unpriced.
- Production cost (what building the dataset cost) is kept separate from evaluation cost (what judging it cost).
- Analyst review time is captured in the console, without anyone filling in a timesheet.
- Cost per found asset and per visually confirmed site are reported where a denominator exists.

## Non-goals
- **Reconciling with the AWS bill** or Cost Explorer: costs are estimates from recorded rates.
- **Purchased imagery:** the sandbox uses open data only (`docs/Clay-Foundry-Technical-Hackathon.md`). A priced source can be added later through the same table.
- **The benchmark's review-effort curve** (locations inspected to reach 50, 80 or 90% of assets, Table 11) **[ext]**: that is a ranking metric (R4).
- **Time spent reading a run without submitting a review.**
- **Budget enforcement** changes: the suite caps stay token-based (`harness/invoke.py:60-68`).

## User stories
- As an ADB analyst, I want the full cost of producing a dataset, including review, so that I can compare it with buying one.
- As an ADB analyst, I want the cost per found asset, so that I can compare across places and asset classes.
- As a reviewer, I want my review time recorded automatically and shown to me before I submit, so that it is accurate without extra work.

## Acceptance criteria
- [ ] **AC1 Rates.** `harness.yaml` gains a `prices` block, beside `prices_per_mtok`:
  - `agentcore_usd_per_hour`: the runtime's vCPU and memory rates at its deployed size;
  - `s3_usd_per_gb_month`;
  - `lgnd_usd_per_call` (per tool name, or `default`);
  - `imagery_usd_per_image` per visual source (0 for `vantor`, `oam`, `naip` and `s2`);
  - `analyst_usd_per_hour`.

  Each entry has `source` and `read` (a date), as `prices_per_mtok` does. A null rate means unpriced. The run-time rates are snapshotted into `run.json` at plan time, next to `prices_per_mtok` (`harness/invoke.py:108`).
- [ ] **AC2 Components.** A pure function computes a run's cost from its archive, snapshot and reviews. Each component reports `quantity`, `unit`, `rate`, `usd` (null if unpriced) and `basis`:
  - `agent_tokens`: the existing estimate;
  - `lgnd_calls`: successful LGND tool calls, counted per tool;
  - `compute`: `runtime_s` × the AgentCore rate, or `0` with basis "local backend" for `backend: local`;
  - `imagery`: the images the visual check read, per source;
  - `storage`: the bytes under `runs/<id>/`, in USD per month;
  - `review`: the summed `active_seconds` of the run's reviews, × the analyst rate;
  - `evaluation`: `judging_cost_usd`, which already includes the visual check.

  `labels` is reported as a count with no price. It is the number of examples passed in the `examples` argument of `toolbox_classifier_build` calls.
- [ ] **AC3 Totals.** `production_usd` sums the priced components among agent_tokens, lgnd_calls, compute, imagery, storage (one month) and review. `evaluation_usd` equals `evaluation`. `unpriced` lists the production components with a null rate. When `unpriced` isn't empty, totals display as "≥ $x".
- [ ] **AC4 Per asset.** `usd_per_found_asset` = production_usd ÷ the number of `found` reference assets, when a reference is tied and found > 0. `usd_per_seen_site` = production_usd ÷ the visual check's `present` sites, when > 0. Both are null otherwise, and both carry the "≥" marker when `unpriced` isn't empty.
- [ ] **AC5 Review time.** In the console review form, the time the form is open while the tab is visible is counted (the Page Visibility API), capped at 2 hours. Before submit, it's shown as "Time on this review: 6 min", and the reviewer can edit it. `POST /api/runs/{id}/reviews` accepts `active_seconds` (an integer, 0–7,200) and `time_edited` (a bool). The review record stores both. Reviews without them count as 0 seconds, with a basis note "N reviews before time capture".
- [ ] **AC6 Shown.** The run view's "Cost, usage and review effort" card lists each component, the two totals and the per-asset figures. Each unpriced row reads "not priced: no rate recorded". The card's footer note changes from "not measured" to naming the unpriced components. `GET /api/runs/{id}` returns `cost`.
- [ ] **AC7 Compare.** `compare.csv` gains `production_usd`, `evaluation_usd`, `review_s`, `labels`, `usd_per_found_asset` and `unpriced`. `compare.html` shows suite totals for production and evaluation.
- [ ] **AC8 Offline.** Replay reproduces every component from the archive. Changing a rate in `harness.yaml` changes only `storage` and `review` for old runs; the snapshotted run-time rates stay fixed. Runs with no `prices` snapshot report those components as unpriced, with basis "run predates rate snapshot".
- [ ] **AC9 Live proof.** One new AgentCore run, tied to `uspvdb-tx-pecos-v4`, with one console review, shows every component. `lgnd_calls` is listed as unpriced unless the open question below is answered. The breakdown is in the handoff.

## Success signals
- **Metric (review-time capture):** over reviews created in the 2 weeks after release:
  - numerator: reviews with `active_seconds` > 0;
  - denominator: all reviews;
  - target: 100%.
- **Metric (priced share of production cost):** over runs in the next suite, the share of production components that are priced. The target is 100% except `lgnd_calls`, until LGND gives a rate.

## Constraints
- Rates come from public price pages, with the read date recorded: Amazon Bedrock AgentCore Runtime pricing (billed per vCPU and memory over time) and Amazon S3 Standard storage pricing. The convention is the one set by `prices_per_mtok` (`harness.yaml:88-101`).
- LGND publishes no terms or pricing that we've found (`analysis/licences.py:55-64`). Its calls stay unpriced until LGND supplies a rate.
- The open imagery sources charge no fee to read (`analysis/licences.py:144-156` lists them). This is recorded as $0, not left out.
- The benchmark records labels and imagery separately from review effort (§5.7) **[ext]**. We do the same **[team]**.
- No credentials in the repo. Rates are public numbers.

## What exists today
- Agent cost is input and output tokens × the snapshotted `prices_per_mtok` (`analysis/signals.py:52-60`), and runtime is `ended_at − started_at` (`analysis/signals.py:61`).
- Judging cost is tokens × price per call (`harness/judge.py:225-231`). The visual check's new calls are added as `visual_cost_usd` (`harness/judge.py:390-393`, `harness/visual.py:324-333`).
- The console shows agent and judge estimates, runtime, tokens and calls. Its note says analyst time and imagery aren't measured (`frontend/src/Evaluation.tsx:420-449`; data at `harness/web/view.py:264-265`).
- Review records hold `reviewer`, `created_at` and the criteria, but no duration (`harness/feedback.py:111-135`; request model at `harness/web/api_docs.py:181-191`).
- Classifier examples are read from `args.examples` (`tools/lgnd/describe.py:66-68`).
- `compare.csv` has `estimated_cost_usd` and `judging_cost_usd` only (`analysis/report.py:119-125`).

## Assumptions and open questions
- Assumption: visible form time is a fair proxy for review effort. If reviewers work in other tabs (for example an outside map), it undercounts, which is why the time can be edited.
- Assumption: one month of storage is the honest default for a dataset that is kept. Longer retention multiplies a figure that is tiny anyway.
- Open: LGND's per-call or subscription price? — owner: user, ask Clay/LGND; default: unpriced, shown as "≥".
- Open: the analyst hourly rate to use for ADB? — owner: Clay/ADB; default: null, so hours are shown without dollars.
- Open: should cost per found asset count only production cost? — owner: team; default: yes. Evaluation cost is reported separately, because an analyst building a dataset wouldn't pay for our judges.
