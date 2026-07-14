// Overzicht lens (TASK-27.18): one health page over the whole vault. Replaces
// the Provenance lens (its coverage shrank to a single line here) and answers
// "hoe staat de kennisbank ervoor?" at a glance: wiki, memory, raw input,
// inbox backlog, and graph freshness.
import type { DataClient, Overview } from "../data-client";
import { clear, el, withLoader } from "../dom";

function tile(label: string, value: string, cls = ""): HTMLElement {
  return el("div", { class: `tile ${cls}` }, [
    el("div", { class: "tile-value" }, [value]),
    el("div", { class: "tile-label" }, [label]),
  ]);
}

function statusRow(byStatus: Record<string, number>): string {
  return Object.entries(byStatus)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${v} ${k}`)
    .join(" · ") || "geen";
}

export function renderOverviewLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Overview>(host, "overzicht laden…", () => client.overview(), (d) => {
    const provPct = d.provenance.total
      ? Math.round((100 * d.provenance.sourced) / d.provenance.total)
      : 0;
    clear(host);
    host.appendChild(el("div", { class: "lens-pad scroll" }, [
      el("h2", {}, ["Overzicht — KennisBank health"]),
      el("div", { class: "tiles" }, [
        tile("wiki-artikelen", String(d.wiki.total), "ok"),
        tile("memories actief", String(d.memory.active), "ok"),
        tile("wacht op beslissing", String(d.memory.unverified), d.memory.unverified ? "warn" : "muted"),
        tile("inbox (input waiting)", String(d.inbox_waiting), d.inbox_waiting ? "warn" : "muted"),
      ]),
      el("h3", {}, ["Wiki"]),
      el("p", {}, [`${d.wiki.total} artikelen: ${statusRow(d.wiki.by_status)}`]),
      el("h3", {}, ["Memory"]),
      el("p", {}, [
        `${d.memory.active} actief · ${d.memory.unverified} unverified (beslis in Memory Health) · ` +
        `${d.memory.superseded} superseded · ${d.memory.quarantined} quarantined`,
      ]),
      el("h3", {}, ["Raw input"]),
      el("p", {}, [`${d.raw.sessies} sessielogs · ${d.raw.transcripts} transcripts in 01-raw/`]),
      el("h3", {}, ["Signalen"]),
      el("ul", { class: "list" }, [
        el("li", {}, [`herkomst: ${d.provenance.sourced}/${d.provenance.total} wiki-artikelen (${provPct}%)`]),
        el("li", {}, [d.graph_stale
          ? "graph is stale — draai /graphify voor een verse kaart"
          : "graph is up-to-date"]),
        el("li", {}, [d.inbox_waiting
          ? `${d.inbox_waiting} item(s) in 00-inbox — draai /intake`
          : "inbox leeg"]),
      ]),
    ]));
  });
}
