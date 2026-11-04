# Plain-language evaluations — local handoff

Aditya / Codex, 2026-11-04. Branch `slice/plain-verdict`, based on main `940d9ff`.

## What changed

- Added `analysis/judging/explain.py`: a deterministic headline, summary of at most 120 words, and one to three review actions.
- Added a **What this means** card above the scores and at the top of the static report. The API's `explanation` field carries the same content, including in the live stream's final event.
- Added optional `plain:` questions to the rubric and displayed them for both new and archived judgements. The current configured rubric supplies display wording; scoring still uses the saved snapshot.
- Counts say **listed locations**, and text matches and judge agreement are explicitly distinguished from factual correctness. No agent, tool, judge prompt, weight, scoring anchor, or infrastructure change.

## Checks actually run

Python 3.13.1 on macOS, with the checked-in lockfile. No AWS credentials, live models, LGND login, or cloud deployment used.

| Acceptance | Evidence | State |
| --- | --- | --- |
| AC1 deterministic explanation | `tests/test_explain.py`: scores, location counts, word cap, real saved image-check shapes, later checks replacing earlier ones | Implemented, offline tests pass |
| AC2 states | High, Medium, no answer, no usable tool data, infrastructure failure, never judged, insufficient judge replies, broken record | Implemented, offline tests pass |
| AC3 plain words | Automated banned-term check; no raw error IDs or model rationale copied into the explanation | Implemented; outside reader still useful |
| AC4 display questions | Old snapshots without `plain`, custom current rubric, missing-file fallback; archived judgement and overall score unchanged | Implemented, offline tests pass |
| AC5 run page / report / API | FastAPI test, escaped user text, static report ordering; actual browser rendering on a synthetic archive with no horizontal overflow or browser JS errors | Implemented; original browser probe on a real archive pending |
| AC6 three real archives and readability | Only a standalone real HTML report was supplied; source spans and judgements are not in Git | Pending; not claimed complete |

Full suite after implementation: **170 passed**. `ruff check .`, `ruff format --check .`, and `mypy` pass. A pre-existing geocoder test reached the network; an earlier, separate commit fixes its cache key and fails on unexpected network access. Baseline before that correction was 156 passed / 1 failed.

## Finish with a teammate's real archives

1. Review this branch, then run the app on three existing archives in the appropriate event sandbox environment.
2. Confirm the plain counts and review actions against the original tool records, especially ambiguous imagery, missing answers and partial searches.
3. Paste the three explanations here and record a readability result or an outside reader's feedback.
4. Run `tests/browser/console_probe.py` on one real archived run, then open the PR for independent review. Do not mark this slice shipped before those checks and review.

The local preview is explicitly synthetic and read-only. It is not a new benchmark result or proof of a fresh AWS deployment.
