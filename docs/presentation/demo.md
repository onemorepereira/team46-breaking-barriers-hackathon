# Demo Script: Judging a Dataset the Agent Already Built

**Length:** about 2 minutes, on slide 3. **Laptop:** Miguel's (the runs live in his archive). **Rule:** the demo judges an existing run; it never builds one.

## Pre-flight (do this within the hour before the slot)
- [ ] Source fresh AWS sandbox credentials in the terminal that runs the console (they expire every few hours), and check with `aws sts get-caller-identity`.
- [ ] Start the console with `uv run harness ui`, open http://127.0.0.1:8787, and leave it running. **Don't restart it during the talk.**
- [ ] Open three tabs and let their maps load:
  - Texas parks, `a5670c6b-542d-49dc-80ec-5448c6bd940c` (needs AWS: the run is in S3);
  - Laos, `b2bdb4d6-f79d-4b07-927b-045b0d496ca3` (FAILED, local);
  - India solar parks, `a9a69e76-f4ae-49a8-b03c-e88682cdb60b` (backup, local);
  - optional: California vineyards, `42b0a155-64e5-4539-9686-056dda4bc9dd` (reviewed and reconsidered; needs AWS).
- [ ] Test one **Judge again** on the India run, about $0.15. That warms Bedrock and proves the credentials.
- [ ] Open `docs/presentation/deck.html` in a full-screen browser window (press `F`), with the browser zoom at 100%.
- [ ] Projector check: the deck fits the screen, and the console is readable (zoom it to 110–125% if needed).

## The walkthrough (with what to say)
| Time | Do | Say | The audience sees |
| --- | --- | --- | --- |
| 0:00 | On slide 3, click **Judge this run live** | "An agent already built this dataset: data centers within 10 miles of Texas parks. Is it trustworthy?" | The Texas run: the prompt, the map with results inside the Texas boundary |
| 0:10 | Click **Judge again** | "Three judges from three companies start now. Note 'Mistral seated for Kimi': Kimi built this, so Kimi doesn't grade it." | The judge panel with three spinners |
| 0:15 | Scroll to the **Claims** table, then point at the map | "This part isn't opinion. Code checked all 15 claims against the exact tool output they cite, and all 8 sites are inside Texas." | 15 rows marked matched, inside; pins on the map |
| 0:45 | Back to the scorecard as verdicts land | "Each judge's score arrives as it finishes. The final score is the median, and the confidence says how far they agree." | Three scores, then the overall score and confidence |
| 1:15 | Click **Result relevance** in the scorecard | "Every vote comes with a reason, and points at the step it relied on." Click a step ref like `T3`. | Each judge's vote and rationale; the timeline scrolls to that tool call |
| 1:40 | Switch to the Laos tab | "And when the agent fails to deliver, here it ran out of budget with no answer, the evaluator says FAILED, whatever the judges think." | FAILED |
| 2:00 | Back to the deck | "So, how does that score work?" Then on to slide 4 | — |
| *(if ahead of time)* | On slide 3, **If time: a run an expert reviewed** | "Here an expert disagreed. The judges reconsidered, and one kept its vote and corrected the reviewer from the steps." Point at the badge and each judge's response | The "Revised after human review" badge, the original judgement, the judges' responses |

**Say this if the score differs from 85.4** (it will, a little): "It moves a bit every time. That's exactly why we report confidence, not just a number."

## If something fails
| Symptom | Do |
| --- | --- |
| Judging hangs past 90 s, or shows an error | Skip it: "Here's the judgement it already made." The page keeps the last verdict, so walk the scorecard as is |
| The Texas tab won't load (credentials or S3) | Use the India tab (local archive) for the same walkthrough |
| The console is down | Restart it with `uv run harness ui` (about 5 s), and keep talking over slide 4 meanwhile |
| No network at all | Local runs still open (India, Laos), but imagery tiles may be blank. Narrate the claims table and scorecard |

## Rehearsal log
| Date | Who | Time | Fixes |
| --- | --- | --- | --- |
| | | | |
