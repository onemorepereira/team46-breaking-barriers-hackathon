# Deck Claims and Their Sources

Every number or factual claim in `deck.html`, with the file it comes from. If a number changes, change it here and in the deck together. Checked 2026-11-04.

| Slide | Claim | Source |
| --- | --- | --- |
| 1 | Team Foundry, Team 46: Aditya Pasarti, Farhan Shahriar, Uday Kandi, Miguel Pereira | The team **[team]** |
| 1 | Evaluating agentic workflows is Clay's #1 unmet need (speaker note) | `docs/Clay-Foundry-Vision-Hackathon.md:17` |
| 1 | "15 data centers" | Run `a5670c6b`: 15/15 claims verified (`docs/console-polish/handoff.md:38`) |
| 2 | Every model and tool call is an OpenTelemetry span | `README.md`, "What we built"; `docs/eval-harness/handoff.md` |
| 2 | Claims cite a tool result, and code checks the value and the area | `docs/judging/guide.md` (measured criteria) |
| 2, 4 | Three judges from three companies: Opus 5.5, DeepSeek V3.2, Kimi K3 | `harness.yaml` (`judging.panel`); `docs/judging/guide.md:38–46` |
| 3 | The Texas parks run was built by Kimi K3 on AgentCore | `docs/console-polish/handoff.md:38` |
| 3 | Kimi steps down for its own agent, and Mistral sits | `docs/judging/guide.md` (recusal); seats recorded in run `a5670c6b`'s judgement |
| 3 | 15/15 claims verified, 8/8 sites inside Texas | `docs/console-polish/handoff.md:38` |
| 3 | The score varies slightly when re-judged | Judges are LLMs; `docs/judging/guide.md` ("Repeat stability") |
| 4 | 2 measured and 8 judged criteria; median per criterion; High/Medium/Low confidence; no answer means FAILED | `docs/judging/guide.md:15–80`; `rubrics/geo-dataset-v1.yaml` |
| 4 | No judge grades its own family's agent | `docs/judging/guide.md` (recusal); `harness.yaml` `recuse_same_family: true` |
| 4 | Judges never see the measured results | `docs/judging/handoff.md`, "Decisions made in this pass" |
| 5 | Planted defects: no area 2→0, made-up site 2→0, answer removed 2→0 | `docs/judging/handoff.md:61–63` (live, run `5769706d`) |
| 5 | The first calibration pass caught a bug in our evidence builder | `docs/judging/handoff.md:55` |
| 5 | α = 0.50, 95% CI 0.12–0.67, 7 runs | `docs/judging/handoff.md:116` (0.502) |
| 5 | Human experts' α ≈ 0.56 in the paper Clay shared (GRA) | `docs/judging/paper-notes.md:17` |
| 6 | Before: FAILED, no answer, $1.50 | `docs/console-polish/handoff.md:39` (run `fdacf7cf`) |
| 6 | After: 85.4 High, 0 errors, 15/15, 8/8, $0.81 | `docs/console-polish/handoff.md:38` (run `a5670c6b`) |
| 6 | "Northern California" resolved to a 20 m building in San Francisco | `docs/judging/handoff.md:110` (run `c251934d`) |
| 6 | The LGND token lives 300 s, and every call after 290 s failed | `docs/console-polish/handoff.md:50` |
| 6 | Narrowed searches (16 km circles) were widened to all of Texas | `docs/console-polish/spec.md`, problem 3 |
| 7 | Strands on Bedrock AgentCore; Sonnet 5.5 or Kimi K3; RODA and LGND Geo over MCP; OTel to S3; FastAPI console; CDK | `README.md`, "How it works" and "Decisions" |
| 7 | The exporter is swapped by config, proved in CI | `README.md:45` and `README.md:129` |
| 7 | ADB's rubric is one YAML file | `docs/judging/guide.md`, "To use ADB's rubric" |
| 7 | Replays work offline from the trace | `README.md` ("Reports work offline"); `docs/tile-cache/handoff.md:24` (31/31 tiles from the archive with every provider blocked) |
| 8 | Checks claims against the tool output, not the world; no answer key yet | `docs/judging/gaps.md`; `docs/factory.md`, "Open work" |
| 8 | Next steps: answer key, ADB rubric, expert ratings, plain-language verdicts, prompt compliance | `docs/factory.md` ("Open work" and "Slices open for the team") |

**Costs for Q&A** (not on a slide):
- **Judging:** $0.10–0.31 per run with the tribunal: run `3d7ac12a` cost $0.10 (`docs/judging/handoff.md`, "Tribunal of three") and `a5670c6b` cost $0.31.
- **The agent:** in our runs, India cost $0.32 (`docs/example-cards/handoff.md`) and Texas $0.81.
