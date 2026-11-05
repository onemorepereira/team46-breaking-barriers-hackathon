# Visual check — Launch

## Rollout
- **Mechanism:** config flag `visual_check.enabled`. It's on in the repo's `harness.yaml` and off for any config without the block.
- **Order:** merge, then restart `harness ui` (the console bundle and the backend ship together). There's no migration. The AgentCore agent image doesn't need a redeploy: the check runs where judging runs (the console or the CLI), not in the agent.
- **Compatibility:**
  - judgements made before keep their v2 rubric snapshot and score;
  - a run gets a check the next time it's judged or re-judged;
  - API fields are additive (`map.visual`, `claims[].properties.visual`, a new image route).

## Rollback
Set `visual_check.enabled: false` (no new checks or calls), or revert the PR. Archived `runs/<id>/visual.json` and `visual/*.jpg` files are inert after a revert. v3 judgements made meanwhile keep their stored score, including the criterion. A re-judge after the revert uses the v2 rubric again.

## Observability
- **Per run:** `visual.json` records status, `elapsed_s`, per-site `tried` (which sources answered or failed), verdict, model, and cost.
- **In the judgement:** `visual_cost_usd`, included in `judging_cost_usd`.
- **During live runs:** the trail shows "Visual check: x of y sites seen".
- **Logs:** `visual check failed` (the thread raised), `visual check archive write failed` (store unwritable), and `visual check still writing after its deadline` (backstop).
- **No alerting** (hackathon console). Watch for `not_checked` sites (deadline) and `error` sites (Bedrock) in `visual.json`.

## Communication
- [x] PR description
- [x] Docs: `docs/visual-check/` (spec, design, handoff), the developer guide configuration table, and the factory ledger
- [x] No breaking API change

## Known limitations
- One checker vote per site; a lenient call is possible (DFW site 1, Spokane rows).
- Only coordinate claims written as "lat, lon" are checked.
- Image dates may differ from the asset's dates.
- Vantor imagery is CC BY-NC 4.0: runs checked with it list "check before sharing". Remove `vantor` from `sources` if that matters for a deployment.

## Post-launch checks
- After the first live runs, open each run's map. Badges, caption and checked images should appear, and `visual.json` should have no `error` sites.
- If many sites are `not_checked`, raise `deadline_s` or lower `max_sites`.
- If checks fail outright, turn `enabled` off.
