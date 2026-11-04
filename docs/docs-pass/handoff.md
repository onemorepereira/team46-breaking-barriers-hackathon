# Documentation in Ship Shape: Handoff

**What shipped** (2026-11-04):
- **Guides:** a [developer guide](../developer-guide.md) (setup, credentials, architecture, archive layout, the full `harness.yaml` and CLI reference, recipes, testing, troubleshooting) and [CONTRIBUTING](../../CONTRIBUTING.md) (branches, commits, CI checks, test-enforced rules, doc conventions, review).
- **Indexes:** a [docs index](../README.md) by audience, and [the factory](../factory.md), a ledger of every effort's purpose and status (asked for during the pass).
- **Accuracy:** 23 stale claims fixed across the README and the feature docs.
- **Checks:** `tests/test_docs.py`, which keeps links, the CLI reference, the config reference and the ledger true.

**Verification:**
- [x] **AC1 Accurate.** An independent subagent audited every doc against the code. It ran the CLI `--help` and the suite, and spot-checked 7 brief footnotes (all resolve). All 23 findings were fixed:
  - **README:** the test count (122 → 151, ×2), the CI list (adds `ruff format`), the third reserve (Sonnet), the task line (Dallas benchmark plus 16 example cards), and "may import only itself and the ones listed";
  - **eval-harness/design.md:** a dated "Revised 2026-11-04" banner covering the modules never split out, the old config and suite examples, the missing deploy scripts, and the IAM role allowing Kimi. Its status went from "Ready for planning" to "Built … kept as history";
  - **eval-harness/spec.md:** five-judge → tribunal (dated);
  - **judging/design.md:** three judges; judge timeouts (240 s read, adaptive retries); stand-ins replacing the "failed judges are not replaced" line; Chart.js removed from the stack; the tile endpoints added to the table;
  - **judging/spec.md:** confidence Low/Medium rules matching the code, and the four basemaps as built;
  - **judging/handoff.md:** the Grok follow-up marked resolved; "below" → "above";
  - **layering/spec.md:** the `analysis` imports matching `ALLOWED` (dated);
  - **tile-cache/design.md:** atime for LRU, mtime for freshness;
  - **example-cards/spec.md:** 16 cards as built;
  - `area_mode` is now explicit in `harness.yaml`.
- [x] **AC2 Developer guide.** Written from the code: config defaults (`harness/config.py`, `harness/tiles.py`, `harness/judge.py`), run limits (`harness/invoke.py:DEFAULT_LIMITS`), env vars (grep of `os.environ`), CLI (`build_parser`), the tool registry and describers, and the archive layout. It covers every topic the audit listed as missing.
- [x] **AC3 Contributor guide.** The CI commands are copied from `.github/workflows/ci.yml`, and each "rule the tests enforce" names its test (`test_layers.py` AC1–AC3, `test_import_lint.py`, `test_docs.py`).
- [x] **AC4 References and core docs.** The `docs/README.md` index covers the guides, the event briefs, feature records, data and config, and the API reference. `test_every_doc_is_reachable_from_the_readme_within_two_links` passes, and it first failed on 9 unreachable docs, including layering, example cards and the tile-cache launch.
- [x] **AC5 Checked mechanically.** `tests/test_docs.py` has 5 tests:
  - relative links resolve;
  - every doc is reachable within 2 links;
  - the guide's CLI table equals the real subcommands, and every `` `harness X` `` mention exists;
  - every top-level, `judging.*` and `tiles.*` key in `harness.yaml` is documented;
  - the factory lists every `docs/<slug>/spec.md`.

  `uv run pytest`: 151 passed; ruff and mypy are clean.

**Exercised live:** `uv run harness --help` and each subcommand's `--help` were run against the guide's CLI table, and all 13 README quickstart commands match the parser.

**Gate history:** Define (self-review), Build, Verify (self-review, plus the independent accuracy audit, which served as the adversarial read; Quick track).

**Decisions and deviations:**
- Feature records are dated history. They got dated notes and corrections, not rewrites (spec non-goal).
- `docs/factory.md` was added at the user's request mid-pass, with a test so no effort goes unlisted.

**Follow-ups:**
- The README sourcing tags (**[team]**, **[event]**, **[ext]**, or a brief citation) are a convention, not a test. A checker would need sentence-level parsing, so it's deferred.
