// Memory Health lens (27.6): lifecycle counts, warmth, supersede chains, quarantine.
import type { DataClient, MemoryHealth } from "../data-client";
import { clear, el, withLoader } from "../dom";

function tile(label: string, value: number, cls: string): HTMLElement {
  return el("div", { class: `tile ${cls}` }, [
    el("div", { class: "tile-value" }, [String(value)]),
    el("div", { class: "tile-label" }, [label]),
  ]);
}

export function renderMemoryHealthLens(host: HTMLElement, client: DataClient): Promise<void> {
  return withLoader<MemoryHealth>(host, "memory-health laden…", () => client.memoryHealth(), (d) => {
    if (d.status === "empty") {
      clear(host);
      host.appendChild(el("div", { class: "empty" }, ["geen memory-data"]));
      return;
    }
    const tiles = el("div", { class: "tiles" }, [
      tile("active", d.counts.active, "ok"),
      tile("superseded", d.counts.superseded, "muted"),
      tile("unverified", d.counts.unverified, "warn"),
      tile("quarantined", d.counts.quarantined, "error"),
    ]);

    const warm = el("ul", { class: "list" });
    for (const w of d.warmth.slice(0, 15)) {
      warm.appendChild(el("li", {}, [`${w.warmth.toFixed(0)}× · ${w.path}${w.last_used ? ` · ${w.last_used}` : ""}`]));
    }

    const chains = el("ul", { class: "list" });
    for (const c of d.supersede_chains.slice(0, 15)) {
      chains.appendChild(el("li", {}, [c.chain.join(" → ")]));
    }

    clear(host);
    host.appendChild(el("div", { class: "lens-pad scroll" }, [
      el("h2", {}, ["Memory Health"]),
      tiles,
      el("h3", {}, [`Warmste memories (top 15 van ${d.warmth.length})`]),
      warm,
      el("h3", {}, [`Supersede-ketens (${d.supersede_chains.length})`]),
      chains,
    ]));
  });
}
