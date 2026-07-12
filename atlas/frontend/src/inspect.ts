// Read-only inspect drawer: click a node/hit/item in any lens to read the file.
// Markdown is rendered by the markdown-it + DOMPurify pipeline in markdown.ts.
import type { DataClient, MemoryLinks } from "./data-client";
import { clear, el } from "./dom";
import { bindOpenInspect, renderMarkdownInto } from "./markdown";

// Cache the (expensive) memory-links payload once per session for the inspect
// "entry points" section, so opening articles stays instant after the first.
let openToken = 0; // bumped each open; guards stale async appends into the drawer
let linksPromise: Promise<MemoryLinks> | null = null;
function memoryLinks(client: DataClient): Promise<MemoryLinks> {
  if (!linksPromise) linksPromise = client.memoryLinks().catch(() =>
    ({ status: "empty", links: {}, counts: {}, types: {} }) as MemoryLinks);
  return linksPromise;
}

// Append "memory entry points" (fragments that point to this article) below the
// article, each opening the fragment. Non-blocking and fail-soft.
async function appendEntryPoints(body: HTMLElement, client: DataClient, articlePath: string, token: number): Promise<void> {
  const ml = await memoryLinks(client);
  if (token !== openToken) return; // a newer doc was opened while links loaded
  const frags = Object.entries(ml.links)
    .filter(([, a]) => a === articlePath)
    .map(([stem]) => stem)
    .sort();
  if (frags.length === 0) return;
  const list = el("ul", { class: "list" });
  for (const stem of frags) {
    const type = ml.types[stem] ? `[${ml.types[stem]}] ` : "";
    const li = el("li", { class: "clickable" }, [`${type}${stem}`]);
    li.addEventListener("click", () => void openInspect(client, `09-memory/${stem}.md`));
    list.appendChild(li);
  }
  body.appendChild(el("div", { class: "entry-points" }, [
    el("h3", {}, [`Memory-ingangen (${frags.length}) — fragmenten die hierheen leiden`]),
    list,
  ]));
}

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
    const docPath = doc.path || path;
    renderMarkdownInto(body, doc.content, client, docPath);
    // entry points (fragments -> this wiki article); non-blocking, fail-soft.
    openToken += 1;
    if (docPath.startsWith("02-wiki/")) {
      void appendEntryPoints(body, client, docPath, openToken);
    }
  } catch (e) {
    clear(body);
    body.appendChild(el("div", { class: "error" }, [`kon niet laden: ${(e as Error).message}`]));
  }
}

// Break the inspect <-> markdown import cycle: markdown.ts calls back here for
// in-viewer wikilink navigation.
bindOpenInspect(openInspect);
