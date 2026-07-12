// The single module that talks to the sidecar. The localhost-only invariant is
// enforced here in code: the base URL is always 127.0.0.1 on the negotiated
// port, and no other module issues network calls (ADR-0004 module boundaries).

export interface Health {
  status: string;
  version: string;
  vault: string;
  sources: Record<string, boolean>;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "wiki" | "memory";
  layer: string;
  node_status: string;
  degree: number;
  [k: string]: unknown;
}
export interface GraphLink { source: string; target: string; rel: string; weight: number; }
export interface Graph { status: string; nodes: GraphNode[]; links: GraphLink[]; }

export interface TimelineBucket {
  start: string; end: string;
  event_count: number; capture_count: number;
  by_kind: Record<string, number>;
}
export interface Timeline { status: string; buckets: TimelineBucket[]; }

export interface MemoryHealth {
  status: string;
  counts: { active: number; quarantined: number; superseded: number; unverified: number };
  supersede_chains: { head: string; chain: string[] }[];
  warmth: { path: string; warmth: number; last_used: string | null }[];
  quarantine: { id: string; reason: string }[];
}

export interface Provenance {
  status: string;
  coverage: { sourced: number; unsourced: number; total: number };
  unsourced: { path: string; reason: string }[];
}

export interface Doc { status: string; path: string; title: string; content: string; }

export interface RecallHit { path: string; score: number; snippet: string; }
export interface Recall {
  status: string; query: string;
  stages: Record<string, { path: string; score: number }[]>;
  final: RecallHit[];
}

function resolvePort(): number | null {
  // Tauri injects the sidecar port; in dev pass ?port=NNNN.
  const fromGlobal = (window as unknown as { __ATLAS_PORT__?: number }).__ATLAS_PORT__;
  if (typeof fromGlobal === "number") return fromGlobal;
  const p = new URLSearchParams(location.search).get("port");
  return p ? Number(p) : null;
}

export class DataClient {
  private readonly base: string | null;

  constructor(port: number | null = resolvePort()) {
    this.base = port ? `http://127.0.0.1:${port}` : null;
  }

  get configured(): boolean {
    return this.base !== null;
  }

  private async get<T>(path: string): Promise<T> {
    if (!this.base) throw new Error("no sidecar port; pass ?port=NNNN");
    // Hard guard: never allow a non-loopback base to slip through.
    if (!this.base.startsWith("http://127.0.0.1:")) {
      throw new Error(`refusing non-loopback base: ${this.base}`);
    }
    const resp = await fetch(this.base + path);
    if (!resp.ok) throw new Error(`${path} -> HTTP ${resp.status}`);
    return resp.json() as Promise<T>;
  }

  health(): Promise<Health> { return this.get<Health>("/health"); }
  graph(): Promise<Graph> { return this.get<Graph>("/graph"); }
  timeline(): Promise<Timeline> { return this.get<Timeline>("/timeline?bucket=week"); }
  memoryHealth(): Promise<MemoryHealth> { return this.get<MemoryHealth>("/memory-health"); }
  provenance(): Promise<Provenance> { return this.get<Provenance>("/provenance"); }
  recall(q: string, k = 5): Promise<Recall> {
    return this.get<Recall>(`/recall?q=${encodeURIComponent(q)}&k=${k}`);
  }
  doc(path: string): Promise<Doc> {
    return this.get<Doc>(`/doc?path=${encodeURIComponent(path)}`);
  }
  // Loopback URL for a vault image; <img src> loads it directly (no CORS issue
  // for image display). Returns null when no sidecar port is configured.
  assetUrl(path: string): string | null {
    return this.base ? `${this.base}/asset?path=${encodeURIComponent(path)}` : null;
  }
}
