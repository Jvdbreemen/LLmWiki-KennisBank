// App-shell: tab router, sidecar port handshake, global status banner
// (ADR-0004 frontend module boundaries). All DOM is built with textContent /
// createElement — never innerHTML — so no lens payload can inject markup.
import { DataClient } from "./data-client";
import { newGeneration, runLensLeave } from "./lifecycle";
import { renderGraphLens } from "./lenses/graph";
import { renderTimeSliderLens } from "./lenses/time-slider";
import { renderMemoryHealthLens } from "./lenses/memory-health";
import { renderTimelineLens } from "./lenses/timeline";
import { renderRecallLens } from "./lenses/recall";
import { renderProvenanceLens } from "./lenses/provenance";
import { renderWordcloudLens } from "./lenses/wordcloud";
import { waitUntilReady } from "./readiness";
import "./style.css";

interface Lens {
  key: string;
  label: string;
  render: (el: HTMLElement, client: DataClient) => void | Promise<void>;
}

const LENSES: Lens[] = [
  { key: "graph", label: "Graph", render: renderGraphLens },
  { key: "wordcloud", label: "Wordcloud", render: renderWordcloudLens },
  { key: "timeslider", label: "Time-slider", render: renderTimeSliderLens },
  { key: "memory", label: "Memory Health", render: renderMemoryHealthLens },
  { key: "timeline", label: "Timeline", render: renderTimelineLens },
  { key: "recall", label: "Recall", render: renderRecallLens },
  { key: "provenance", label: "Provenance", render: renderProvenanceLens },
];

const client = new DataClient();

// Wait for the sidecar before rendering anything data-driven: the frozen
// (PyInstaller) sidecar needs seconds to boot, and a single un-retried fetch
// at startup loses that race with a permanent "Failed to fetch".
async function connectSidecar(bar: HTMLElement): Promise<boolean> {
  bar.replaceChildren();
  const span = document.createElement("span");
  bar.appendChild(span);
  if (!client.configured) {
    span.className = "warn";
    span.textContent = "geen sidecar-poort — start met ?port=NNNN";
    return false;
  }
  span.textContent = "sidecar starten…";
  // No deadline: a cold sidecar boot must never leave the app permanently on
  // "Failed to fetch". Show elapsed time so a slow start is visibly alive.
  const t0 = Date.now();
  const ticker = window.setInterval(() => {
    span.textContent = `sidecar starten… (${Math.round((Date.now() - t0) / 1000)}s)`;
  }, 1000);
  try {
    const h = await waitUntilReady(() => client.health(), { timeoutMs: Number.POSITIVE_INFINITY });
    const live = Object.entries(h.sources)
      .filter(([, v]) => v)
      .map(([k]) => k);
    span.className = h.status === "ok" ? "ok" : "warn";
    // Show the resolved vault path (from KENNISBANK_VAULT via the sidecar) so
    // the user can verify at a glance that the right vault was picked up.
    span.textContent = `sidecar ${h.status} · v${h.version} · vault: ${h.vault} · bronnen: ${live.join(", ") || "geen"}`;
    return true;
  } catch (e) {
    span.className = "error";
    span.textContent = `sidecar onbereikbaar: ${(e as Error).message}`;
    return false;
  } finally {
    window.clearInterval(ticker);
  }
}

async function main(): Promise<void> {
  const tabs = document.getElementById("tabs")!;
  const bar = document.getElementById("statusbar")!;
  const lens = document.getElementById("lens")!;

  let active = LENSES[0].key;
  const select = (key: string) => {
    newGeneration(); // invalidate any in-flight render from the previous lens
    runLensLeave(); // stop the previous lens's animation loop, if any
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

  // Gate the first lens render on sidecar readiness; tabs stay clickable and a
  // manual tab switch simply retries the fetch.
  lens.textContent = "wachten op sidecar…";
  await connectSidecar(bar);
  select(active);
}

void main();
