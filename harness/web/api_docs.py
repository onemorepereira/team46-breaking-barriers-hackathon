"""The console API's documentation: the overview, tags, error shapes and request/response models that
FastAPI renders at /api/docs. Kept apart from app.py so the routes stay readable."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

DESCRIPTION = """
The **Team Foundry console** runs a geospatial agent on a prompt, records every model and tool decision as
OpenTelemetry spans, and scores the run for the quality and accuracy of the dataset it produced.

**How a run flows**

1. **Start a run** (`POST /api/runs`) with a prompt such as *"Find the solar parks in Jodhpur district,
   Rajasthan, India…"*. The search area is read from the prompt and resolved to an official boundary
   (OpenStreetMap or US Census). LGND Geo searches are kept inside it.
2. **Stream its events** (`GET /api/runs/{run_id}/events`): each step arrives in plain English as it happens,
   then each judge's verdict, then a final `done` event with the full run.
3. **Read the result** (`GET /api/runs/{run_id}`), or the static report (`GET /reports/{run_id}`).

**How a run is scored**

- *Measured by code:* claim provenance (does each claimed value appear in the tool result it cites?) and area
  compliance (is each claimed site inside the requested area?).
- *Judged:* a tribunal of three LLM judges from three model families scores eight criteria (tool choice and
  arguments, sequencing and recovery, efficiency, result relevance, grounding, completeness, honest
  uncertainty) on 0–2 scales. Each criterion takes the median vote.
- *Gates:* a run with no answer, or no successful tool call, is **FAILED**. A run whose model calls all failed
  (for example, expired credentials) is **not scored**.
- *Confidence* (High, Medium or Low) says how far the judges agreed and whether the trace is intact. It is not
  ground truth.

The rubric is `rubrics/geo-dataset-v1.yaml`; see `docs/judging/guide.md` for the full method.
"""

TAGS: list[dict[str, Any]] = [
    {"name": "Runs", "description": "Start a run, list archived runs, and read one in full."},
    {"name": "Live events", "description": "Server-sent events for a run in progress or being judged."},
    {"name": "Judging", "description": "Send a run to the judge tribunal again."},
    {"name": "Reports", "description": "Static HTML reports, one per run."},
    {
        "name": "Tiles",
        "description": "Map imagery served and cached by the console (docs/tile-cache): imagery basemaps, and the tile under each search result, archived with its run so replays work offline.",
    },
    {"name": "Setup", "description": "What this console is configured with."},
]

ERRORS: dict[int, dict[str, Any]] = {
    400: {"description": "The prompt is empty, the model is unknown, the run was refused (for example, the "
                         "suite's cost cap), or a paging cursor is invalid.",  # fmt: skip
          "content": {"application/json": {"example": {"error": "Type a prompt first."}}}},
    404: {"description": "No run with that ID (or no live stream / report for it).",
          "content": {"application/json": {"example": {"detail": "unknown run"}}}},
    409: {"description": "The run is still running or already being judged.",
          "content": {"application/json": {"example": {"detail": "this run is still running or being judged"}}}},
}  # fmt: skip

TILE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The tile. `X-Tile-Origin` says where it came from: `cache`, `archive`, `upstream` or `stale` (an expired copy, served because the provider failed).",
        "content": {"image/jpeg": {}, "image/png": {}},
    },
    404: {"description": "Unknown source or index, a tile out of range, or an invalid bbox."},
    502: {
        "description": "No copy anywhere and the provider failed (or answered with something that isn't an image)."
    },
}

EVENTS_DOC = """
A `text/event-stream` of JSON events (`data: {...}`), in order. The stream ends after `done`.

| `type` | When | Carries |
| --- | --- | --- |
| `area` | first, for a new run | `label`, `source`, `geometry` (GeoJSON) of the requested area, or a `note` saying why there is none |
| `rejudge` | first, for a re-judge | nothing else: the run is being judged again, so no `step` events follow |
| `step` | each model call or tool call, as it ends | `entry`: a plain-English `title` and `detail`, `status`, tokens, the raw span; `chips`: result footprints for the map |
| `judging` | the run ended; judging starts | `seats`: the judges, with `recused_for` where a reserve sits for a same-family judge |
| `judge` | each judge's verdict | `key`, `status`, `score` (0–100), `cost_usd`, `latency_s`, `stood_in_for` |
| `not_scored` | no model call succeeded | `cause` |
| `judge_error` | judging failed | `error` |
| `done` | last | `status`, `error`, and `view`: the same object as **One run, in full** |

Live streams exist for runs started or re-judged since the console started; an archived run has none (404).
"""


class RunRequest(BaseModel):
    prompt: str = Field("", description="What the agent should find, and where. The area is read from it.",
                        examples=["Find the solar parks in Jodhpur district, Rajasthan, India, and give each "
                                  "one's location exactly as the tool returned it."])  # fmt: skip
    model: str | None = Field(None, description="An agent model key from **Agent models and the seated "
                                                "judges**. Defaults to the configured default.",
                              examples=["sonnet"])  # fmt: skip


class RunStarted(BaseModel):
    run_id: str = Field(description="The new run's ID. Stream its events at /api/runs/{run_id}/events.")


class JudgeStarted(BaseModel):
    run_id: str
    events: str = Field(description="Where the judging progress streams.")


class ModelsResponse(BaseModel):
    models: list[str] = Field(description="Agent model keys a run can use.", examples=[["sonnet", "kimi"]])
    judges: list[str] = Field(description="The seated judge tribunal (before recusal).",
                              examples=[["opus", "deepseek", "kimi"]])  # fmt: skip


class RunRow(BaseModel):
    id: str
    started_at: str | None = Field(None, description="UTC, ISO 8601.")
    model_key: str | None = Field(None, description="The agent model.")
    status: str = Field(description="`ok`, `limit_exceeded`, `error` or `running`.")
    prompt: str = Field(description="The prompt, first 140 characters.")
    prompt_file: str | None = None
    score: float | None = Field(
        None, description="Overall score, 0–100; 0 when FAILED; null when not judged."
    )
    verdict: str = Field(description="`scored`, `FAILED`, `not scored` or `not judged`.")
    not_scored_cause: str | None = Field(
        None, description="Why the run wasn't scored (an infrastructure error)."
    )
    confidence: str | None = Field(None, description="`High`, `Medium` or `Low`: judge agreement and trace "
                                                     "integrity, not ground truth.")  # fmt: skip
    cost_usd: float | None = Field(None, description="Agent cost, from token counts and `prices_per_mtok`.")
    judging_cost_usd: float | None = Field(None, description="What the judges cost.")
    tool_calls: int
    errors: int
    runtime_s: float | None = None
    area: str | None = Field(None, description="The requested area, as resolved from the prompt.")


class RunsResponse(BaseModel):
    runs: list[RunRow] = Field(description="One page of runs, newest first.")
    next: str | None = Field(None, description="Pass as `before` for the next page; null on the last page.")
    total: int = Field(description="Runs matching the filters, across all pages.")
