// Wordcloud lens (27.13): the vault's concepts sized by importance, where
// importance = how much links to an article (graph degree) plus how often it is
// used (kb-usage warmth). A human editor sees at a glance what the knowledge
// base is "about". MVP: a flex tag-cloud (no layout lib) — deliberately simple
// and dependency-light after the mermaid/hljs freezes.
import { communityColor } from "../colors";
import type { DataClient, Graph, GraphNode } from "../data-client";
import { clear, el, withLoader } from "../dom";
import { openInspect } from "../inspect";

const MIN_PX = 12;
const MAX_PX = 52;
const TOP_N = 150; // cap terms so the cloud stays readable

function weightOf(n: GraphNode): number {
  // degree dominates (structure), warmth adds usage signal.
  return n.degree + Number(n.warmth ?? 0) * 1.5;
}

function labelOf(n: GraphNode): string {
  return n.label.replace(/\.md$/, "");
}

export function renderWordcloudLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Graph>(host, "wordcloud laden…", () => client.graph(), (data) => {
    const nodes = data.nodes.filter((n) => weightOf(n) > 0);
    if (data.status === "empty" || nodes.length === 0) {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen kennis-data voor de wordcloud"]));
      return;
    }

    const top = nodes.sort((a, b) => weightOf(b) - weightOf(a)).slice(0, TOP_N);
    const maxW = weightOf(top[0]);
    const minW = weightOf(top[top.length - 1]);
    const span = Math.max(1, maxW - minW);
    // shuffle deterministically (by id hash) so sizes aren't sorted into a wedge
    top.sort((a, b) => (a.id < b.id ? -1 : 1));

    const cloud = el("div", { class: "cloud" });
    for (const n of top) {
      const w = weightOf(n);
      const px = MIN_PX + Math.sqrt((w - minW) / span) * (MAX_PX - MIN_PX);
      const term = el("span", {
        class: "cloud-term clickable",
        title: `${labelOf(n)} — links ${n.degree}, warmth ${n.warmth ?? 0}`,
      }, [labelOf(n)]);
      term.style.fontSize = `${px.toFixed(1)}px`;
      term.style.color = n.kind === "memory" ? "#f5a623" : communityColor(n.community as number | null);
      term.addEventListener("click", () => void openInspect(client, n.id));
      cloud.appendChild(term);
    }

    clear(host);
    host.appendChild(el("div", { class: "lens-pad scroll" }, [
      el("h2", {}, ["Wordcloud — belang via links + gebruik"]),
      el("div", { class: "muted" }, [`top ${top.length} concepten · grootte = degree + warmth · kleur = community`]),
      cloud,
    ]));
  });
}
