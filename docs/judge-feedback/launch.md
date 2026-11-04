# Human Feedback for the Judges: Launch

## Rollout
- **Mechanism:** on by default through `harness.yaml`: `judging.guidance: true` and `judging.reconsider: true`. Nothing is deployed. Reviews, reconsideration and guidance run in the console (`harness ui`) and the CLI on the operator's machine. The AgentCore runtime is unchanged.
- **Order:** merge, then restart the console. No migration is needed:
  - old judgements have no `revision` and no `guidance` keys, and read as before;
  - a deployment starts with no reviews and no guidance.
- **Compatibility:** every record carries `schema_version: 1`, and readers ignore keys they don't know.

## Rollback
- **Switch it off without a code change:** set `judging.reconsider: false` and/or `judging.guidance: false` in `harness.local.yaml`, then restart the console. Alternatively, switch guidance off on the Guidance page (`POST /api/guidance/off`), which keeps the history.
- **Bad guidance:** approve the previous version on the Guidance page, which is a rollback.
- **Revert the commits:** `feedback/` objects in the archive become unused files. A revised run keeps its revised `judgement.json`, and its original is in `runs/<id>/judgements/`. To restore originals after a revert:

  ```sh
  # for each revised run: copy runs/<id>/judgements/<revision.previous>.json back over runs/<id>/judgement.json
  ```

  This is the one step that isn't automatic (design, "One-way doors").

## Observability
- **Agreement with reviewers:** the Guidance page, or `harness agreement --human`. Krippendorff's α and the mean absolute difference, by guidance version. These are the spec's success signals.
- **Resistance to wrong reviews:** `harness calibrate <run> --feedback`. Re-run it after any change to `prompts/judge/reconsider.md`.
- **Guidance actually applied:** every judgement records `guidance.version`, and the run page shows it. A judgement with `guidance_error` (the archive was unreadable) is shown as a warning.
- **Cost:** reconsideration ≈ one panel pass ($0.10–0.31); evaluation is estimated before it starts.

## Communication
- [x] PR description
- [x] Judging guide: "Human feedback: reviews, reconsideration and guidance"
- [x] Developer guide: CLI, config keys, archive files
- [x] API reference (`/api/docs`, tags Feedback and Guidance)

## Known limitations
- **Reviewer identity is a typed name.** There's no sign-in, which suits a local operator console. A shared deployment needs one.
- **Evaluation needs about 15 reviewed runs.** A third are held out, and at least 5 held-out runs are needed. Until then, approving guidance needs a stated reason.
- **No concurrent-write protection.** Writes are last-writer-wins: don't run `harness judge` on a run the console is judging, and don't approve from two places at once.
- **The sycophancy checks take one sample per check, with no control.** A fail should be re-run once before acting on it.

## Post-launch checks
- After the first 5 reviews: `harness agreement --human` reports a number.
- After the first approved version: judge one run and check its page shows the guidance version, then re-run `harness calibrate <run>` with guidance active (it still passes).
- **Signs that mean rolling back the guidance:**
  - calibration fails with it;
  - agreement with reviewers drops in the next evaluation.
