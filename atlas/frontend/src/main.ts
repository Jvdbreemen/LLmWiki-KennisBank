// App-shell: tab router, sidecar port handshake, global status banner
// (ADR-0004 frontend module boundaries). All DOM is built with textContent /
// createElement — never innerHTML — so no lens payload can inject markup.
import { DataClient } from "./data-client";
import { renderGraphLens } from "./lenses/graph";
import { renderTimeSliderLens } from "./lenses/time-slider";
import { renderMemoryHealthLens } from "./lenses/memory-health";
import { renderTimelineLens } from "./lenses/timeline";
import { renderRecallLens } from "./lenses/recall";
import { renderProvenanceLens } from "./lenses/provenance";
import "./style.css";

interface Lens {
  key: string;
  label: string;
  render: (el: HTMLElement, client: DataClient) => void | Promise<void>;
}

const LENSES: Lens[] = [
  { key: "graph", label: "Graph", render: renderGraphLens },
  { key: "timeslider", label: "Time-slider", render: renderTimeSliderLens },
  { key: "memory", label: "Memory Health", render: renderMemoryHealthLens },
  { key: "timeline", label: "Timeline", render: renderTimelineLens },
  { key: "recall", label: "Recall", render: renderRecallLens },
  { key: "provenance", label: "Provenance", render: renderProvenanceLens },
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
