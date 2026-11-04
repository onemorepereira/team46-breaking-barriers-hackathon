# Fix value-matching false positives

Owner: Aditya. Branch: `slice/evidence-matching`, after `slice/plain-verdict`. 2026-11-04.

## Problem

The current value checker accepts `supported` inside `not supported`, and a claimed latitude and longitude taken from different result rows. It also accepts a value from a failed tool call. These can inflate the code-checked portion of a score even when the judge panel is sound.

## Acceptance

1. Opposite verification labels do not match. Structured verdict/answer fields use whole-value equality; free-text verdicts exclude negated phrases and longer words.
2. Coordinate claims must match a pair in one source record or one table row, with the existing rounding tolerance. No pairing across separate rows, no guessing coordinate order in an unlabeled JSON array. Ordinary non-JSON `lat, lon` pairs remain supported.
3. A failed cited tool call cannot mark a value matched.
4. Positive cases, rounded coordinates, nested MCP text, and all existing tests still pass. No model calls, judge votes, or rubric anchors change.
5. New judgements record the checker version; a replay of an older judgement displays an update note. Original saved archives and judgements are not rewritten by viewing them.

## Limits

This still checks only declared values in cited evidence. It does not prove the claim's meaning, bind every name to an entity, detect every omitted claim, or establish real-world accuracy. Structured checks can conservatively reject source formats they do not recognize. Prompt-condition checking and an independent answer key remain separate work.
