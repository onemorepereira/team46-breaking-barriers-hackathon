# Contributing to the Team Foundry Eval Harness

Thanks for helping. This page covers the rules a change must follow to be merged. To set up and run the code, see the [developer guide](docs/developer-guide.md). For where everything else lives, see the [docs index](docs/README.md).

## Branches and commits

- **Work on a branch, never on `main`.** Branch from `main` with a prefix that says what the change is: `feat/`, `fix/`, `docs/`, `chore/` or `improve/` (older branches used `feature/` and `doc/`), or `slice/<name>` for a team slice (see [how to take a slice](docs/factory.md#how-to-take-a-slice)). Open a PR back to `main`, reviewed by someone who didn't write it. (Before 2026-11-04, all work went to `design/eval-harness`.)
- **Commit messages:** a short imperative subject line (≤ 72 characters, e.g. `Tile cache: archive result tiles with each run`), a blank line, then a body that says *why*, what changed and how it was checked. If an AI assistant co-wrote the change, end with its `Co-Authored-By:` line.
- **Keep one change per commit when you can.** A fix found while doing something else gets its own commit, or at least its own paragraph in the body.

## Before you push

CI (`.github/workflows/ci.yml`) runs exactly these, and a push must pass them all:

```sh
uv run ruff check .            # lint (line length 110)
uv run ruff format --check .   # formatting; `uv run ruff format .` fixes it
uv run mypy                    # types, for core, tools, analysis and harness
uv run pytest                  # the whole suite; offline, no AWS needed
uv run --group infra pytest tests/test_infra.py   # the CDK stack's checks (needs Node for jsii)

pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm --dir frontend test       # the workspace's tests
pnpm --dir frontend build      # typecheck and build into harness/web/static/workspace/
```

The built workspace is committed, and CI fails if the build changes anything under `harness/web/static/workspace/`. So after any change in `frontend/`, rebuild and commit the bundle with it.

CI also runs **gitleaks** on the full history. Never commit credentials: no AWS keys, session tokens, LGND tokens or `.env` files. Keep local credential files outside the repo. If one slips into a commit, rotate it and rewrite the branch before pushing.

Also never commit:
- **your sandbox's settings**: they go in the git-ignored `harness.local.yaml`, never in `harness.yaml`;
- **runtime data**: runs, archives, reports and tiles (`archive/`, `out/`).

Check `git status` before you push.

## Rules the tests enforce

| Rule | Enforced by |
| --- | --- |
| **Layering.** `core` imports nothing first-party; `tools` imports `core`; `agent` imports `core` and `tools`; `analysis` imports `core` plus `tools` descriptors, parsers and describers; `harness` imports anything but `agent`. The table is in the [README](README.md#code-layout) | `tests/test_layers.py` |
| **Prompts are files.** Every text sent to a model lives in `prompts/` as Markdown and is loaded with `core.prompts.load`, never as a long string in Python | `tests/test_layers.py` |
| **Tool knowledge stays in `tools/`.** RODA and LGND tool names, URLs and result formats belong in `tools/roda/` and `tools/lgnd/` | `tests/test_layers.py` |
| **Dependencies are reviewed.** A new runtime dependency goes in `pyproject.toml` *and* `tests/allowed_deps.txt`, with a comment saying why. Observability-backend SDKs are not allowed, because OpenTelemetry is the contract | `tests/test_import_lint.py` |
| **Docs stay true.** Relative links in `README.md`, `CONTRIBUTING.md` and `docs/` must point to real files; every doc must be reachable from the README within two links; the developer guide must match the CLI and `harness.yaml`; and [the factory](docs/factory.md) must link every `docs/<slug>/spec.md` | `tests/test_docs.py` |

Write tests alongside the code:
- No network: fake the external boundary, as `tests/test_tiles.py` and `tests/test_judging.py` do.
- No sleeps: inject a clock or set file times.
- Build archived runs with `tests/fixtures/builder.py`.

## Documentation conventions

- **Sourcing in the README.** Every statement either cites the briefs (footnotes like `[^T99]` for the [Technical brief](docs/Clay-Foundry-Technical-Hackathon.md) and `[^V110]` for the [Vision brief](docs/Clay-Foundry-Vision-Hackathon.md), with line numbers) or carries a tag: **[team]** for our own decisions, **[event]** for event logistics, **[ext]** for general background.
- **One folder per feature.** A feature or meaningful change gets `docs/<slug>/` with:
  - `spec.md`: problem, testable acceptance criteria, non-goals, assumptions;
  - `design.md`: how, with options weighed, failure modes and rollback;
  - `handoff.md`: what shipped, and how each criterion was proven, with dated results.

  Small changes can skip `design.md`. Link the folder from the [docs index](docs/README.md), and add or update its row in [the factory](docs/factory.md).
- **Feature records are dated history.** When behavior changes later, add a dated note to the old record (e.g. "Revised 2026-11-04: …"), and update the guides and the README so they describe the present.
- **Plain language.** Short sentences, the active voice, and real numbers with their units.

## Changing behavior that others depend on

- **API changes:** when `/api/*` changes, update every caller in the repo in the same change: `harness/web/static/*.js`, the workspace's `frontend/src/api.ts` (then rebuild its bundle), the tests, the endpoint table in `docs/judging/design.md`, and the models and prose in `harness/web/api_docs.py` (shown at `/api/docs`).
- **Agent-side changes** (`agent/`, `tools/`, `prompts/agent/`, and dependencies or the `Dockerfile`, since the agent image installs them) only reach AgentCore after a redeploy (`cd infra && CDK_DOCKER=podman npx aws-cdk deploy`). Say so in the commit if you don't deploy.
- **Rubric and judge changes** are config (`rubrics/*.yaml`, the `judging:` and `visual_check:` blocks in `harness.yaml`). Bump the rubric's `version` when its criteria change; earlier judgements keep the rubric snapshot they were scored with. Run `uv run harness calibrate <run-id>` afterwards to check that the panel still catches planted defects.

## Reviewing

Check that:
- the change does what its spec says, and nothing it doesn't;
- each acceptance criterion is proven by something that was actually run;
- the docs above are updated.

Prefer a reviewer who didn't write the change, and run the real path, not just the tests, before approving.
