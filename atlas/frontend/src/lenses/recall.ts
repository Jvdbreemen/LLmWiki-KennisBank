// Recall Inspector lens (27.8): live query against /recall, ordered final hits.
// Full per-stage waterfall follows when the sidecar surfaces stages.
import type { DataClient, Recall } from "../data-client";
import { clear, el, message } from "../dom";

export function renderRecallLens(host: HTMLElement, client: DataClient): Promise<void> {
  clear(host);
  const input = el("input", { type: "text", placeholder: "zoekvraag… (bv. OTGW settings)" }) as HTMLInputElement;
  const button = el("button", { class: "run" }, ["Recall"]);
  const results = el("div", { class: "recall-results scroll" });

  const run = async () => {
    const q = input.value.trim();
    if (!q) return;
    message(results, "loading", "recall draait (embed via Ollama)…");
    try {
      const d: Recall = await client.recall(q, 8);
      clear(results);
      if (d.status !== "ok" || d.final.length === 0) {
        results.appendChild(el("div", { class: "empty" }, [`geen hits (status ${d.status})`]));
        return;
      }
      const list = el("ol", { class: "list" });
      for (const h of d.final) {
        list.appendChild(el("li", {}, [
          el("div", { class: "hit-path" }, [`${h.score.toFixed(4)} · ${h.path}`]),
          el("div", { class: "hit-snippet" }, [h.snippet]),
        ]));
      }
      results.appendChild(list);
    } catch (e) {
      message(results, "error", `recall faalde: ${(e as Error).message}`);
    }
  };

  button.addEventListener("click", run);
  input.addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === "Enter") run(); });

  host.appendChild(el("div", { class: "lens-pad" }, [
    el("h2", {}, ["Recall Inspector"]),
    el("div", { class: "recall-bar" }, [input, button]),
    results,
  ]));
  return Promise.resolve();
}
