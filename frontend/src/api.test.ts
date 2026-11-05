import { test } from "node:test";
import assert from "node:assert/strict";
import {
  basePath,
  candidatesOf,
  chipFor,
  draftPayload,
  formatScore,
  reviewPayload,
  sectionIssues,
  visualCaption,
  weakCriterion,
} from "./api.ts";
test("API URLs preserve workshop authentication proxy and work on localhost", () => {
  assert.equal(basePath("/proxy/8787/workspace/"), "/proxy/8787");
  assert.equal(basePath("/workspace/"), "");
  assert.equal(basePath("/proxy/8787/workspace"), "\/proxy/8787");
});
test("map candidates use recorded coordinates, deduplicate and keep zero coordinates", () => {
  const point = (c: any) => ({
    geometry: { coordinates: c },
    properties: { claim: "site", ref: "T2", inside: false },
  });
  const view: any = {
    map: {
      claims: {
        features: [
          point([0, 0]),
          point([0, 0]),
          point([12, 24]),
          point([NaN, 0]),
        ],
      },
    },
  };
  const sites = candidatesOf(view);
  assert.equal(sites.length, 2);
  assert.equal(sites[0].lat, 0);
  assert.equal(sites[1].lat, 24);
  assert.equal(sites[0].inside, false);
});
test("missing scores do not become a false zero", () => {
  assert.equal(formatScore(null), "—");
  assert.equal(formatScore(0), "0");
  assert.equal(formatScore(87.5), "87.5");
  assert.equal(formatScore(87.54), "87.5");
  assert.equal(formatScore(100), "100");
});
test("review payload distinguishes agreeing from suggested scores and requires authors/reasons", () => {
  assert.deepEqual(
    reviewPayload(" Ada ", "grounding", "agree", "0", "note", "T1").criteria,
    { grounding: { agree: true } },
  );
  assert.deepEqual(
    reviewPayload(
      "Ada",
      "grounding",
      "disagree",
      "1",
      "needs evidence",
      "T1, T2",
    ).criteria,
    {
      grounding: {
        agree: false,
        score: 1,
        reason: "needs evidence",
        refs: ["T1", "T2"],
      },
    },
  );
  assert.throws(() => reviewPayload("", "grounding", "agree", "1", "", ""));
  assert.throws(() =>
    reviewPayload("Ada", "grounding", "disagree", "1", "", ""),
  );
  assert.throws(() => reviewPayload("Ada", "", "note", "1", "note", ""));
});
test("the base path is the part before the last /workspace segment", () => {
  assert.equal(basePath("/workspaces/team46/workspace/"), "/workspaces/team46");
  assert.equal(
    basePath("/proxy/8787/workspaces/x/workspace"),
    "/proxy/8787/workspaces/x",
  );
  assert.equal(basePath("/proxy/8787/runs"), "/proxy/8787");
  assert.equal(basePath("/runs"), "");
});
test("a suggested score must be a number: an empty or non-numeric score is refused, not saved as 0", () => {
  assert.throws(
    () => reviewPayload("Ada", "grounding", "disagree", "", "why", ""),
    /score/,
  );
  assert.throws(
    () => reviewPayload("Ada", "grounding", "disagree", "x", "why", ""),
    /score/,
  );
  assert.equal(
    (
      reviewPayload("Ada", "grounding", "disagree", "0", "why", "")
        .criteria as any
    ).grounding.score,
    0,
  );
});
test("candidates skip features with no geometry instead of throwing", () => {
  const view: any = {
    map: {
      claims: {
        features: [
          { geometry: null, properties: {} },
          { properties: {} },
          { geometry: { coordinates: [null, null] }, properties: {} },
          { geometry: { coordinates: [3, 4] }, properties: { claim: "ok" } },
        ],
      },
    },
  };
  const sites = candidatesOf(view);
  assert.equal(sites.length, 1);
  assert.equal(sites[0].id, 0);
  assert.equal(sites[0].name, "ok");
});
test("a location's imagery is the chip it names, else the nearest one within 300 m", () => {
  const chip = (node: string, lat: number, lon: number) => ({
    properties: { node, lat, lon },
  });
  const chips = [
    chip("naip/obs:2", 31, -103),
    chip("naip/obs:22", 31.001, -103),
  ];
  const at = (name: string, lat: number, lon: number): any => ({
    name,
    lat,
    lon,
  });
  assert.equal(chipFor(at("site (chip naip/obs:22)", 0, 0), chips), 1);
  assert.equal(
    chipFor(at("Solar park location (naip/obs:22)", 0, 0), chips),
    1,
  );
  assert.equal(chipFor(at("site", 31.0002, -103), chips), 0);
  assert.equal(chipFor(at("site", 31.1, -103), chips), -1);
  assert.equal(chipFor(at("site", 31, -103), []), -1);
});
test("one review covers several questions; each suggestion needs a score and a reason", () => {
  const p = draftPayload(" Ada ", {
    grounding: { decision: "agree", score: "", reason: "", refs: "" },
    efficiency: {
      decision: "disagree",
      score: "1",
      reason: "two repeat searches",
      refs: "T3 T4",
    },
  });
  assert.equal(p.reviewer, "Ada");
  assert.deepEqual(p.criteria, {
    grounding: { agree: true },
    efficiency: {
      agree: false,
      score: 1,
      reason: "two repeat searches",
      refs: ["T3", "T4"],
    },
  });
  assert.throws(() => draftPayload("Ada", {}), /at least one/);
  assert.throws(
    () =>
      draftPayload("", {
        g: { decision: "agree", score: "", reason: "", refs: "" },
      }),
    /name/,
  );
  assert.throws(
    () =>
      draftPayload("Ada", {
        g: { decision: "disagree", score: "1", reason: " ", refs: "" },
      }),
    /Explain/,
  );
});

