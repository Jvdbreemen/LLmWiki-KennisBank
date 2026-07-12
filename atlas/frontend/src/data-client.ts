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
  timeline(): Promise<unknown> { return this.get("/timeline?bucket=week"); }
  memoryHealth(): Promise<unknown> { return this.get("/memory-health"); }
  provenance(): Promise<unknown> { return this.get("/provenance"); }
  recall(q: string, k = 5): Promise<unknown> {
    return this.get(`/recall?q=${encodeURIComponent(q)}&k=${k}`);
  }
}
