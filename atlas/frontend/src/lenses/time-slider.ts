// Time-slider lens (27.5): the graph filtered by a valid-as-of instant. Bi-
// temporal nodes (memory) carry valid_from/valid_until; wiki nodes are atemporal
// and always shown. Filtering is client-side over the /graph payload.
import ForceGraph from "force-graph";

import { communityColor } from "../colors";
import type { DataClient, Graph, GraphNode } from "../data-client";
import { clear, el, withLoader } from "../dom";
import { openInspect } from "../inspect";
import { onLensLeave } from "../lifecycle";

const nodeColor = (n: GraphNode): string =>
  n.kind === "memory" ? "#f5a623" : communityColor(n.community as number | null);

export function renderTimeSliderLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Graph>(host, "graaf laden…", () => client.graph(), (data) => {
    if (data.status === "empty" || data.nodes.length === 0) {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen graaf-data"]));
      return;
    }

    // capture-time axis: wiki uses `created`, memory falls back to valid_from.
    const timeOf = (n: GraphNode): string | null =>
      (n.created as string | null) ?? (n.valid_from as string | null) ?? null;
    const dated = data.nodes
      .map((n) => { const t = timeOf(n); return t ? Date.parse(t) : NaN; })
      .filter((t) => !Number.isNaN(t));
    const hasTemporal = dated.length > 0;
    const minT = hasTemporal ? Math.min(...dated) : Date.now();
    const maxT = hasTemporal ? Math.max(...dated) : Date.now();

    clear(host);
    const canvas = el("div", { class: "graph-canvas" });
    const label = el("span", { class: "slider-label" }, ["valid-as-of: nu"]);
    const slider = el("input", { type: "range" }) as HTMLInputElement;
    slider.min = "0";
    slider.max = "1000";
    slider.value = "1000";
    slider.disabled = !hasTemporal;

    const note = hasTemporal
      ? `capture-tijd over ${dated.length} nodes (wiki=created, memory=valid_from)`
      : "geen tijd-metadata op nodes; slider inactief";

    host.appendChild(el("div", { class: "slider-bar" }, [label, slider, el("span", { class: "muted" }, [note])]));
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
      const nodes = data.nodes.filter((n) => {
        const t = timeOf(n);
        if (!t) return true; // no capture time known: always visible
        return Date.parse(t) <= asOf;
      });
      const ids = new Set(nodes.map((n) => n.id));
      const links = data.links.filter((l) => ids.has(l.source) && ids.has(l.target));
      graph.graphData({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) });
    };

    slider.addEventListener("input", () => {
      const frac = Number(slider.value) / 1000;
      const asOf = minT + frac * (maxT - minT);
      label.textContent = `valid-as-of: ${new Date(asOf).toISOString().slice(0, 10)}`;
      apply(asOf);
    });

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
