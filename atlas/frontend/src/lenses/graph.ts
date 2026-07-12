// Graph lens: the canvas force-graph over /graph. force-graph (MIT, vasturiano)
// renders on canvas so it scales past the ~1000-node SVG ceiling the ADR names.
import ForceGraph from "force-graph";

import type { DataClient, Graph, GraphNode } from "../data-client";

const KIND_COLOR: Record<string, string> = {
  wiki: "#4f9cf9",
  memory: "#f5a623",
};

function message(el: HTMLElement, cls: string, text: string): void {
  el.replaceChildren();
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text; // textContent, never innerHTML: no injection surface
  el.appendChild(div);
}

export async function renderGraphLens(el: HTMLElement, client: DataClient): Promise<void> {
  message(el, "loading", "graaf laden…");
  let data: Graph;
  try {
    data = await client.graph();
  } catch (e) {
    message(el, "error", `graaf onbeschikbaar: ${(e as Error).message}`);
    return;
  }
  if (data.status === "empty" || data.nodes.length === 0) {
    message(el, "empty", "geen graaf-data (bron niet beschikbaar)");
    return;
  }

  el.replaceChildren();
  const graph = new ForceGraph(el)
    .graphData({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.links.map((l) => ({ ...l })),
    })
    .nodeId("id")
    .nodeLabel((n: object) => {
      const node = n as GraphNode;
      return `${node.label} (${node.kind}, ${node.node_status}, degree ${node.degree})`;
    })
    .nodeColor((n: object) => KIND_COLOR[(n as GraphNode).kind] ?? "#888")
    .nodeVal((n: object) => 1 + (n as GraphNode).degree)
    .linkColor(() => "rgba(160,160,160,0.25)")
    .backgroundColor("#0f1117");

  const resize = () => graph.width(el.clientWidth).height(el.clientHeight);
  resize();
  window.addEventListener("resize", resize);
}
