import { describe, expect, it } from "vitest";

import type { GraphNode } from "./data-client";
import {
  type GraphFilter,
  nodeColor,
  nodeVal,
  passesFilter,
  provenanceColor,
  statusColor,
  warmthHalo,
} from "./encoding";

function node(over: Partial<GraphNode> = {}): GraphNode {
  return {
    id: "02-wiki/x.md", label: "x.md", kind: "wiki", layer: "wiki",
    node_status: "current", degree: 0, community: 0, warmth: 0, importance: 0,
    ...over,
  } as GraphNode;
}

describe("statusColor", () => {
  it("maps lifecycle status to a colour, unknown -> grey", () => {
    expect(statusColor("current")).toBe("#58d68d");
    expect(statusColor("unverified")).toBe("#f5b041");
    expect(statusColor("superseded")).toBe("#8a90a0");
    expect(statusColor("weird")).toBe("#8a90a0");
  });
});

describe("nodeColor", () => {
  it("uses status colour in status mode", () => {
    expect(nodeColor(node({ node_status: "unverified" }), "status")).toBe("#f5b041");
  });
  it("memory is always warm-hued in community mode", () => {
    expect(nodeColor(node({ kind: "memory", community: 3 }), "community")).toBe("#f5a623");
  });
});

describe("nodeVal", () => {
  it("grows with wiki degree", () => {
    expect(nodeVal(node({ degree: 10 }))).toBeGreaterThan(nodeVal(node({ degree: 1 })));
  });
  it("grows with memory importance", () => {
    const lo = nodeVal(node({ kind: "memory", importance: 1 }));
    const hi = nodeVal(node({ kind: "memory", importance: 5 }));
    expect(hi).toBeGreaterThan(lo);
  });
  it("grows with warmth", () => {
    expect(nodeVal(node({ warmth: 8 }))).toBeGreaterThan(nodeVal(node({ warmth: 0 })));
  });
});

describe("warmthHalo", () => {
  it("is zero without usage and positive with usage", () => {
    expect(warmthHalo(node({ warmth: 0 }))).toBe(0);
    expect(warmthHalo(node({ warmth: 5 }))).toBeGreaterThan(0);
  });
});

describe("provenanceColor", () => {
  it("at-risk is red, sourced is green", () => {
    expect(provenanceColor(true)).toBe("#ec7063");
    expect(provenanceColor(false)).toBe("#58d68d");
  });
});

describe("passesFilter", () => {
  const base: GraphFilter = { hideSuperseded: false, kinds: new Set(["wiki", "memory"]) };
  it("hides superseded when requested", () => {
    expect(passesFilter(node({ node_status: "superseded" }), { ...base, hideSuperseded: true })).toBe(false);
    expect(passesFilter(node({ node_status: "current" }), { ...base, hideSuperseded: true })).toBe(true);
  });
  it("hides kinds not in the set", () => {
    expect(passesFilter(node({ kind: "memory" }), { ...base, kinds: new Set(["wiki"]) })).toBe(false);
  });
});
