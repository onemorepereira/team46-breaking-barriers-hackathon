# Layering refactor — Handoff

**What shipped:** the code is split into six layers with enforced boundaries.
- `core/`: store, span schema, geometry, prompt loader.
- `prompts/`: every model-facing text, as Markdown.
- `tools/`: one package per MCP server, `roda/` and `lgnd/`, each with descriptors, result parsers, client and auth, plus a registry and test fakes.
- `agent/`: the runtime.
- `analysis/`: pure grading.
- `harness/`: CLI, UI and services.

It also fixes the empty map for non-US prompts. LGND's Sentinel-2 tables are now parsed, and tiles come from EOX Sentinel-2 cloudless when the chip isn't NAIP.

**Verification**
- [x] **AC1, the layer rule:** `tests/test_layers.py::test_ac1_imports_follow_the_layer_table`. A planted violation was flagged (analysis importing `tools.lgnd.client`; harness importing `agent`).
- [x] **AC2, prompts are files:** `test_ac2_no_inline_model_instructions`. A planted "You are…" string was flagged. Prompts present: `agent/system`, `agent/search_area`, `agent/search_area_enforced`, `harness/narrative`, `harness/area_extract`, `tasks/*`.
- [x] **AC3, tool knowledge stays in `tools/`:** `test_ac3_tool_knowledge_stays_in_tools`. A planted tool name in `harness/` was flagged.
- [x] **AC4, behavior unchanged:**
  - Suite: 84 passed (78 at baseline, plus 3 layer tests and 3 new LGND/tile tests). ruff and mypy are clean.
  - System prompt SHA-256 unchanged (`5514f687…`, also confirmed on the deployed run's spans).
  - CLI commands unchanged.
  - Live local UI run ("farmland within laos"): 0 missing fields; 15 Sentinel-2 tiles, all inside Laos.
  - Live AgentCore run `91af58a6`, after a redeploy: 0 missing fields, 6 of 6 claims matched, LGND area enforced.

**Decisions and deviations:**
- `analysis/` may import `tools.*.descriptors` and `tools.lgnd.results`. Both are pure, static metadata and parsers, so the grader knows each server's dataset fields without depending on clients.
- Display imagery lives in `harness/imagery.py`. It's presentation only and never reaches the agent.

**Follow-ups:**
- The Laos run hit the 400k input-token cap. LGND's Sentinel-2 grids are large. Consider a higher cap for country-scale prompts, or trimming the grids before the model sees them.
- The test fakes (`tools/scripted.py`) ship in the image. They're harmless, because they're only used when `HARNESS_TEST_SCRIPT` is set.
