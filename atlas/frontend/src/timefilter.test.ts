import { describe, expect, it } from "vitest";

import { type TemporalNode, visibleAsOf } from "./timefilter";

const at = (iso: string) => Date.parse(iso);

describe("visibleAsOf — valid axis boundaries", () => {
  const node: TemporalNode = { valid_from: "2026-07-01", valid_until: "2026-07-10" };

  it("== valid_from is inclusive (visible)", () => {
    expect(visibleAsOf(node, at("2026-07-01"), "valid")).toBe(true);
  });
  it("before valid_from is hidden", () => {
    expect(visibleAsOf(node, at("2026-06-30"), "valid")).toBe(false);
  });
  it("== valid_until is exclusive (hidden)", () => {
    expect(visibleAsOf(node, at("2026-07-10"), "valid")).toBe(false);
  });
  it("just inside the window is visible", () => {
    expect(visibleAsOf(node, at("2026-07-09"), "valid")).toBe(true);
  });
  it("open-ended (no valid_until) stays valid after valid_from", () => {
    const open: TemporalNode = { valid_from: "2026-07-01" };
    expect(visibleAsOf(open, at("2030-01-01"), "valid")).toBe(true);
  });
  it("atemporal node (no dates) is always visible", () => {
    expect(visibleAsOf({}, at("2000-01-01"), "valid")).toBe(true);
  });
});

describe("visibleAsOf — capture axis", () => {
  const node: TemporalNode = { created: "2026-07-05" };
  it("hidden before it was captured", () => {
    expect(visibleAsOf(node, at("2026-07-04"), "capture")).toBe(false);
  });
  it("visible once captured", () => {
    expect(visibleAsOf(node, at("2026-07-05"), "capture")).toBe(true);
  });
});

describe("visibleAsOf — bi-temporal difference (late import)", () => {
  // A fact TRUE since 2020 but only captured in 2026.
  const node: TemporalNode = { valid_from: "2020-01-01", created: "2026-07-01" };
  it("at 2021 it is valid but not yet captured — the two axes differ", () => {
    expect(visibleAsOf(node, at("2021-01-01"), "valid")).toBe(true);
    expect(visibleAsOf(node, at("2021-01-01"), "capture")).toBe(false);
  });
});
