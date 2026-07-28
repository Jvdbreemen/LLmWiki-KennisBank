// Cmd+K command palette (TASK-91 F2): jump to a lens or open a document.
// The title index is fetched ONCE per session (prebuilt in kb-index.db, served
// by /titles) and filtered client-side — no live query per keystroke, no graph
// dependency. Pure filtering lives in fuzzyFilter so vitest can pin it.
import type { DataClient, TitleItem } from "./data-client";
import { el } from "./dom";

export interface PaletteEntry {
  kind: "lens" | "doc";
  key: string; // lens key of vault-relatief pad
  title: string;
  layer?: string;
}

// All query tokens must appear as substrings (title or key); rank by earliest
// match position, then by title length (shorter = more specific), then alpha.
export function fuzzyFilter(entries: PaletteEntry[], query: string, limit = 12): PaletteEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return entries.slice(0, limit);
  const tokens = q.split(/\s+/);
  const scored: { e: PaletteEntry; pos: number }[] = [];
  for (const e of entries) {
    const hay = `${e.title} ${e.key}`.toLowerCase();
    let worst = -1;
    let ok = true;
    for (const t of tokens) {
      const i = hay.indexOf(t);
      if (i < 0) { ok = false; break; }
      worst = Math.max(worst, i);
    }
    if (ok) scored.push({ e, pos: worst });
  }
  scored.sort((a, b) =>
    a.pos - b.pos ||
    a.e.title.length - b.e.title.length ||
    a.e.title.localeCompare(b.e.title));
  return scored.map((s) => s.e).slice(0, limit);
}

interface PaletteActions {
  selectLens: (key: string) => void;
  openDoc: (path: string) => void;
}

let titlesCache: TitleItem[] | null = null;

export function installPalette(client: DataClient, lenses: { key: string; label: string }[],
                               actions: PaletteActions): void {
  let overlay: HTMLElement | null = null;

  const close = () => { overlay?.remove(); overlay = null; };

  const open = async () => {
    if (overlay) { close(); return; }
    const input = el("input", { class: "palette-input", type: "text",
                                placeholder: "spring naar lens of document…" }) as HTMLInputElement;
    const list = el("div", { class: "palette-list" });
    const box = el("div", { class: "palette-box" }, [input, list]);
    overlay = el("div", { class: "palette-overlay" }, [box]);
    overlay.addEventListener("click", (ev) => { if (ev.target === overlay) close(); });
    document.body.appendChild(overlay);
    input.focus();

    const lensEntries: PaletteEntry[] = lenses.map((l) => (
      { kind: "lens", key: l.key, title: l.label } as PaletteEntry));
    if (titlesCache === null) {
      try {
        titlesCache = (await client.titles()).items;
      } catch {
        titlesCache = []; // sidecar zonder /titles: palet blijft lens-only
      }
    }
    const docEntries: PaletteEntry[] = titlesCache.map((t) => (
      { kind: "doc", key: t.path, title: t.title, layer: t.layer } as PaletteEntry));
    const all = [...lensEntries, ...docEntries];

    let selected = 0;
    let current: PaletteEntry[] = [];
    const activate = (e: PaletteEntry) => {
      close();
      if (e.kind === "lens") actions.selectLens(e.key);
      else actions.openDoc(e.key);
    };
    const rerender = () => {
      current = fuzzyFilter(all, input.value);
      list.replaceChildren();
      current.forEach((e, i) => {
        const tag = e.kind === "lens" ? "lens" : (e.layer || "doc");
        const row = el("div", { class: `palette-row${i === selected ? " active" : ""}` }, [
          el("span", { class: "palette-tag" }, [tag]),
          el("span", {}, [e.title]),
        ]);
        row.addEventListener("click", () => activate(e));
        list.appendChild(row);
      });
    };
    input.addEventListener("input", () => { selected = 0; rerender(); });
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") { close(); }
      else if (ev.key === "ArrowDown") { selected = Math.min(selected + 1, current.length - 1); rerender(); ev.preventDefault(); }
      else if (ev.key === "ArrowUp") { selected = Math.max(selected - 1, 0); rerender(); ev.preventDefault(); }
      else if (ev.key === "Enter" && current[selected]) { activate(current[selected]); }
    });
    rerender();
  };

  window.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
      ev.preventDefault();
      void open();
    }
  });
}
