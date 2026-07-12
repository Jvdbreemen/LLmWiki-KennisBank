// Provenance lens (27.9): kb-lint-style herkomst coverage over the wiki.
import type { DataClient, Provenance } from "../data-client";
import { clear, el, withLoader } from "../dom";

export function renderProvenanceLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<Provenance>(host, "provenance laden…", () => client.provenance(), (d) => {
    if (d.status === "empty") {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen wiki-data"]));
      return;
    }
    const pct = d.coverage.total ? Math.round((d.coverage.sourced / d.coverage.total) * 100) : 0;
    const bar = el("div", { class: "cov-bar" });
    const fill = el("div", { class: "cov-fill" });
    fill.style.width = `${pct}%`;
    bar.appendChild(fill);

    const list = el("ul", { class: "list" });
    for (const u of d.unsourced) {
      list.appendChild(el("li", { title: u.reason }, [u.path]));
    }

    clear(host);
    host.appendChild(el("div", { class: "lens-pad scroll" }, [
      el("h2", {}, ["Provenance-dekking"]),
      el("div", {}, [`${d.coverage.sourced} / ${d.coverage.total} wiki-artikelen met herkomst (${pct}%)`]),
      bar,
      el("h3", {}, [`Zonder herkomst (${d.coverage.unsourced})`]),
      list,
    ]));
  });
}
