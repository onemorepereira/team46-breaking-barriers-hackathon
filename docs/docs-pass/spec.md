# Documentation in Ship Shape: Spec (Quick track)

**Status:** Built

## Problem
Most of the repo's documentation is feature records: spec, design and handoff per feature. A new developer or contributor has no single place to:
- set up the repo and run it;
- learn the configuration and CLI;
- see how to extend it (a tool, a prompt, a rubric, a judge, an example card);
- learn the project's conventions.

Some claims have also gone stale after a day of fast changes. The people affected are the team, Clay and ADB, who inherit the open-source repo after the event.

## Acceptance criteria
- [x] **AC1 Accurate.** Every stale or false claim found by an independent audit of the docs against the code is fixed or explicitly dated as history, in the README, the feature docs and the in-code API docs. "Current" numbers (test count, panel) match the code.
- [x] **AC2 Developer guide** (`docs/developer-guide.md`), written for someone who has never seen the repo, covering:
  - prerequisites;
  - setup and first run, offline and then with AWS;
  - credentials (how they're loaded, and that sandbox session tokens expire);
  - architecture in one screen;
  - the archive and `out/` layout;
  - a configuration reference for every `harness.yaml` key and its default;
  - the environment variables;
  - a CLI reference for every subcommand and flag;
  - recipes for adding an MCP tool server, a task prompt or suite, swapping the rubric, changing the judges, and adding an example card;
  - testing (offline, fixtures, what CI runs);
  - troubleshooting for the failures seen in live runs.
- [x] **AC3 Contributor guide** (`CONTRIBUTING.md`, at the root where GitHub surfaces it), covering:
  - the branch rule;
  - commit format;
  - the checks to run before pushing (the exact CI commands);
  - the layering rules;
  - the dependency allowlist;
  - prompts as files;
  - the secrets rule;
  - the README sourcing convention (cite a brief or tag **[team]**, **[event]** or **[ext]**);
  - the feature-doc convention (`docs/<slug>/` with spec, design, handoff);
  - how to review.
- [x] **AC4 References and core documents.** `docs/README.md` indexes every doc by audience and kind: the event briefs (core), feature records, guides, and the in-app API reference. Every doc is reachable from the README in at most 2 clicks, and every relative link in the docs resolves.
- [x] **AC5 Checked mechanically.**
  - A test fails if a relative Markdown link in `README.md`, `CONTRIBUTING.md` or `docs/**/*.md` points to a missing file.
  - Every `harness <cmd>` mentioned in the developer guide must exist in the CLI.
  - Every top-level `harness.yaml` key must be documented in the guide.

## Non-goals
- Rewriting the feature records (spec, design, handoff). They're dated history: they get dated notes, not rewrites.
- A docs website or generator.
- A CHANGELOG. Git history plus the dated handoffs serve that at this stage.

## Assumptions and open questions
- The branch rule (work on `design/eval-harness`, never `main`) is the current team practice and goes into CONTRIBUTING as such. Owner: the team lead. Default: as stated, until the hackathon merge.

## Plan
1. Independent accuracy audit (subagent), then fix each finding (AC1).
2. Write `docs/developer-guide.md` from the code: config defaults (`harness/config.py`), CLI (`harness/cli.py`), env vars, the tool registry, the archive layout (AC2).
3. Write `CONTRIBUTING.md` from CI (`.github/workflows/ci.yml`), the layering test and the allowlist (AC3).
4. Write `docs/README.md` and link it from the README (AC4).
5. Add `tests/test_docs.py` (AC5), then run the suite, lint and types.
5a. Added at the user's request mid-pass: `docs/factory.md`, a ledger of every effort's purpose and status, kept complete by a test.
6. Verify (self-review), then the handoff.
