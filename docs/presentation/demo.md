# Demo Script: Judging a Dataset the Agent Already Built

**Length:** about 2 minutes, on slide 3. **Laptop:** Miguel's (the runs live in his archive). **Rule:** the demo judges an existing run; it never builds one.

## Pre-flight (do this within the hour before the slot)
- [ ] Source fresh AWS sandbox credentials in the terminal that runs the console (they expire every few hours), and check with `aws sts get-caller-identity`.
- [ ] Start the console with `uv run harness ui`, open http://127.0.0.1:8787, and leave it running. **Don't restart it during the talk.**
- [ ] Open three tabs and let their maps load. All three runs are in S3, so the console needs AWS credentials:
  - Pecos County solar, `6d5e9d6b-72c5-437b-9771-f4a0253546f2` (the live demo; tied to the USGS reference);
  - Texas parks, `815fd905-5dd9-4dbb-a73c-d824c6824893` (FAILED: step limit, no answer);
  - Jodhpur solar parks, `36efccf9-63ea-45b2-84b2-9a7c9d57ea3f` (backup).
- [ ] Test one **Re-judge** on the Jodhpur run, about $0.22 for the three-pass panel plus a few cents for the visual check. That warms Bedrock and proves the credentials.
- [ ] **Re-judge the Pecos run once too.** Each judgement now also runs the visual check (a vision model looks at every reported site, up to a 60 s deadline), and its final verdicts are archived and reused, so the live re-judge then makes no image calls. Note the score it lands on: it includes `visual_confirmation` now, so it may differ from the 100 recorded on 2026-11-04.
- [ ] Open `docs/presentation/deck.html` in a full-screen browser window (press `F`), with the browser zoom at 100%.
- [ ] Projector check: the deck fits the screen, and the console is readable (zoom it to 110–125% if needed).

## The walkthrough (with what to say)
| Time | Do | Say | The audience sees |
| --- | --- | --- | --- |
| 0:00 | On slide 3, click **Judge this run live** | "An agent already built this dataset: the solar farms in Pecos County, Texas. Is it trustworthy?" | The Pecos run: the prompt, sites inside the county boundary |
| 0:10 | Click **Re-judge** | "Three judges from three companies start now. Note 'Mistral seated for Opus': Sonnet built this, so Anthropic's judge doesn't grade it." | The judge panel with three spinners |
| 0:15 | Scroll to the **Claims** table, then point at the map | "This part isn't opinion. Code checked all 14 claims against the exact tool output they cite, and all 14 are inside the county." | 14 rows marked matched, inside; pins on the map |
| 0:45 | Back to the scorecard as verdicts land | "Each judge's score arrives as it finishes. Every judge votes three times at once, the score is the average of all those votes, and the confidence says how far they agree." | Three scores near 100, high confidence |
| 1:10 | Scroll to **Against the reference** | "Now the question judges can't answer: what did it miss? USGS lists 12 solar farms in this county. The agent found 7." Point at the red farms on the map | Site recall 0.58, precision 1.0; missed farms in red |
| 1:40 | Switch to the Texas parks tab | "And when the agent fails to deliver, here it hit its step limit with no answer, the evaluator says FAILED, whatever the judges think." | FAILED |
| 2:00 | Back to the deck | "So, how does that score work?" Then on to slide 4 | — |

**Say this if the score differs from 100** (it may, a little): "It moves a bit every time. That's exactly why we report confidence, not just a number."

## If something fails
| Symptom | Do |
| --- | --- |
| Judging hangs past 90 s (it usually takes about 20 s), or shows an error | Skip it: "Here's the judgement it already made." The page keeps the last verdict, so walk the scorecard as is |
| The Pecos tab won't load (credentials or S3) | Refresh the credentials; meanwhile use the Jodhpur tab for the same walkthrough (without the reference card) |
| The console is down | Restart it with `uv run harness ui` (about 5 s), and keep talking over slide 4 meanwhile |
| No network at all | The demo runs are in S3, so they won't open. Use the deck's slides 4–8 and `deck.pdf`, and narrate the numbers from this script |

## Rehearsal log
| Date | Who | Time | Fixes |
| --- | --- | --- | --- |
| | | | |
