// App-shell: tab router, sidecar port handshake, global status banner
// (ADR-0004 frontend module boundaries). All DOM is built with textContent /
// createElement — never innerHTML — so no lens payload can inject markup.
import { DataClient } from "./data-client";
import { renderGraphLens } from "./lenses/graph";
import "./style.css";

interface Lens {
  key: string;
  label: string;
  render: (el: HTMLElement, client: DataClient) => void | Promise<void>;
}

function placeholder(name: string): Lens["render"] {
  return (el) => {
    el.replaceChildren();
    const div = document.createElement("div");
    div.className = "placeholder";
    div.textContent = `${name}: nog niet gebouwd (sidecar-endpoint is klaar)`;
    el.appendChild(div);
  };
}

const LENSES: Lens[] = [
  { key: "graph", label: "Graph", render: renderGraphLens },
  { key: "timeslider", label: "Time-slider", render: placeholder("Time-slider (27.5)") },
  { key: "memory", label: "Memory Health", render: placeholder("Memory Health (27.6)") },
  { key: "timeline", label: "Timeline", render: placeholder("Timeline (27.7)") },
  { key: "recall", label: "Recall", render: placeholder("Recall Inspector (27.8)") },
  { key: "provenance", label: "Provenance", render: placeholder("Provenance (27.9)") },
];

const client = new DataClient();

function renderStatusbar(bar: HTMLElement): void {
  bar.replaceChildren();
  const span = document.createElement("span");
  if (!client.configured) {
    span.className = "warn";
    span.textContent = "geen sidecar-poort — start met ?port=NNNN";
    bar.appendChild(span);
    return;
  }
  span.textContent = "sidecar verbinden…";
  bar.appendChild(span);
  client
    .health()
    .then((h) => {
      const live = Object.entries(h.sources)
        .filter(([, v]) => v)
        .map(([k]) => k);
      span.className = h.status === "ok" ? "ok" : "warn";
      span.textContent = `sidecar ${h.status} · v${h.version} · bronnen: ${live.join(", ") || "geen"}`;
    })
    .catch((e) => {
      span.className = "error";
      span.textContent = `sidecar onbereikbaar: ${(e as Error).message}`;
    });
}

function main(): void {
  const tabs = document.getElementById("tabs")!;
  const bar = document.getElementById("statusbar")!;
  const lens = document.getElementById("lens")!;

  let active = LENSES[0].key;
  const select = (key: string) => {
    active = key;
    for (const btn of tabs.children) {
      (btn as HTMLElement).classList.toggle("active", (btn as HTMLElement).dataset.key === key);
    }
    const l = LENSES.find((x) => x.key === key)!;
    void l.render(lens, client);
  };

  for (const l of LENSES) {
    const btn = document.createElement("button");
    btn.dataset.key = l.key;
    btn.textContent = l.label;
    btn.addEventListener("click", () => select(l.key));
    tabs.appendChild(btn);
  }

  renderStatusbar(bar);
  select(active);
}

main();
