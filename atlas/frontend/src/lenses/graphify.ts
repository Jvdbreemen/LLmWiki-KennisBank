// Graphify lens (TASK-84): embed the interactive graph.html that the graphify
// pipeline emits in <vault>/graphify-out/. The page is self-contained and the
// sidecar serves it over loopback http, so its scripts run inside the iframe
// (a file:// embed would hit the file://-wall and stay blank).
import type { DataClient } from "../data-client";
import { clear, el, message } from "../dom";
import { currentGeneration, isCurrent } from "../lifecycle";

export async function renderGraphifyLens(host: HTMLElement, client: DataClient): Promise<void> {
  const url = client.graphifyHtmlUrl();
  if (!url) {
    message(host, "error", "geen sidecar-poort — start met ?port=NNNN");
    return;
  }
  const gen = currentGeneration();
  message(host, "loading", "graphify-graaf laden…");
  // Probe before embedding: a missing graph.html would otherwise show the
  // sidecar's raw 404 JSON inside the iframe instead of a clear message.
  try {
    const resp = await fetch(url, { method: "HEAD" });
    if (!isCurrent(gen)) return;
    if (!resp.ok) {
      message(host, "empty", "geen graphify-out/graph.html in de vault — draai /graphify eerst");
      return;
    }
  } catch (e) {
    if (!isCurrent(gen)) return;
    message(host, "error", `onbeschikbaar: ${(e as Error).message}`);
    return;
  }
  clear(host);
  const frame = el("iframe", { class: "graphify-frame", title: "Graphify-kennisgraaf" }) as HTMLIFrameElement;
  frame.src = url;
  host.appendChild(frame);
}
