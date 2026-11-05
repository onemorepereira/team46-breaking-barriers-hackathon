# Demo Script: Judging a Dataset the Agent Already Built

**Length:** about 2 minutes, on slide 3. **Laptop:** Miguel's (the runs live in his archive). **Rule:** the demo judges an existing run; it never builds one.

## Pre-flight (do this within the hour before the slot)
- [ ] Source fresh AWS sandbox credentials in the terminal that runs the console (they expire every few hours), and check with `aws sts get-caller-identity`.
- [ ] Start the console with `uv run harness ui`, open http://127.0.0.1:8787, and leave it running. **Don't restart it during the talk.**
- [ ] Open three tabs and let their maps load. All three runs are in S3, so the console needs AWS credentials:
  - Pecos County solar, `79c18997-d5c2-4b29-a8c6-af45558c76ca` (the live demo; Sonnet on AgentCore, 2026-11-05; tied to the USGS reference; judged 99.4, High, with its visual verdicts archived);
  - Kathmandu substations, `5f830bdc-ff04-4556-86ff-aee04e807fe6` (contrast: 38.3; the agent found nothing it could stand behind and said so);
  - Jodhpur solar parks, `e18447dc-ca18-4f54-90eb-c6d99f073e3c` (backup).
- [ ] Test one **Re-judge** on the Jodhpur run, about $0.22 for the three-pass panel plus a few cents for the visual check. That warms Bedrock and proves the credentials.
- [ ] The Pecos run's visual verdicts are already archived (5 / 5 seen), so the live re-judge makes no image calls. Don't re-judge it beforehand unless you want to check the score; it was 99.4 on 2026-11-05.
- [ ] Open `docs/presentation/deck.html` in a full-screen browser window (press `F`), with the browser zoom at 100%.
- [ ] Projector check: the deck fits the screen, and the console is readable (zoom it to 110–125% if needed).

## The walkthrough (with what to say)
| Time | Do | Say | The audience sees |
| --- | --- | --- | --- |
| 0:00 | On slide 3, click **Judge this run live** | "An agent already built this dataset: the solar farms in Pecos County, Texas. Is it trustworthy?" | The Pecos run: the prompt, sites inside the county boundary |
| 0:10 | Click **Re-judge** | "Three judges from three companies start now. Note 'Mistral seated for Opus': Sonnet built this, so Anthropic's judge doesn't grade it." | The judge panel with three spinners |
| 0:15 | Scroll to the **Claims** table, then point at the map | "This part isn't opinion. Code checked all 5 claims against the exact tool output they cite, all 5 are inside the county, and a vision model saw a solar farm in a sharp open image of each one." | 5 rows marked matched, inside; pins on the map; visual confirmation 5/5 in the scorecard |
| 0:45 | Back to the scorecard as verdicts land | "Each judge's score arrives as it finishes. Every judge votes three times at once, the score is the average of all those votes, and the confidence says how far they agree." | Three scores near 99, high confidence |
| 1:10 | Scroll to **Against the reference** | "Now the question judges can't answer: what did it miss? USGS lists 12 solar farms in this county. The agent found 5." Point at the red farms on the map | Site recall 0.42, precision 1.0; missed farms in red |
| 1:40 | Switch to the Kathmandu tab | "And when the agent can't find anything it can stand behind, it says so, and the score shows it: 38.3." | 38.3, no sites |
| 2:00 | Back to the deck | "So, how does that score work?" Then on to slide 4 | — |

**Say this if the score differs from 99.4** (it may, a little): "It moves a bit every time. That's exactly why we report confidence, not just a number."

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
