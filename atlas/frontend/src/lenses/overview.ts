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

// Activiteits-heatmap (TASK-91 F1, idee uit Pratiyush/llm-wiki): één cel per
// dag, intensiteit in vijf stappen. De data komt als dag-aggregaat uit de
// sidecar (één SQL GROUP BY) — hier alleen nog DOM, O(dagen) en O(1) met
// vaultgrootte. Geen canvas, geen graaf: dit is de niet-grafische ingang.
function heatmapStrip(buckets: { day: string; n: number }[], days = 182): HTMLElement {
  const byDay = new Map(buckets.map((b) => [b.day, b.n]));
  const max = Math.max(1, ...buckets.map((b) => b.n));
  const wrap = el("div", { class: "heatmap" });
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today.getTime() - i * 86400000);
    const iso = d.toISOString().slice(0, 10);
    const n = byDay.get(iso) ?? 0;
    const q = n === 0 ? 0 : Math.min(4, 1 + Math.floor((3 * n) / max));
    const cell = el("span", { class: `heat q${q}`, title: `${iso}: ${n} event(s)` });
    wrap.appendChild(cell);
  }
  return wrap;
}

function freshnessLine(f: { d7: number; d30: number; d90: number; older: number; unknown: number }): string {
  return `vers (<=7d): ${f.d7} · <=30d: ${f.d30} · <=90d: ${f.d90} · ouder: ${f.older}` +
    (f.unknown ? ` · zonder datum: ${f.unknown}` : "");
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
      el("h3", {}, ["Activiteit (laatste ~6 maanden)"]),
      d.heatmap && d.heatmap.length
        ? heatmapStrip(d.heatmap)
        : el("p", { class: "muted" }, ["geen activity-data (kb-activity.db ontbreekt of oudere sidecar)"]),
      el("h3", {}, ["Wiki"]),
      el("p", {}, [`${d.wiki.total} artikelen: ${statusRow(d.wiki.by_status)}`]),
      ...(d.freshness ? [el("p", { class: "muted" }, [freshnessLine(d.freshness)])] : []),
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
