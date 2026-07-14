// Memory Health lens (27.6): the editor-in-chief cockpit for the memory layer.
// Lifecycle counts, the unverified quarantine queue, an importance x recency
// heatmap, warm/stale usage, and supersede chains — every row links back to the
// source memory file. Operationalises "the system proposes, the human decides".
import type { DataClient, MemoryHealth } from "../data-client";
import { AGE_BUCKETS, ageBucket } from "../encoding";
import { clear, el, withLoader } from "../dom";
import { openInspect } from "../inspect";

const memPath = (id: string) => `09-memory/${id}.md`;

function tile(label: string, value: number, cls: string): HTMLElement {
  return el("div", { class: `tile ${cls}` }, [
    el("div", { class: "tile-value" }, [String(value)]),
    el("div", { class: "tile-label" }, [label]),
  ]);
}

const TEMP_CLASS: Record<string, string> = { warm: "t-warm", tepid: "t-tepid", stale: "t-stale" };

function heatmap(cells: MemoryHealth["heatmap"]): HTMLElement {
  // grid[importance 1..5][bucket 0..3] = count
  const grid: number[][] = Array.from({ length: 5 }, () => [0, 0, 0, 0]);
  let max = 1;
  for (const c of cells) {
    const imp = Math.min(5, Math.max(1, c.importance));
    const b = ageBucket(c.age_days);
    grid[imp - 1][b] += 1;
    max = Math.max(max, grid[imp - 1][b]);
  }
  const table = el("div", { class: "heatmap" });
  // header row
  table.appendChild(el("div", { class: "hm-corner" }, ["imp \\ leeftijd"]));
  for (const b of AGE_BUCKETS) table.appendChild(el("div", { class: "hm-head" }, [b]));
  for (let imp = 5; imp >= 1; imp--) {
    table.appendChild(el("div", { class: "hm-row" }, [`imp ${imp}`]));
    for (let b = 0; b < 4; b++) {
      const n = grid[imp - 1][b];
      const cell = el("div", { class: "hm-cell", title: `importance ${imp}, ${AGE_BUCKETS[b]}: ${n}` }, [n ? String(n) : ""]);
      cell.style.background = n ? `rgba(79,156,249,${(0.15 + 0.85 * (n / max)).toFixed(2)})` : "#12151d";
      table.appendChild(cell);
    }
  }
  return table;
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
      tile("unverified", d.counts.unverified, "warn"),
      tile("superseded", d.counts.superseded, "muted"),
      tile("quarantined", d.counts.quarantined, "error"),
    ]);

    // quarantine queue: unverified memories awaiting a human decision. The
    // label opens the fragment; ✓/✗ call the sidecar's single write path
    // (frontmatter status -> current/retracted) and the row reflects it.
    const queue = el("ul", { class: "list" });
    if (d.queue.length === 0) {
      queue.appendChild(el("li", { class: "muted" }, ["niets in quarantaine — alles geverifieerd"]));
    }
    for (const q of d.queue.slice(0, 30)) {
      const label = el("span", { class: "clickable" }, [`imp ${q.importance} · ${q.id}${q.created ? ` · ${q.created}` : ""}`]);
      label.addEventListener("click", () => void openInspect(client, memPath(q.id)));
      const approve = el("button", { class: "decide approve", title: "goedkeuren → status current" }, ["✓"]) as HTMLButtonElement;
      const reject = el("button", { class: "decide reject", title: "afwijzen → status retracted" }, ["✗"]) as HTMLButtonElement;
      const li = el("li", { class: "queue-item" }, [approve, reject, label]);
      const decide = async (decision: "approve" | "reject") => {
        approve.disabled = reject.disabled = true;
        try {
          const r = await client.decideMemory(q.id, decision);
          li.replaceChildren(el("span", { class: "muted" }, [`${q.id} → ${r.new_status}`]));
        } catch (e) {
          approve.disabled = reject.disabled = false;
          li.appendChild(el("span", { class: "error" }, [` mislukt: ${(e as Error).message}`]));
        }
      };
      approve.addEventListener("click", () => void decide("approve"));
      reject.addEventListener("click", () => void decide("reject"));
      queue.appendChild(li);
    }

    const warm = el("ul", { class: "list" });
    for (const w of d.warmth.slice(0, 15)) {
      const badge = el("span", { class: `temp ${TEMP_CLASS[w.temperature] ?? ""}` }, [w.temperature]);
      const li = el("li", { class: "clickable" }, [badge, ` ${w.warmth.toFixed(0)}× · ${w.path}${w.last_used ? ` · ${w.last_used}` : ""}`]);
      // The sidecar resolves warmth stems to real doc paths (wiki or memory);
      // only fall back to the memory dir for a bare, unresolved stem.
      li.addEventListener("click", () => void openInspect(client, w.path.includes("/") ? w.path : memPath(w.path)));
      warm.appendChild(li);
    }

    // supersede chains: each existing target opens its fragment; targets whose
    // file is gone render muted with a marker instead of a dead link.
    const chains = el("ul", { class: "list" });
    for (const c of d.supersede_chains.slice(0, 15)) {
      const li = el("li", {});
      c.chain.forEach((stem, i) => {
        if (i > 0) li.appendChild(document.createTextNode(" → "));
        if ((c.missing ?? []).includes(stem)) {
          li.appendChild(el("span", { class: "muted", title: "fragment bestaat niet meer" }, [`${stem} (ontbreekt)`]));
        } else {
          const link = el("span", { class: "clickable chain-link" }, [stem]);
          link.addEventListener("click", () => void openInspect(client, memPath(stem)));
          li.appendChild(link);
        }
      });
      if (c.valid_until) li.appendChild(document.createTextNode(` (tot ${c.valid_until})`));
      chains.appendChild(li);
    }

    clear(host);
    host.appendChild(el("div", { class: "lens-pad scroll" }, [
      el("h2", {}, ["Memory Health — cockpit"]),
      tiles,
      el("h3", {}, [`Quarantaine-queue (${d.counts.unverified} unverified — mens beslist)`]),
      queue,
      el("h3", {}, ["Importance × recency (aantal active memories)"]),
      heatmap(d.heatmap),
      el("h3", {}, [`Warm / stale (top 15 van ${d.warmth.length})`]),
      warm,
      el("h3", {}, [`Supersede-ketens (${d.supersede_chains.length})`]),
      chains,
    ]));
  });
}
