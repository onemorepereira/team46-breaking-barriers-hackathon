# Deck Claims and Their Sources

Every number or factual claim in `deck.html`, with the file it comes from. If a number changes, change it here and in the deck together. Checked 2026-11-04; deck and this table brought up to date with `main` on 2026-11-05 (the 5-minute deck and `deck.pdf` too).

**Run archive cleanup (2026-11-04):** all earlier runs were deleted, and five control runs were re-run. Claims about earlier runs (the FAILED → 85.4 bug-fix story, calibration, agreement, Opus's correction) are cited to the handoffs that recorded them; those run IDs no longer open in the console. The live-demo claims (slides 1 and 3) cite the new runs, read from the console's run view on 2026-11-04.

**Second cleanup (2026-11-05):** every run started before `3847ae55` (2026-11-05 10:56 UTC) was deleted, including the Pecos demo run and the runs cited for the visual check (`1e940baf`, `e614c610`, `195ff1d6`). Their figures stay cited to the handoffs that recorded them; the IDs no longer open. Kept: `3847ae55` and the ADB T1 suite runs (`fe9b540d` … `e18447dc`) and `7f9a6617`. The demo needs a fresh Pecos run before it is given.

| Slide | Claim | Source |
| --- | --- | --- |
| 1, 11 | Team Foundry, Team 46: Aditya Pasarti, Farhan Shahriar, Uday Kandi, Miguel Pereira | The team **[team]** |
| 11 | Open source, Apache-2.0 | `LICENSE` |
| 1 | Evaluating agentic workflows is Clay's #1 unmet need (speaker note) | `docs/Clay-Foundry-Vision-Hackathon.md:17` |
| 1 | "5 solar farms" | Run `79c18997` (Pecos County solar, Sonnet 5.5 on AgentCore, 2026-11-05): 5 coordinate claims, 5/5 verified |
| 2 | Every model and tool call is an OpenTelemetry span | `README.md`, "What we built"; `docs/eval-harness/handoff.md` |
| 2 | Claims cite a tool result, and code checks the value and the area | `docs/judging/guide.md` (measured criteria) |
| 2, 4 | Three judges from three companies: Opus 5.5, DeepSeek V3.2, Kimi K3 | `harness.yaml` (`judging.panel`); `docs/judging/guide.md`, "The panel" |
| 3 | The Pecos run was built by Sonnet 5.5 on AgentCore | Run `79c18997` manifest (`model_key: sonnet`, backend `agentcore`) |
| 3 | Opus steps down for its own family's agent, and Mistral sits | `docs/judging/guide.md` (recusal); run `79c18997` seats: mistral (for opus), deepseek, kimi |
| 3 | 5/5 claims verified, 5/5 inside the county, 5/5 seen in the imagery; 99.4, High confidence | Run `79c18997` view (`kpis`, `scorecard`, `map.visual`), 2026-11-05 |
| 3 | Against the USGS inventory: 5 of 12 farms found (site recall 0.417, precision 1.0) | Run `79c18997` `reference`, against `references/uspvdb-tx-pecos-v4` |
| 3 (contrast) | A weak run: Kathmandu substations, 38.3 (no sites; the agent said it could not find any) | Run `5f830bdc` (ADB T1 suite, 2026-11-05) |
| 3 | The score varies slightly when re-judged | Judges are LLMs; `docs/judging/guide.md` ("Repeat stability") |
| 4 | Measured by code (provenance; sites inside the boundary and seen in open imagery) plus 8 judged criteria; each criterion the mean of every vote over three concurrent passes; High/Medium/Low confidence; no answer means FAILED | `rubrics/geo-dataset-v1.yaml` (`version: 3`: 4 measured incl. request conditions, 8 judged); `harness.yaml` (`judging.passes: 3`); `docs/judging-stability/handoff.md`; `docs/visual-check/handoff.md` |
| 4 | No judge grades its own family's agent | `docs/judging/guide.md` (recusal); `harness.yaml` `recuse_same_family: true` |
| 4 | Judges never see the measured results | `docs/judging/handoff.md`, "Decisions made in this pass" |
| 5 | Planted defects: no area 2→0, made-up site 2→0, answer removed 2→0 | `docs/judging/handoff.md:61–63` (live, run `5769706d`) |
| 5 | The first calibration pass caught a bug in our evidence builder | `docs/judging/handoff.md:55` |
| 5 | Agreement score 0.50 (Krippendorff's α), 95% CI 0.12–0.67, 7 runs | `docs/judging/handoff.md:116` (0.502) |
| 5 | Human experts' α ≈ 0.56 in the paper Clay shared (GRA) | `docs/judging/paper-notes.md:17` |
| 6 | A review is evidence to check, not an order; the revised score keeps the original | `docs/judge-feedback/spec.md` (AC3, AC4); `docs/judging/guide.md`, "Human feedback" |
| 6 | Opus: "The steps show eight sites were checked against imagery, not three: five Central Valley sites in T6 and three North Coast sites in T9" (our deliberately wrong review) | `docs/judge-feedback/handoff.md`, "Exercised live" (run `42b0a155`, review `r-4d3985152d1d`) |
| 6 | Lessons are tested on held-out runs (a third of reviewed runs) and approved by a person; each score records its guidance version; rollback | `docs/judge-feedback/design.md`, "Train and held-out runs", "Evaluation", "Approval, off and rollback" |
| 6 | Stored in each deployment's own archive, not in the code or a browser | `docs/judge-feedback/design.md`, "Where things live" |
| 6 | Wrong, "I insist" and injected reviews resisted, live, measured against a control | `docs/judge-feedback/handoff.md`, AC7 (run `a5670c6b`, `harness calibrate --feedback`, $1.43) |
| 7 | Before: FAILED, no answer, $1.50 | `docs/console-polish/handoff.md:39` (run `fdacf7cf`) |
| 7 | After: 85.4 High, 0 errors, 15/15, 8/8, $0.81 | `docs/console-polish/handoff.md:38` (run `a5670c6b`) |
| 7 | "Northern California" resolved to a 20 m building in San Francisco | `docs/judging/handoff.md:110` (run `c251934d`) |
| 7 | The LGND token lives 300 s, and every call after 290 s failed | `docs/console-polish/handoff.md:50` |
| 7 | Narrowed searches (16 km circles) were widened to all of Texas | `docs/console-polish/spec.md`, problem 3 |
| 8 | Strands on Bedrock AgentCore; Sonnet 5.5 or Kimi K3; RODA and LGND Geo over MCP; OTel to S3; FastAPI console; CDK | `README.md`, "How it works" and "Decisions" |
| 8 | The exporter is swapped by config, proved in CI | `README.md`: "OpenTelemetry is the only telemetry API" and goal 5, "Keep observation pluggable" |
| 8 | ADB's rubric is one YAML file | `docs/judging/guide.md`, "To use ADB's rubric" |
| 8 | Replays work offline from the trace | `README.md` ("Reports work offline"); `docs/tile-cache/handoff.md:24` (31/31 tiles from the archive with every provider blocked) |
| 9 | Runs in AWS us-west-2: AgentCore Runtime, Amazon ECR (agent image), Secrets Manager (LGND login), CloudWatch (logs and traces), S3 run archive | `infra/app.py` (stack region, `DockerImageAsset`, `LgndGeoLogin` secret, archive bucket, runtime log group) |
| 9 | Strands agent; RODA and LGND Geo MCP servers; AWS Open Data | `README.md`, "How it works"; `agent/`, `tools/` |
| 9 | Agents Sonnet 5.5 and Kimi K3; judges Opus 5.5, DeepSeek V3.2, Kimi K3 | `harness.yaml` (`models`, `judging.panel`) |
| 9 | Six steps: start a run (cost caps), the agent builds, traces are saved, code checks, three-family judges score with three passes each and the votes averaged, a person reviews | `README.md`, "How it works"; `docs/judging/guide.md`; `docs/judging-stability/handoff.md`; `docs/judge-feedback/spec.md`. The diagram and its alt text say "mean of votes, 3 passes" (corrected 2026-11-05) |
| 10 | Proves claims match their tool output, sites are in the area and visible in open imagery, judges agree; not yet how many sites were missed, which needs an answer key (one so far: USGS, Pecos) | `docs/judging/gaps.md`; [visual-check handoff](../visual-check/handoff.md); `references/uspvdb-tx-pecos-v4` |
| 10 | Next: answer keys for ADB's places, ADB's rubric, ADB's experts reviewing runs (the loop is built), a second vision vote per site; shipped since: plain-language verdicts, prompt compliance, the vision check | `docs/factory.md` ("Open work"); plain-language verdicts and prompt compliance shipped in PR #7; visual check in PR #33 |

**Costs for Q&A** (not on a slide):
- **Judging:** about $0.22 per three-pass judging on a Sonnet run (`docs/judging-stability/handoff.md`, "Proof"), plus the visual check: $0.057 for 5 sites on run `1e940baf` (`docs/visual-check/handoff.md`, "Exercised live"). Before three passes, one pass cost $0.10 (run `3d7ac12a`, `docs/judging/handoff.md`, "Tribunal of three") to $0.31 (run `a5670c6b`, `docs/console-polish/handoff.md:38`).
- **The agent:** in our runs, India cost $0.32 (`docs/example-cards/handoff.md`) and Texas $0.81.
