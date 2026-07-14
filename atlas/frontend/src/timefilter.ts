// Bi-temporal valid-as-of filter for the Time-slider (TASK-27.5). Pure and
// deterministic (as-of is passed in, never read from a clock) so the semantics
// are unit-tested independently of the renderer.
//
// - "valid" axis  = when a fact was TRUE: visible iff valid_from <= asOf and
//   (valid_until absent OR valid_until > asOf). valid_until is EXCLUSIVE.
// - "capture" axis = when the system KNEW it: visible iff created <= asOf.
// A node with no date on the chosen axis is atemporal and always visible.

export type TimeAxis = "valid" | "capture";

export interface TemporalNode {
  valid_from?: string | null;
  valid_until?: string | null;
  created?: string | null;
}

function ms(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

export function visibleAsOf(node: TemporalNode, asOf: number, axis: TimeAxis): boolean {
  if (axis === "capture") {
    const c = ms(node.created);
    return c === null || c <= asOf;
  }
  // valid axis
  const start = ms(node.valid_from) ?? ms(node.created);
  if (start !== null && start > asOf) return false;      // not yet valid
  const end = ms(node.valid_until);
  if (end !== null && end <= asOf) return false;          // valid_until exclusive
  return true;
}
