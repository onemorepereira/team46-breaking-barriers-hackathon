# Slice: Presentation and Demo Materials

**Status:** Open · **Owner:** unassigned · **Size:** about a day · **Branch:** `slice/presentation` from `main` · **Deck freeze:** 2 hours before the presentation slot
**Read first:** the [README](../../README.md) (mission, what we built, verified results, and "How we win", which lists the four judging criteria), [the factory](../factory.md) (every effort and its status), the [factory rules for slices](../factory.md#how-to-take-a-slice).

## Problem
Tomorrow we present to the judges and to Clay and ADB. The work is spread across a README, seven feature records and a live console, and none of it is a story yet. We need a short deck, a demo that can't fail, and answers ready for the hard questions. Every number has to be true and traceable to the repo, because the judges include domain experts.

## What exists today (start here)
- **The pitch outline:** the README's "How we win" maps each of the four equally weighted judging criteria (Technological Implementation, Design, Potential Impact, Quality of Idea) to our answer **[event]**.
- **Results with evidence:**
  - README "Verified results";
  - `docs/judging/handoff.md` (the judges, agreement α, calibration);
  - `docs/console-polish/handoff.md` (the Texas parks run, before and after);
  - `docs/tile-cache/handoff.md` (offline replay);
  - `docs/example-cards/handoff.md`.
- **Demo assets:**
  - the console (`uv run harness ui`) with 16 one-click example prompts;
  - archived runs on **Miguel's machine** (see the open question below):
    - local archive, which replays offline: `a9a69e76` (India solar parks, 87.5 High), `53fd4e2a` (ZIP 75080), `b2bdb4d6` (a FAILED run, which shows that the evaluator says no);
    - S3 archive, which needs AWS: `a5670c6b` (Texas parks on AgentCore, 85.4 High).

## Open question (owner: Miguel; default applies until answered)
- **Where the demo runs live.** `archive/` and `out/` are git-ignored, so a fresh clone has no runs, and a teammate's own deployed stack starts with an empty archive. Committing a curated demo archive would also publish LGND Geo results from a commercial service, so check its terms first. **Default:** the demo runs on Miguel's machine. The slice owner writes the script against the run IDs above, using screenshots Miguel shares, and rehearses on Miguel's laptop.
- **What the briefs ask for:** `docs/Clay-Foundry-Vision-Hackathon.md`, e.g. the MVP success criteria near line 106, and the "recorded-trace fallback" near line 64.

## Acceptance criteria
- [ ] **AC1 A deck of 12 slides or fewer**, in any tool (Google Slides, Keynote, Canva, or Markdown slides), with a PDF export at `docs/presentation/deck.pdf` and the source or a share link in `docs/presentation/README.md`. The arc:
  1. the problem: can ADB trust a dataset an AI agent built?;
  2. what we built (one architecture slide naming Bedrock, AgentCore, Strands, MCP, OpenTelemetry, S3, the judge tribunal and the console);
  3. the live demo;
  4. results;
  5. limits and next steps.

  Each of the four judging criteria is answered visibly on at least one slide.
- [ ] **AC2 Every claim is sourced.** `docs/presentation/claims.md` lists each number or factual claim in the deck with the repo file and line it comes from (e.g. "α = 0.50, docs/judging/handoff.md"). Anything without a source is cut or marked as our opinion. A teammate checks the list against the files.
- [ ] **AC3 A demo script that can't fail.** `docs/presentation/demo.md` is a timed 5-minute walkthrough with exact clicks, prompts (from the example cards) and what the audience should see at each step. It includes:
  - **a pre-flight checklist**: fresh AWS credentials sourced, `harness ui` running, LGND login valid, a test run done within the hour, the browser zoomed for the projector;
  - **a fallback path**: if the network or a model fails, open the local-archive runs (IDs above) and replay them offline. The S3 run needs AWS credentials;
  - **a timing**: rehearse it at least once, end to end, and record how long it took.
- [ ] **AC4 A one-page explainer** (`docs/presentation/one-pager.md`, or a PDF) for ADB and Clay readers with no technical background: what the evaluator checks, how to read a score and its confidence, and what it does **not** prove yet (no answer key; it checks the agent's work against its own tool results).
- [ ] **AC5 Ready for hard questions.** `docs/presentation/qa.md` gives 10 or more likely questions with short answers sourced to the docs. Cover at least:
  - LLM judge bias and recusal;
  - why three judges;
  - what α 0.50 means;
  - what a run costs;
  - what's verified versus judged;
  - what happens when the area or the tools fail;
  - why AWS Bedrock;
  - how ADB's own rubric would plug in.
- [ ] **AC6 Rehearsed.** Do one full dry run with the team (deck, then demo, then 3 questions), and add the notes and fixes to `docs/presentation/README.md`.

## Non-goals and boundaries
- No code changes. If the demo exposes a bug, write it up as a new open row in [the factory](../factory.md) and tell Miguel. Don't fix it in this slice.
- Don't promise features that aren't built. **Freeze rule:** a slice counts as shipped in the deck only if it's merged to `main` with its handoff by the deck freeze (2 hours before the slot). Anything else is a "next step".
- Keep live runs for rehearsal modest (each costs $0.30–1.50 in Bedrock). Prefer the archived runs.

## How to check your work
```sh
uv run harness ui                      # rehearse against the real console
uv run harness replay a9a69e76-f4ae-49a8-b03c-e88682cdb60b   # offline fallback (on Miguel's machine): rebuild a report from the local archive
```

## When done
Write `docs/presentation/handoff.md` (what's ready, the rehearsal time, open risks), set Status to `Built`, update [the factory](../factory.md), and open a PR to `main`.
