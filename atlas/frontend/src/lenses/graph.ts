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
  type GraphFilter,
  nodeColor,
  nodeVal,
  passesFilter,
  provenanceColor,
  statusColor,
  warmthHalo,
} from "../encoding";
import { openInspect } from "../inspect";
import { onLensLeave } from "../lifecycle";

function legend(colorMode: ColorMode | "provenance"): HTMLElement {
  const items: [string, string][] =
    colorMode === "status"
      ? [["#58d68d", "current"], ["#f5b041", "unverified"], ["#8a90a0", "superseded"], ["#ec7063", "quarantined"]]
      : colorMode === "kind"
        ? [["#4f9cf9", "wiki"], ["#f5a623", "memory"]]
        : colorMode === "provenance"
          ? [["#58d68d", "gesourcet (herkomst resolveert)"], ["#ec7063", "at-risk (geen/dode herkomst)"]]
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
  if (data.status === "empty" || data.nodes.length === 0) {
    clear(host);
    host.appendChild(el("div", { class: "empty" }, ["geen graaf-data (bron niet beschikbaar)"]));
    return;
  }

  let colorMode: ColorMode | "provenance" = "community";
  let atRiskOnly = false;
  const filter: GraphFilter = { hideSuperseded: false, kinds: new Set(["wiki", "memory"]) };

  const colorFor = (node: GraphNode): string =>
    colorMode === "provenance"
      ? provenanceColor(atRisk.has(node.id))
      : nodeColor(node, colorMode);

  clear(host);

  // controls
  const modeSel = document.createElement("select");
  for (const m of ["community", "status", "kind", "provenance"]) {
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
  const legendBox = el("div", { class: "legend-box" }, [legend(colorMode)]);
  const controls = el("div", { class: "graph-controls" }, [modeSel, supLabel, riskLabel, legendBox]);
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
      const r = Math.sqrt(nodeVal(node)) * 1.8;
      const halo = warmthHalo(node);
      if (halo > 0) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + halo, 0, 2 * Math.PI);
        ctx.fillStyle = "rgba(245,166,35,0.12)";
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = colorFor(node);
      ctx.fill();
      if (node.node_status !== "current" && node.node_status !== "active") {
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
  };

  modeSel.addEventListener("change", () => {
    colorMode = modeSel.value as ColorMode | "provenance";
    clear(legendBox);
    legendBox.appendChild(legend(colorMode));
  });
  supCb.addEventListener("change", () => {
    filter.hideSuperseded = supCb.checked;
    apply();
  });
  riskCb.addEventListener("change", () => {
    atRiskOnly = riskCb.checked;
    apply();
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
