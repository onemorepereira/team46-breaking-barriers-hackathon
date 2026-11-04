# Presentation: Handoff (first version, for Miguel to edit and present)

**What's ready** (branch `feature/presentation-deck`, 2026-11-04):
- `deck.html`, 8 slides;
- `deck.pdf`;
- `demo.md`, the judging-only script with pre-flight and fallbacks;
- `claims.md`, every deck number with its source;
- `one-pager.md`;
- `qa.md`, 12 questions;
- `README.md`, how to present, the keys and timing.

The team name, the logo and all four members are on the title slide, the closing slide, the one-pager, the presentation README and the main README.

**Verification:**
- [x] **AC1 Deck.** Rendered in headless Chromium at 1600×900, slide by slide (slide 4 both unrevealed and fully revealed):
  - 0 page errors, and 0 elements overflowing any slide (slide 4 overflowed at first, so its copy was tightened);
  - `N` shows the notes and timer;
  - the only links are to the local console's three demo runs, all of which returned HTTP 200 on the running console. There's no CDN, and the logo is inlined;
  - the print style exports an 8-page PDF (`deck.pdf`).
- [ ] **AC2 Every claim sourced.** `claims.md` maps each deck number to a repo file and line. **Still to do:** a teammate checks the list against the files.
- [x] **AC3 Demo script:** `demo.md`, with timed steps, the lines to say, pre-flight and fallbacks, built around **Judge again** on run `a5670c6b`. Not yet rehearsed live (AC6).
- [x] **AC4 One-pager:** `one-pager.md`, in plain language, including what the evaluator doesn't prove yet.
- [x] **AC5 Q&A:** `qa.md`, 12 questions covering every topic the spec lists, each answer sourced.
- [ ] **AC6 Rehearsed:** a team dry run, with timings and fixes logged in `demo.md`. **Owner: Miguel.**

**Also in this change:** the README test count was corrected (151 to 157), and the team line was added to the main README.

**Risks:**
- The re-judged score will differ slightly from 85.4. `demo.md` gives the line to say.
- The Texas run lives in S3, so fresh AWS credentials are needed on the laptop. The India run is the local backup.
- The deck counts only merged slices as shipped (the freeze rule in `spec.md`). Plain-language verdicts and prompt compliance appear as "next".
