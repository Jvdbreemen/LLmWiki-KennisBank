// Recall Inspector lens (27.8): the live retrieval waterfall. Shows WHY a
// document is retrieved for a query — the vector/FTS candidates, their RRF
// fusion, and the per-hit rerank factor breakdown (relevance x recency x
// importance x trust x usage = final). Data comes live from /recall (reuses the
// production _kbindex/_rank pipeline), so the shown factors match kb-recall.
import type { DataClient, Recall, RerankEntry, StageEntry } from "../data-client";
import { clear, el, message } from "../dom";
import { openInspect } from "../inspect";

const base = (p: string) => p.replace(/\\/g, "/").split("/").pop() ?? p;
const FACTORS = ["relevance", "recency", "importance", "trust", "usage"] as const;

function stageList(title: string, entries: StageEntry[]): HTMLElement {
  const ul = el("ul", { class: "list" });
  for (const e of entries) {
    ul.appendChild(el("li", { title: e.path }, [`${e.score.toFixed(4)} · ${base(e.path)}`]));
  }
  return el("div", { class: "stage-col" }, [el("h3", {}, [title]), ul]);
}

function factorRow(hit: RerankEntry): HTMLElement {
  const row = el("div", { class: "factors" }, []);
  const f = hit.factors ?? {};
  for (const name of FACTORS) {
    if (f[name] === undefined) continue;
    row.appendChild(el("span", { class: "factor", title: name }, [`${name[0].toUpperCase()} ${f[name].toFixed(3)}`]));
    row.appendChild(document.createTextNode(" × "));
  }
  row.appendChild(el("span", { class: "factor final" }, [`= ${(f.final ?? hit.score).toFixed(5)}`]));
  return row;
}

export function renderRecallLens(host: HTMLElement, client: DataClient): Promise<void> {
  clear(host);
  const input = el("input", { type: "text", placeholder: "zoekvraag… (bv. OTGW settings)" }) as HTMLInputElement;
  const button = el("button", { class: "run" }, ["Recall"]);
  const results = el("div", { class: "recall-results scroll" });

  const run = async () => {
    const q = input.value.trim();
    if (!q) return;
    message(results, "loading", "recall-waterfall draait (embed via Ollama)…");
    try {
      const d: Recall = await client.recall(q, 8);
      clear(results);
      if (d.status !== "ok" || d.final.length === 0) {
        results.appendChild(el("div", { class: "empty" }, [`geen hits (status ${d.status})`]));
        return;
      }

      // final hits with factor breakdown (the "why")
      const rerankByPath = new Map(d.stages.rerank.map((r) => [r.path, r]));
      const finalBox = el("div", {}, [el("h3", {}, ["Eindresultaat — waarom (relevance × rerank-factoren)"])]);
      const list = el("ol", { class: "list" });
      for (const h of d.final) {
        const rr = rerankByPath.get(h.path);
        const label = h.neighbor ? `graafbuur · ${base(h.path)}` : `${h.score.toFixed(5)} · ${base(h.path)}`;
        const li = el("li", { class: "clickable" }, [
          el("div", { class: "hit-path" }, [label]),
          rr ? factorRow(rr) : el("span", {}, []),
          el("div", { class: "hit-snippet" }, [h.snippet]),
        ]);
        li.addEventListener("click", () => void openInspect(client, h.path));
        list.appendChild(li);
      }
      finalBox.appendChild(list);

      // the upstream stages: vector + FTS candidates -> RRF fusion
      const stages = el("div", { class: "stages-grid" }, [
        stageList("Vector-KNN", d.stages.vector),
        stageList("FTS", d.stages.fts),
        stageList("RRF-fusie", d.stages.rrf),
      ]);

      results.appendChild(finalBox);
      results.appendChild(el("h3", {}, ["Waterfall — kandidaten per fase"]));
      results.appendChild(stages);
    } catch (e) {
      message(results, "error", `recall faalde: ${(e as Error).message}`);
    }
  };

  button.addEventListener("click", run);
  input.addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === "Enter") run(); });

  host.appendChild(el("div", { class: "lens-pad" }, [
    el("h2", {}, ["Recall Inspector — retrieval waterfall"]),
    el("div", { class: "recall-bar" }, [input, button]),
    results,
  ]));
  return Promise.resolve();
}
