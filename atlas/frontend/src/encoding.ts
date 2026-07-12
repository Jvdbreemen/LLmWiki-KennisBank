// Data-driven visual encoding for the Graph lens (TASK-27.4). Pure functions so
// the mapping (field -> visual channel) is unit-tested against known nodes,
// giving data-parity without a live browser.
import { communityColor } from "./colors";
import type { GraphNode } from "./data-client";

export type ColorMode = "community" | "status" | "kind";

const STATUS_COLOR: Record<string, string> = {
  current: "#58d68d",
  active: "#58d68d",
  unverified: "#f5b041",
  superseded: "#8a90a0",
  quarantined: "#ec7063",
};

const KIND_COLOR: Record<string, string> = { wiki: "#4f9cf9", memory: "#f5a623" };

export function statusColor(status: string): string {
  return STATUS_COLOR[status] ?? "#8a90a0";
}

// Provenance overlay colour: at-risk (no/dead herkomst per kb-lint) vs sourced.
export function provenanceColor(atRisk: boolean): string {
  return atRisk ? "#ec7063" : "#58d68d";
}

// Node colour by the selected channel. Community is the default (clusters read
// at a glance); status/kind are alternates surfaced via the legend toggle.
export function nodeColor(node: GraphNode, mode: ColorMode): string {
  if (mode === "status") return statusColor(node.node_status);
  if (mode === "kind") return KIND_COLOR[node.kind] ?? "#8a90a0";
  return node.kind === "memory"
    ? KIND_COLOR.memory
    : communityColor(node.community as number | null);
}

// Node size: importance drives memory nodes (1-5), degree drives wiki nodes
// (link centrality), warmth adds a usage bump. Monotonic in each input.
export function nodeVal(node: GraphNode): number {
  const structural = node.kind === "memory"
    ? Number(node.importance ?? 0)
    : Math.min(Number(node.degree ?? 0), 24) * 0.6;
  const warmth = Number(node.warmth ?? 0) * 0.4;
  return 1 + structural + warmth;
}

// Halo radius (extra ring) from usage warmth; 0 = no halo.
export function warmthHalo(node: GraphNode): number {
  return Math.min(Number(node.warmth ?? 0), 10) * 0.8;
}

export interface GraphFilter {
  hideSuperseded: boolean;
  kinds: Set<string>; // which kinds to show, e.g. {"wiki","memory"}
}

export function passesFilter(node: GraphNode, f: GraphFilter): boolean {
  if (f.hideSuperseded && node.node_status === "superseded") return false;
  if (!f.kinds.has(node.kind)) return false;
  return true;
}
