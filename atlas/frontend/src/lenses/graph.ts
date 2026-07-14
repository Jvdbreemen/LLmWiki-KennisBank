// Graph lens (TASK-27.4): canvas force-graph with data-driven encoding, a
// legend, colour-mode + status/kind filters, and click-to-inspect. Nodes are
// coloured by community (default; user preference), sized by importance/degree,
// ringed by lifecycle status, and haloed by usage warmth. Encoding lives in the
// unit-tested encoding.ts so the field->channel mapping is verifiable.
import ForceGraph from "force-graph";

import type { DataClient, Graph, GraphNode } from "../data-client";
import { clear, el } from "../dom";
import {
  type ColorMode,
  entryPointColor,
  type GraphFilter,
  nodeColor,
  nodeVal,
  passesFilter,
  provenanceColor,
  statusColor,
  warmthHalo,
} from "../encoding";
import { openInspect } from "../inspect";
import { currentGeneration, isCurrent, onLensLeave } from "../lifecycle";

// Above this node count the graph drops per-node halo/ring detail (LOD) to keep
// pan/zoom smooth; the omission is surfaced in the controls, never silent.
const LOD_NODES = 400;

function legend(colorMode: ColorMode | "provenance" | "entry-points"): HTMLElement {
  const items: [string, string][] =
    colorMode === "status"
      ? [["#58d68d", "current"], ["#f5b041", "unverified"], ["#8a90a0", "superseded"], ["#ec7063", "quarantined"]]
      : colorMode === "kind"
        ? [["#4f9cf9", "wiki"], ["#f5a623", "memory"]]
        : colorMode === "provenance"
          ? [["#58d68d", "gesourcet (herkomst resolveert)"], ["#ec7063", "at-risk (geen/dode herkomst)"]]
          : colorMode === "entry-points"
            ? [["#3a3f4a", "blinde vlek (0 memory-ingangen)"], ["#4f9cf9", "veel ingangen (agent vindt dit)"]]
            : [["#4f9cf9", "community-cluster (kleur = cluster)"], ["#f5a623", "memory"]];
  const row = el("div", { class: "legend" }, [el("span", { class: "muted" }, ["kleur: "])]);
  for (const [c, label] of items) {
    const sw = el("span", { class: "swatch" }, []);
    sw.style.background = c;
    row.appendChild(sw);
    row.appendChild(document.createTextNode(label + "  "));
  }
  row.appendChild(el("span", { class: "muted" }, ["· grootte = importance/degree · ring = status · halo = warmth"]));
  return row;
}

