# Presentation

Team Foundry (Team 46): Aditya Pasarti · Farhan Shahriar · Uday Kandi · Miguel Pereira

| File | What it is |
| --- | --- |
| [`deck.html`](deck.html) | The deck: 11 slides, one self-contained file (no internet needed) |
| [`deck.pdf`](deck.pdf) | The same deck as a PDF, for the judges and as a backup |
| [`demo.md`](demo.md) | The 2-minute live demo (judging an existing run), its pre-flight checklist and fallbacks |
| [`claims.md`](claims.md) | Every number in the deck, with its source in the repo |
| [`one-pager.md`](one-pager.md) | A plain-language explainer for ADB and Clay |
| [`qa.md`](qa.md) | Likely questions, with short sourced answers |
| [`spec.md`](spec.md) | What this slice set out to deliver |
| [`handoff.md`](handoff.md) | What's ready, what's verified, and what's left (rehearsal) |

## Presenting the deck
Open `deck.html` in Chrome or Safari.

| Key | Does |
| --- | --- |
| → , space, Enter, click | Next. On slide 4, each press reveals the next step first |
| ← , Backspace | Back |
| `F` | Full screen |
| `N` | Presenter notes, with a timer that starts the first time you press it |
| Home / End | First or last slide |

A slide's number is in the URL (`deck.html#4`), so a reload stays put.

**The demo link** on slide 3 opens the console at `http://127.0.0.1:8787`, so the console must be running (see `demo.md`).

## Regenerating the PDF
Run this after editing `deck.html`:
```sh
uv run --no-project --with playwright python -c "
from playwright.sync_api import sync_playwright; import pathlib
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1600, 'height': 900})
    pg.goto(pathlib.Path('docs/presentation/deck.html').resolve().as_uri())
    pg.pdf(path='docs/presentation/deck.pdf', width='1600px', height='900px', print_background=True); b.close()"
```

## Timing (target about 8¼ minutes plus Q&A)
| Slide | Topic | Time |
| --- | --- | --- |
| 1 | The problem, and the team | 0:30 |
| 2 | Our idea: Record, Verify, Judge | 0:40 |
| 3 | **Live:** judging a dataset | 2:00 |
| 4 | How the score works | 0:50 |
| 5 | Proof: calibration and agreement | 0:45 |
| 6 | A human in the loop: experts correct the judges, and the judges learn | 0:45 |
| 7 | It caught our own bugs | 0:45 |
| 8 | Built to plug in | 0:30 |
| 9 | Architecture on AWS | 0:45 |
| 10 | Limits and next steps | 0:30 |
| 11 | Thank you: the team, then questions | 0:15 |
