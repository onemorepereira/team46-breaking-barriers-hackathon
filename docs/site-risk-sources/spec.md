# Hazard Source Registry: Spec

**Roadmap:** H1 · **Track:** Standard · **Product stage:** Introduction · **Status:** Specified · **Last updated:** 2026-11-05
**Depends on:** none. [R9](../adb-deployment-profile/spec.md) (the ADB profile) uses the registry's commercial flag once both exist.
**Size:** about 2 days

## Problem
ADB, and any developer, may ask: "should we build housing, power plants, solar or wind farms, or schools in this area, or is the risk of natural and man-made disasters too high?" **[team]** An agent can answer only from hazard and exposure data. The open sources come with licences that range from public domain to non-commercial ([catalog](catalog.md)) **[ext]**.

ADB's outputs must exclude non-commercial data (report Table 1, §7.4) **[ext]**. Today our licence checks know only imagery and reference sets (`analysis/licences.py`, `analysis/reference.py` `BAD_LICENCE_RE`). An agent given hazard tools could put CC BY-NC flood extents into an ADB answer, and nothing would flag it **[team]**.

## Users
- **Primary:** whoever adds a hazard source to the agent's tools ([H2](../hazard-tools/spec.md)). They need to know whether it may be used, and how to credit it.
- **Secondary:** ADB legal, who sign off the list; the judges and report, which show each run's sources.

## Goals
- Every hazard or exposure source an agent can reach has a registry entry: its licence, licence family, commercial verdict, attribution text, version and date checked.
- A source with no entry, or an unclear licence, can't be used in a run under `profile: adb`.
- The [catalog](catalog.md) and the registry agree, and a test keeps them in step.

## Non-goals
- **Hosting or downloading data.** That's H2.
- **Legal advice.** The registry records what the publisher's page says; ADB legal decides.
- **Licences of software engines** (CLIMADA, OpenQuake). Their copyleft is a build-time question for [H5](../expected-annual-loss/spec.md).

## Acceptance criteria
- [ ] **AC1 Registry.** `tools/hazard/sources.yaml` lists each source with these fields:
  - `id`, `name`, `publisher`, `version`;
  - `licence` (its exact name) and `licence_url`;
  - `family`: `public_domain`, `cc0`, `cc_by`, `share_alike`, `non_commercial`, `proprietary` or `unclear`;
  - `commercial`: `yes`, `conditional` or `no`;
  - `attribution`: the credit line;
  - `checked` (a date) and `checked_by`;
  - `notes`: conflicts or conditions.

  It holds every source in the catalog.
- [ ] **AC2 Loader.** `tools.hazard.registry.load()` refuses an entry with a missing field or an unknown family, naming the source and the field.
- [ ] **AC3 Consistency.** A test fails if a catalog row has no registry entry, or if the two disagree on the commercial verdict.
- [ ] **AC4 Gate.** `analysis/licences.py` adds each hazard source a run used to the run's licence list. Under `profile: adb` ([R9](../adb-deployment-profile/spec.md)), a source whose family is `non_commercial`, `proprietary` or `unclear` makes the run not presentable, and the source is named. Without R9, the source is listed with a warning.
- [ ] **AC5 Conflicts recorded.** JRC flood (ODbL or CC BY) and World Bank CCKP (CC BY or ODbL) are entered as `share_alike` until the publisher confirms otherwise, and the entry's note quotes both statements.
- [ ] **AC6 Re-check.** `harness hazard-sources check` fetches each `licence_url` and lists the ones that fail, or whose page changed since `checked`. It is run once, and the output is recorded in the handoff.

## Success signals
- **Metric (coverage):**
  - **numerator:** hazard tool calls in runs whose source has a registry entry;
  - **denominator:** all hazard tool calls;
  - **target:** 100%.
- **Metric (clean answers):** runs under `profile: adb` that use a non-commercial source and are still marked presentable. **Target:** 0.

## Constraints
- **Repo:** share-alike and non-commercial data stays out of the repo (`references/README.md`). The registry holds metadata only.
- **Dated checks:** licences change. The catalog's 2026-11-05 check is the baseline.

## What exists today
- **Licence lists per run:** `analysis/licences.py` (imagery, references, judges).
- **The non-commercial pattern for reference sets:** `analysis/reference.py` `BAD_LICENCE_RE`.
- **The catalog:** [catalog.md](catalog.md), checked 2026-11-05.

## Assumptions and open questions
- **Open:** does ADB hold hazard or exposure layers it can share (for example from the Disaster Risk Analytics Explorer)? *Owner:* Miguel, who asks Clay and ADB. *Default:* none until they say so.
- **Open:** which JRC flood licence applies? *Owner:* Miguel, who asks JRC. *Default:* treated as share-alike.
- **Open:** are Global Energy Monitor's "commercial exemption" terms acceptable? *Owner:* team. *Default:* `unclear`, so it's blocked under `adb`.
- **Assumption:** US federal data with no licence statement (IBTrACS, NOAA Storm Events, FEMA) is public domain, recorded as `public_domain` with a note saying it was assumed.
