import { test } from "node:test";
import assert from "node:assert/strict";
import { basePath, candidatesOf, formatScore, reviewPayload } from "./api.ts";
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
