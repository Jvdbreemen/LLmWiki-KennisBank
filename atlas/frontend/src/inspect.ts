// Read-only inspect drawer: click a node/hit/item in any lens to read the file.
// Markdown is rendered by the markdown-it + DOMPurify pipeline in markdown.ts.
import type { DataClient } from "./data-client";
import { clear, el } from "./dom";
import { bindOpenInspect, renderMarkdownInto } from "./markdown";

let drawer: HTMLElement | null = null;

function ensureDrawer(): { host: HTMLElement; title: HTMLElement; body: HTMLElement } {
  if (!drawer) {
    const close = el("button", { class: "insp-close", title: "sluiten" }, ["×"]);
    close.addEventListener("click", () => drawer?.classList.remove("open"));
    const title = el("div", { class: "insp-title" }, []);
    const body = el("div", { class: "insp-body" }, []);
    drawer = el("aside", { class: "inspect" }, [
      el("div", { class: "insp-head" }, [title, close]),
      body,
    ]);
    document.body.appendChild(drawer);
  }
  return {
    host: drawer,
    title: drawer.querySelector(".insp-title") as HTMLElement,
    body: drawer.querySelector(".insp-body") as HTMLElement,
  };
}

export async function openInspect(client: DataClient, path: string): Promise<void> {
  const { host, title, body } = ensureDrawer();
  host.classList.add("open");
  title.textContent = path;
  clear(body);
  body.appendChild(el("div", { class: "loading" }, ["laden…"]));
  try {
    const doc = await client.doc(path);
    title.textContent = doc.title || path;
    renderMarkdownInto(body, doc.content, client, doc.path || path);
  } catch (e) {
    clear(body);
    body.appendChild(el("div", { class: "error" }, [`kon niet laden: ${(e as Error).message}`]));
  }
}

// Break the inspect <-> markdown import cycle: markdown.ts calls back here for
// in-viewer wikilink navigation.
bindOpenInspect(openInspect);