export async function renderGraphLens(host: HTMLElement, client: DataClient): Promise<void> {
  const gen = currentGeneration();
  clear(host);
  host.appendChild(el("div", { class: "loading" }, ["graaf laden…"]));
  let data: Graph;
  try {
    data = await client.graph();
  } catch (e) {
    clear(host);
    host.appendChild(el("div", { class: "error" }, [`graaf onbeschikbaar: ${(e as Error).message}`]));
    return;
  }
  // provenance overlay data (at-risk = unsourced per kb-lint); fail-soft.
  const atRisk = new Set<string>();
  try {
    for (const u of (await client.provenance()).unsourced) atRisk.add(u.path);
  } catch { /* overlay simply shows nothing at-risk */ }
  if (!isCurrent(gen)) return; // user switched lenses during the awaits
  if (data.status === "empty" || data.nodes.length === 0) {
    clear(host);
    host.appendChild(el("div", { class: "empty" }, ["geen graaf-data (bron niet beschikbaar)"]));
    return;
  }

  let colorMode: ColorMode | "provenance" | "entry-points" = "community";
  let atRiskOnly = false;
  const filter: GraphFilter = { hideSuperseded: false, kinds: new Set(["wiki", "memory"]) };

  // entry-point counts (TASK-27.14) are loaded lazily on first "entry-points"
  // select, because the first /memory-links call may take ~47s (then cached).
  let entryCounts: Record<string, number> | null = null;
  let maxEntry = 0;

  const colorFor = (node: GraphNode): string => {
    if (colorMode === "provenance") return provenanceColor(atRisk.has(node.id));
    if (colorMode === "entry-points") {
      return entryCounts ? entryPointColor(entryCounts[node.id] ?? 0, maxEntry) : "#3a3f4a";
    }
    return nodeColor(node, colorMode);
  };

  clear(host);

  // controls
  const modeSel = document.createElement("select");
  for (const m of ["community", "status", "kind", "provenance", "entry-points"]) {
    const o = document.createElement("option");
    o.value = m; o.textContent = `kleur: ${m}`;
    modeSel.appendChild(o);
  }
  const supCb = document.createElement("input");
  supCb.type = "checkbox";
  const supLabel = el("label", {}, [supCb, "verberg superseded"]);
  const riskCb = document.createElement("input");
  riskCb.type = "checkbox";
  const riskLabel = el("label", {}, [riskCb, "toon alleen at-risk (geen herkomst)"]);
  const memCb = document.createElement("input");
  memCb.type = "checkbox";
  const memLabel = el("label", {}, [memCb, "toon memory-fragmenten (nodes)"]);
  const lodNote = el("span", { class: "muted" }, []);
  const legendBox = el("div", { class: "legend-box" }, [legend(colorMode)]);
  const controls = el("div", { class: "graph-controls" }, [modeSel, supLabel, riskLabel, memLabel, lodNote, legendBox]);
  const canvas = el("div", { class: "graph-canvas" });
  host.appendChild(el("div", { class: "graph-wrap" }, [controls, canvas]));

  const graph = new ForceGraph(canvas)
    .nodeId("id")
    .nodeLabel((n: object) => {
      const node = n as GraphNode;
      const c = node.community_name ? ` · ${node.community_name}` : "";
      return `${node.label} — ${node.kind}, ${node.node_status}, links ${node.degree}, warmth ${node.warmth}${c}`;
    })
    .nodeCanvasObject((n: object, ctx: CanvasRenderingContext2D) => {
      const node = n as GraphNode & { x: number; y: number };
      // Level-of-detail: above LOD_NODES, drop the per-node halo and status ring
      // (the expensive per-frame extras) so pan/zoom stays smooth on large graphs.
      const lite = data.nodes.length > LOD_NODES;
      const r = Math.sqrt(nodeVal(node)) * 1.8;
      if (!lite) {
        const halo = warmthHalo(node);
        if (halo > 0) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, r + halo, 0, 2 * Math.PI);
          ctx.fillStyle = "rgba(245,166,35,0.12)";
          ctx.fill();
        }
      }
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = colorFor(node);
      ctx.fill();
      if (!lite && node.node_status !== "current" && node.node_status !== "active") {
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = statusColor(node.node_status);
        ctx.stroke();
      }
    })
    .onNodeClick((n: object) => void openInspect(client, (n as GraphNode).id))
    .linkColor(() => "rgba(160,160,160,0.22)")
    .backgroundColor("#0f1117")
    .cooldownTicks(120)
    .onEngineStop(() => graph.pauseAnimation());

  const apply = () => {
    const nodes = data.nodes.filter(
      (n) => passesFilter(n, filter) && (!atRiskOnly || atRisk.has(n.id)),
    );
    const ids = new Set(nodes.map((n) => n.id));
    const links = data.links.filter((l) => ids.has(l.source) && ids.has(l.target));
    graph.graphData({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) });
    graph.resumeAnimation();
    lodNote.textContent = nodes.length > LOD_NODES
      ? `LOD aan (${nodes.length} nodes; halo/ring uit voor snelheid)` : "";
  };

  modeSel.addEventListener("change", async () => {
    colorMode = modeSel.value as ColorMode | "provenance" | "entry-points";
    clear(legendBox);
    legendBox.appendChild(legend(colorMode));
    if (colorMode === "entry-points" && entryCounts === null) {
      legendBox.appendChild(el("span", { class: "muted" }, [" · ingangen laden (kan even duren)…"]));
      try {
        const ml = await client.memoryLinks();
        entryCounts = ml.counts ?? {};
        maxEntry = Math.max(0, ...Object.values(entryCounts));
      } catch { entryCounts = {}; }
      if (!isCurrent(gen)) return;
      clear(legendBox);
      legendBox.appendChild(legend(colorMode));
      apply(); // repaint with entry-point colours
    }
  });
  supCb.addEventListener("change", () => {
    filter.hideSuperseded = supCb.checked;
    apply();
  });
  riskCb.addEventListener("change", () => {
    atRiskOnly = riskCb.checked;
    apply();
  });
  memCb.addEventListener("change", async () => {
    memCb.disabled = true;
    clear(legendBox);
    legendBox.appendChild(el("span", { class: "muted" }, [
      memCb.checked ? "memory-fragmenten laden (kan even duren)…" : "graaf herladen…"]));
    try {
      const g = await client.graph(memCb.checked);
      if (!isCurrent(gen)) return;
      data = g;
      apply();
    } catch { /* keep current graph on failure */ }
    memCb.disabled = false;
    clear(legendBox);
    legendBox.appendChild(legend(colorMode));
  });

  const resize = () => graph.width(canvas.clientWidth).height(canvas.clientHeight);
  resize();
  window.addEventListener("resize", resize);
  onLensLeave(() => {
    window.removeEventListener("resize", resize);
    graph.pauseAnimation();
    graph.graphData({ nodes: [], links: [] });
  });
  apply();
}
