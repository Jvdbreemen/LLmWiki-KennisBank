// Time-slider lens (27.5): the graph filtered by a valid-as-of instant. Bi-
// temporal nodes (memory) carry valid_from/valid_until; wiki nodes are atemporal
// and always shown. Filtering is client-side over the /graph payload.
import ForceGraph from "force-graph";

import { communityColor } from "../colors";
import type { DataClient, Graph, GraphNode } from "../data-client";
import { clear, el, withLoader } from "../dom";
import { openInspect } from "../inspect";
import { onLensLeave } from "../lifecycle";
import { type TemporalNode, type TimeAxis, visibleAsOf } from "../timefilter";

const nodeColor = (n: GraphNode): string =>
  n.kind === "memory" ? "#f5a623" : communityColor(n.community as number | null);

export function renderTimeSliderLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Graph>(host, "graaf laden…", () => client.graph(), (data) => {
    if (data.status === "empty" || data.nodes.length === 0) {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen graaf-data"]));
      return;
    }

    let axis: TimeAxis = "capture";

    const anyDate = (n: GraphNode): number[] =>
      [n.created, (n as { valid_from?: string }).valid_from]
        .map((v) => (v ? Date.parse(String(v)) : NaN))
        .filter((t) => !Number.isNaN(t));
    const dated = data.nodes.flatMap(anyDate);
    const hasTemporal = dated.length > 0;
    const minT = hasTemporal ? Math.min(...dated) : Date.now();
    const maxT = hasTemporal ? Math.max(...dated) : Date.now();

    clear(host);
    const canvas = el("div", { class: "graph-canvas" });
    const label = el("span", { class: "slider-label" }, ["as-of: nu"]);
    const slider = el("input", { type: "range" }) as HTMLInputElement;
    slider.min = "0";
    slider.max = "1000";
    slider.value = "1000";
    slider.disabled = !hasTemporal;

    // axis toggle: capture-time (when known) vs valid-time (when true).
    const axisSel = document.createElement("select");
    for (const [v, t] of [["capture", "as: capture-tijd (wanneer bekend)"],
                          ["valid", "as: valid-tijd (wanneer waar)"]] as const) {
      const o = document.createElement("option");
      o.value = v; o.textContent = t;
      axisSel.appendChild(o);
    }

    const note = hasTemporal
      ? `${data.nodes.length} nodes · valid_until exclusief · sleep om te scrubben`
      : "geen tijd-metadata op nodes; slider inactief";

    host.appendChild(el("div", { class: "slider-bar" }, [axisSel, label, slider, el("span", { class: "muted" }, [note])]));
    host.appendChild(canvas);

    const graph = new ForceGraph(canvas)
      .nodeId("id")
      .nodeLabel((n: object) => (n as GraphNode).label)
      .nodeColor((n: object) => nodeColor(n as GraphNode))
      .nodeVal((n: object) => 1 + (n as GraphNode).degree)
      .onNodeClick((n: object) => void openInspect(client, (n as GraphNode).id))
      .linkColor(() => "rgba(160,160,160,0.25)")
      .backgroundColor("#0f1117")
      .cooldownTicks(120)
      .onEngineStop(() => graph.pauseAnimation());

    const apply = (asOf: number) => {
      const nodes = data.nodes.filter((n) => visibleAsOf(n as unknown as TemporalNode, asOf, axis));
      const ids = new Set(nodes.map((n) => n.id));
      const links = data.links.filter((l) => ids.has(l.source) && ids.has(l.target));
      graph.graphData({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) });
    };

    const asOfNow = () => minT + (Number(slider.value) / 1000) * (maxT - minT);
    const refresh = () => {
      const asOf = asOfNow();
      label.textContent = `as-of: ${new Date(asOf).toISOString().slice(0, 10)}`;
      apply(asOf);
    };
    slider.addEventListener("input", refresh);
    axisSel.addEventListener("change", () => { axis = axisSel.value as TimeAxis; refresh(); });

    const resize = () => graph.width(canvas.clientWidth).height(canvas.clientHeight);
    resize();
    window.addEventListener("resize", resize);
    onLensLeave(() => {
      window.removeEventListener("resize", resize);
      graph.pauseAnimation();
      graph.graphData({ nodes: [], links: [] });
    });
    apply(maxT);
  });
}
