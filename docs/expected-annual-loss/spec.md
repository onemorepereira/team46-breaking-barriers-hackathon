# Expected Annual Loss: Spec

**Roadmap:** H5 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** [H2](../hazard-tools/spec.md), [H3](../site-screening-task/spec.md).
**Size:** about 5 to 7 days

## Problem
A hazard level ("100-year flood depth 0.8 m") says how likely and how strong an event is, not what it would cost. Investors and ADB's disaster risk finance work in losses: expected annual loss (EAL) and the loss at a return period (report Table 5, disaster risk finance) **[ext]**.

CLIMADA, an open engine from ETH Zürich, computes EAL for any area. It has tropical-cyclone hazard built on IBTrACS and synthetic tracks ([catalog](../site-risk-sources/catalog.md#engines-that-tie-the-data-together)) **[ext]**. It is GPL-3.0, so linking it into our code has licence consequences **[ext]**.

## Users
- **Primary:** ADB disaster risk finance and investors comparing places by expected loss.
- **Secondary:** the evaluator, which checks loss numbers in answers.

## Goals
- The agent can ask for EAL and the 100-year loss for an asset of a given type and value at a place, for tropical cyclone first.
- The figures are reproducible: same inputs, same CLIMADA version, same result.
- Our code's licence is unaffected.

## Non-goals
- **Earthquake loss.** OpenQuake is AGPL-3.0, and GEM's global models are non-commercial, so it waits on H2's seismic question.
- **Portfolio or insurance pricing.**
- **Calibrating vulnerability curves.** CLIMADA's published defaults are used and named.

## Acceptance criteria
- [ ] **AC1 Separate service.** CLIMADA runs as its own process (a container in the AgentCore stack, or a local process), called over HTTP or MCP. Our code doesn't import it. The design records why: GPL-3.0 copyleft applies to linking, and a separate service avoids it. The design cites the GPL FAQ for that boundary.
- [ ] **AC2 Tool.** `loss_at(lat, lon | area, asset_type, value_usd, hazard="tropical_cyclone")` returns:
  - EAL in USD and as a share of value;
  - the loss at return periods 10, 50, 100 and 250 years;
  - the hazard set (STORM or IBTrACS-based) and its version;
  - the impact function's name and source;
  - the CLIMADA version.
- [ ] **AC3 Reproducible.** The same call returns the same numbers twice, and a test pins a known answer on a fixture.
- [ ] **AC4 Cross-check.** At the five H2 live places, the cyclone EAL ratio is compared with GIRI's published infrastructure AAL for the country (CC BY 3.0 IGO). The ratio and any difference above a factor of 3 are recorded in the handoff.
- [ ] **AC5 Answer.** The H3 answer gains an optional `losses` block. The H4 provenance check covers its numbers.
- [ ] **AC6 Speed.** A point loss call returns within 30 s. Longer calls are refused with a message, not left to time out.

## Success signals
- **Metric (grounded losses):**
  - **numerator:** loss figures in answers that match a `loss_at` result;
  - **denominator:** all loss figures in answers;
  - **target:** 100%.

## Constraints
- **Licence:** GPL-3.0 for CLIMADA; its data API products carry their own licences, checked against H1.
- **Compute:** CLIMADA's global cyclone sets are large. The design states memory and time per call, measured.

## What exists today
- None. This is new.

## Assumptions and open questions
- **Open:** is a separate service enough to keep GPL obligations off our code? *Owner:* team, who records the reading in the design. *Default:* yes, with CLIMADA unmodified and called over a network boundary.
- **Open:** which hazard after cyclone? *Owner:* ADB. *Default:* river flood, from Aqueduct depths with JRC depth-damage curves, if the curves' licence is clean.