test("visual check caption: score denominator, no verdicts, not run", () => {
  assert.equal(visualCaption(null), null);
  assert.equal(
    visualCaption({ status: "checked", sites: 3, seen: 1, checked: 3 }),
    "Visually checked: 1 of 3 sites seen",
  );
  assert.equal(
    visualCaption({ status: "checked", sites: 0, seen: 0, checked: 0 }),
    "Visual check: the answer listed no locations to check",
  );
  assert.equal(
    visualCaption({ status: "checked", sites: 2, seen: 0, checked: 0 }),
    "Visual check: no site could be confirmed or ruled out",
  );
  assert.equal(
    visualCaption({
      status: "not_checked",
      checked: 0,
      reason: "no eligible checker model",
    }),
    "Visual check not run: no eligible checker model",
  );
  assert.equal(
    visualCaption({
      status: "not_checked",
      sites: 2,
      seen: 1,
      checked: 1,
      reason: "no eligible checker model",
    }),
    "Visually checked: 1 of 1 sites seen",
  );
});

test("reported sites carry their visual verdict", () => {
  const view: any = {
    map: {
      claims: {
        features: [
          {
            geometry: { coordinates: [-96.5, 32.5] },
            properties: {
              claim: "site",
              ref: "T1",
              visual: { verdict: "absent" },
            },
          },
          {
            geometry: { coordinates: [-96.4, 32.5] },
            properties: { claim: "other", ref: "T1" },
          },
        ],
      },
    },
  };
  const c = candidatesOf(view);
  assert.equal(c[0].visual?.verdict, "absent");
  assert.equal(c[1].visual, null);
});

test("evaluation issues: each section's rule, and an unjudged run counts nothing", () => {
  const view: any = {
    kpis: { confidence: "Low", errors: 2 },
    scorecard: {
      criteria: [
        { id: "a", score: 100 },
        { id: "b", score: 83.3 },
        { id: "c", score: null },
        { id: "d", score: 75 },
      ],
      judges: [{ status: "ok" }, { status: "error" }],
      judges_in_doubt: false,
      gates: [{ id: "no_answer" }],
      failure_modes: [{ id: "overconfidence" }],
    },
    conditions: {
      status: "checked",
      rows: [
        { cells: [{ status: "supported" }, { status: "unverified" }] },
        { cells: [{ status: "contradicted" }] },
      ],
    },
    reference: { missed: ["r1", "r2", "r3"] },
    licences: { presentable: false, blockers: ["LGND Geo service"] },
  };
  assert.deepEqual(sectionIssues(view), {
    rubric: 2,
    conditions: 2,
    judges: 2,
    failures: 3,
    reference: 3,
    licences: 1,
  });
  assert.equal(weakCriterion({ score: 99.9 }), true);
  assert.equal(weakCriterion({ score: null }), false);
  const clean = sectionIssues({ kpis: {}, scorecard: null } as any);
  assert.ok(Object.values(clean).every((n) => n === 0));
  assert.equal(
    sectionIssues({
      kpis: {},
      scorecard: null,
      conditions: { status: "not_checked", rows: [] },
      licences: { presentable: false },
    } as any).licences,
    1,
  );
});
