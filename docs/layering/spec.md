# Layering refactor — Spec (Define-lite)

**Track:** Quick   **Product stage:** Introduction
**Status:** Built   **Last updated:** 2026-11-04

## Problem

The code mixes concerns across packages, so it's hard to see, change or review any one of them on its own:
- Prompt text lives inline in Python (`harness/narrative.py`, `harness/geo.py`, `agent/handler.py`), next to code.
- Tool and MCP specifics (RODA and LGND tool names, schemas, result formats, URLs, OAuth) are spread over `agent/`, `analysis/` and `harness/`.
- The layers import each other freely: `harness/` imports `agent/`, and `agent/` imports `analysis/`.

## Target layers

| Layer | Package | Holds | May import (first-party) |
| --- | --- | --- | --- |
| Core | `core/` | Shared, dependency-light building blocks: archive store, span-schema constants and `span_kind_for`, geometry math, the prompt loader | nothing |
| Prompts | `prompts/` (Markdown only) | Every piece of text sent to a model: the agent system prompt, the search-area note, narrative instructions, area-extraction instructions, task prompts | n/a (data) |
| Tools | `tools/` | One subpackage per tool server (`tools/roda/`, `tools/lgnd/`), plus `tools/scripted.py` test fakes and the `tools/registry.py` that builds the MCP clients. Each server package owns its descriptors (tool names, which tools read an area, dataset fields), result parsing, client construction and auth | `core` |
| Agent runtime | `agent/` | Strands agent, hooks, telemetry, archive processor, entry points | `core`, `tools` |
| Analysis | `analysis/` | Pure functions over archived runs | `core`, `tools.*.descriptors` (static metadata only) |
| Harness | `harness/` | CLI, config, invoking runs, UI, narrative and area-resolution services | `core`, `analysis`, `tools` (never `agent`: runs it as a subprocess or remotely) |

## Acceptance criteria

- [ ] **AC1 Layer rule.** A test parses every module's imports, and fails on any first-party import the table doesn't allow.
- [ ] **AC2 Prompts are files.** Every model-facing instruction is loaded from `prompts/` through `core.prompts`. A test fails if any `.py` file under `core/`, `tools/`, `agent/`, `analysis/` or `harness/` contains an inline model instruction (a string literal over 160 characters that addresses the model, e.g. starting "You ").
- [ ] **AC3 Tool knowledge stays in `tools/`.** A test fails if any module outside `tools/` contains a server-specific literal: a RODA or LGND tool name, `geo.lgnd.ai`, or `roda-mcp-server`.
- [ ] **AC4 Behavior unchanged:**
  - the full suite is green;
  - the system prompt's SHA-256 is unchanged;
  - the CLI's commands and flags are unchanged;
  - a scripted local run, a live local run and a live AgentCore run each report 0 missing fields, with claims graded and area enforcement working.

## Non-goals

- No behavior or feature changes.
- No prompt wording changes, apart from moving text into files.
- No new dependencies.

## Plan

1. `core/`: move `analysis/store.py` there; split the span schema out of `analysis/trace.py` into `core/spans.py`; move geometry math into `core/geometry.py`; add `core/prompts.py`.
2. `prompts/`: lay it out as `agent/system.md`, `agent/search_area.md`, `harness/narrative.md`, `harness/area_extract.md` and `tasks/*.md`. Update the suite file and the docs to match.
3. `tools/`:
   - `roda/` (descriptors, client);
   - `lgnd/` (descriptors, areas, results, auth, login, client);
   - `scripted.py`;
   - `registry.py` (client building, moved out of `handler.py`).
4. Rewire `agent/`, `analysis/` and `harness/` to the new modules, and delete the old copies.
5. Tests for AC1–AC3; update the Dockerfile and `pyproject` packages.
6. Verify AC4: suite, scripted, live local, then deploy and run live on AgentCore. Commit after each green step.
