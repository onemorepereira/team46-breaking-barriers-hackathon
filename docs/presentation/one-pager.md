# Team Foundry: Can You Trust a Dataset an AI Agent Built?

**Team Foundry (Team 46):** Aditya Pasarti · Farhan Shahriar · Uday Kandi · Miguel Pereira
**Clay Earth Dataset Foundry hackathon, Track 1 (ADB agentic eval)**

## The problem
AI agents can now build geospatial datasets on request: "find the solar parks in this district", "map the flooded farmland". But a program officer can't tell whether to trust the result. Did the agent search the right place? Are its sites real results from its tools, or guesses? Clay calls evaluating these agentic workflows its number one unmet need.

## What we built
An evaluator that judges **the work, not just the answer**.
1. **Record:** every step the agent takes (each search, each image check, each decision) is saved as evidence.
2. **Verify:** every site the agent reports must point to the tool result it came from. A program checks that the value really is there, and that the site is inside the area that was asked for.
3. **Judge:** three AI judges from three different companies score what a program can't: did it use the right tools, are the results what was asked for, and is it honest about uncertainty? Each vote comes with a reason and points at the step it relied on.

## How to read a score
- **Score, 0 to 100:** how well the work was done, combining the program's checks with the judges' votes (the middle vote of three counts).
- **Confidence (High, Medium or Low):** how far the judges agree, and whether the record of the run is complete. It tells you how much weight to put on the score.
- **FAILED:** the agent never delivered an answer, or none of its tools worked. No score can hide that.

## Why you can rely on it
- **We sabotaged runs on purpose:** searches with no area, a made-up site, a missing answer. Each time, the evaluator lowered exactly the right part of the score.
- **The judges agree about as well as human experts do** in a published study on this kind of task (agreement 0.50, against 0.56 for experts).
- **It caught bugs in our own system.** Once, a place name was matched to a single building, so every search came back empty; once, a sign-in expired mid-run. The evidence showed exactly what went wrong. After the fixes, a run that had failed scored 85 out of 100 with high confidence.

## Experts stay in charge
An expert can review any score, criterion by criterion. The judges then reconsider against the evidence. They don't simply obey: in our test, a judge rejected a deliberately wrong review and pointed to the steps that disproved it. Reviews also become short lessons for the judges. Each lesson is tested on runs it wasn't drawn from, approved by a person, and kept per deployment, so ADB's judges learn from ADB's experts.

## What it doesn't prove yet
It checks the agent against **its own evidence**, not against the real world. Confirming that a site really is a data center needs a reference list (an "answer key"), and ADB's own scoring rules. Both plug in without rebuilding the system: ADB's rubric is a single file.

## What it costs
About $0.30–0.80 for the agent and $0.10–0.30 for the judges, per run.
