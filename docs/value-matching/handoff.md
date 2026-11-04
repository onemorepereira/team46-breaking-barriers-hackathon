# Value checker v2 — local handoff

Aditya / Codex, 2026-11-04. Branch `slice/evidence-matching` follows `slice/plain-verdict`.

## What changed

The checker now:

- compares structured answer/verdict labels as whole values, rather than accepting `supported` inside `not supported`;
- requires both coordinates in one record or labelled table row, with rounding tolerance, instead of finding latitude and longitude independently anywhere in the output;
- rejects values cited from failed tool calls;
- records `value_matcher_version: 2` in new judgements, and shows a plain update note when replaying an older judgement with current checks.

No agent, MCP client, rubric anchor, judge vote, or cloud infrastructure changed. Saved archives and judgement files are not rewritten by viewing them. Older reports can receive different measured scores when regenerated; that is deliberate and disclosed.

## Verification

`tests/test_provenance.py` now covers opposite labels, nested verdicts, coordinates split across records or rows, correct rounded pairs, nested MCP JSON text, explicit GeoJSON coordinate order, unlabeled arrays, hemisphere errors, failed calls, and replay notes. Existing text, escaped Unicode and number tests remain.

The two original reproductions both changed from `True` to `False`. The report/API test verifies that reading an old judgement leaves its saved bytes unchanged. Offline checks and the full suite are recorded in the parent review handoff.

## Limits and review

This is still value-level source checking, not semantic claim verification or an independent answer key. A declared value can appear in the cited output without proving its associated name or full sentence. Some unfamiliar structured coordinate formats will now be rejected conservatively. A reviewer should check a real LGND archive before merging, and update the demo's saved report rather than silently comparing old and regenerated scores.
