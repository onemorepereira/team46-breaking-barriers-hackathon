# Condition-aware evaluations — handoff

Aditya / Codex, 2026-11-04. Branch `slice/complete-evaluations`, integrated with main `4612e27` (including Miguel's human review and judge reconsideration).

## Shipped on this branch

- Plain-language explanations and stricter source-value checks from the earlier branches.
- New runs extract conditions once with the configured narrative model, archive them in `conditions.json`, and then judge. Invalid/missing extraction is recorded visibly and prevents an overall score. Extraction usage is saved separately; existing agent/judge cost totals do not include this extra call.
- Replay and re-judge only read stored conditions. Legacy archives have no conditions table or condition score; no retroactive model call.
- A claim-by-condition matrix includes status, reason and evidence refs. Boundary contradictions are explicit; missing proximity evidence stays unverified. Reference points require matching metadata from successful tools. Far references cannot establish absence of nearer ones.
- Great-circle point distance, with explicit point/boundary limitations. Target identity and other constraints remain for judge/human assessment.
- Rubric v2 adds measured condition coverage and makes relevance/completeness assess all request conditions. Output scores cannot exceed measured spatial-condition coverage; missing evidence prevents High confidence. Existing rubric-v1 archives keep their scoring definitions.
- The API, console, static reports and final live-stream response carry the same matrix. No worker redeployment is needed.

## Run it without credentials or charges

```sh
git switch slice/complete-evaluations
uv sync
uv run python -m scripts.demo_evals
```

Open http://127.0.0.1:8789/runs/run-0001. This is a read-only synthetic demonstration: one location inside the boundary, one outside, and no evidenced protected-area reference. The matrix must show supported / contradicted area cells and unverified distance cells. No AWS or model calls occur; the basemap imagery is deliberately absent. The fixture judge votes are not real model accuracy measurements.

For the full app over real archives, use `uv run harness ui`. Use your event account's `harness.local.yaml`, never someone else's account settings. Verify `aws sts get-caller-identity` before live calls. A new run adds one Bedrock condition-extraction call. Replay stays free of model calls.

## UI handoff

`GET /api/runs/{id}` and the live `done.view` include `explanation` (headline, summary, check_by_hand), `conditions` (conditions, rows of cells, supported, total, score, needs_review, error), and `source_check_note`. Each cell has condition_id, status, reason, refs. Legacy conditions are null. Rendering uses text nodes/HTML escaping. Keep the reasons and unverified status visible when redesigning; do not turn absence of evidence into a green check.

## Validation

Tests cover known distances and the date line, extraction once, omitted distance constraints, invalid distances, extraction failure, failed evidence, supported/contradicted/unverified matrix cells, matching reference types, negative reference labels, far-reference uncertainty, legacy replay, output caps, and no mutation of archived judgements. The existing feedback tests still pass with version-scoped guidance. Full checks are recorded in the PR.

Browser: actual running synthetic app inspected; matrix and explanations visible. Tests do not establish real-world retrieval accuracy or expert agreement.

**Still pending:** a fresh live event-sandbox run of Miguel's ZIP/protected-area example, live planted-defect calibration under rubric v2, and three-real-archive readability/human checks. These require the appropriate AWS/LGND environment and real archives. They are not claimed complete. This branch is ready for code/UI integration review, not yet a validated scientific benchmark.
