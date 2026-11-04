# Condition-aware evaluations — handoff

Aditya / Codex, 2026-11-04. Branch `slice/complete-evaluations`, integrated with main `4612e27` (including Miguel's human review and judge reconsideration).

## Shipped on this branch

- Plain-language explanations and stricter source-value checks from the earlier branches.
- New runs extract conditions once with the configured narrative model, archive them in `conditions.json`, and then judge. Failed extraction is recorded visibly and prevents an overall score only when the selected rubric includes condition_compliance. An unset narrative model records conditions as not checked (N/A) and permits the remaining evaluation. Extraction usage is saved separately; existing agent/judge cost totals do not include this extra call.
- Replay only reads stored conditions and never calls models. Explicit re-judging under a condition-aware rubric retries missing or failed extraction; valid archived conditions are reused. Wrapped JSON is accepted and invalid replies get one corrective retry.
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

For the full app over real archives, use `uv run harness ui`. Use your event account's `harness.local.yaml`, never someone else's account settings. Verify `aws sts get-caller-identity` before live calls. A new run adds a Bedrock condition-extraction call, with one corrective retry for malformed replies. Explicit re-judging can retry missing or failed extraction. Replay stays free of model calls.

## UI handoff

`GET /api/runs/{id}` and the live `done.view` include `explanation` (headline, summary, check_by_hand), `conditions` (conditions, rows of cells, supported, total, score, needs_review, error), and `source_check_note`. Each cell has condition_id, status, reason, refs. Legacy conditions are null. Rendering uses text nodes/HTML escaping. Keep the reasons and unverified status visible when redesigning; do not turn absence of evidence into a green check.

## Validation

Tests cover known distances and the date line, extraction once, omitted distance constraints, invalid distances, extraction failure, failed evidence, supported/contradicted/unverified matrix cells, matching reference types, negative reference labels, far-reference uncertainty, legacy replay, output caps, and no mutation of archived judgements. The existing feedback tests still pass with version-scoped guidance. Final local checks: **222 tests passed**, ruff lint/format, mypy and diff checks passed (Python 3.13.1). An advanced distance request with no locations receives zero output credit. Browser demo shows the coverage cap even when fixture judges unanimously give full marks.

Browser: actual running synthetic app inspected; matrix and explanations visible. Tests do not establish real-world retrieval accuracy or expert agreement.

**Live ZIP case now checked (November 4):** event run `d0bfb674-ac6c-4058-bfc8-fa92bccfd224` completed with real Kimi/RODA/LGND and three valid judges. The refreshed matcher-3 report has 14/14 source values matched, but no adequate located evidence for protected-area designation/proximity. Condition coverage remains 3/6, output is capped at 50, overall is 68.8 and confidence Medium. The parser correction is documented in [value matching](../value-matching/handoff.md#live-lgnd-follow-up-matcher-version-3). A separate Sonnet Napa imagery run (`a6d3001c-5768-446c-9f33-c93b2e866c6c`) also completed end to end.

**Still pending:** live planted-defect calibration under rubric v2 and three-real-archive readability/human checks. Successful cloud execution does not establish retrieval accuracy or expert agreement. This branch is ready for code/UI integration review, not yet a validated scientific benchmark.


## Review fixes (Nov 4)

All nine PR #7 review threads were addressed: tolerant JSON parsing with one corrective retry; retrying failed/missing extraction on explicit re-judge; optional-model N/A handling; proximity-only omission detection; rubric-scoped caps and extraction-error handling; excluding the claimed site's own coordinates as reference evidence; shared coordinate parsing for lng, mixed-case fields and GeoJSON Points; preserving condition-review actions; and one provenance pass per run view/static report. Valid saved conditions are reused and offline replay never calls Bedrock. Regression tests cover the reported cases, including successful retry after timeout and preserving not-scored state after two invalid replies.

## Second review pass (Nov 4)

A re-review of `ffb3284` found ten more problems, all addressed here with regression tests in `tests/test_conditions.py`:

- **Self-reference:** a claimed site's own record is now the closest match in its cited result at the claim's own rounding, for every claim. An unclaimed site whose label contains the reference words can still count.
- **Nothing to extract:** an empty conditions list or blank prompt is saved as no checkable conditions, not an error.
- **Model unset:** runs show "not checked" and stay below High confidence.
- **Omitted distances:** the safety net covers radius, "from", "closer than" and "under" phrasings, ignores minimum distances, and counts distinct limits.
- **Reference shapes:** polygon, multipolygon and nested-centroid references now count. A site inside the polygon is 0 km; otherwise the nearest outer-ring vertex is used, which can only overstate the distance.
- **Damaged `conditions.json`:** reads as an extraction error, so the page still opens and Re-judge can replace the file.
- **Explanations:** recovery steps always survive the cut to three checks, and the judges-disagree doubt depends on the actual confidence reasons.

**Scoring rulings to review:**

- **The output cap now uses the weakest condition's coverage**, not the pooled share. The `condition_compliance` criterion stays the pooled share (spec AC3). This lowers scores on runs with gaps: the live ZIP run above recorded output 50 and overall 68.8 under the pooled cap. If its 3/6 is all area cells, as the notes suggest, output becomes 0 on replay. That run was not re-scored here.
- **"None found" still scores 0 on output**, as commit `c212302` intended, because code can't tell it from no work. The page now says so and asks for a check by hand. An explicit negative result in the agent's claims format would be the real fix.

**Not changed:** `judge_run` still pays for the panel after a failed extraction, and new runs still extract under rubrics without the criterion.
