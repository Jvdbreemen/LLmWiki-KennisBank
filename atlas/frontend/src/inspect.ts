// Read-only inspect drawer: click a node/hit/item in any lens to read the file.
// Markdown is rendered by the markdown-it + DOMPurify pipeline in markdown.ts.
// Navigation: lenses open a root document (fresh history); wikilinks inside the
// drawer navigate with browser-style back/forward (DocHistory). Memory entry
// points expand inline (accordion) instead of navigating away.
import type { DataClient, MemoryLinks } from "./data-client";
import { clear, el } from "./dom";
import { DocHistory } from "./history";
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

const history = new DocHistory();

// Append "memory entry points" (fragments that point to this article) below the
// article. Each row is an accordion: the fragment expands inline (lazy-loaded,
// DOM kept so re-toggling is free) instead of replacing the article.
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
    const marker = el("span", { class: "acc-marker" }, ["▸"]);
    const head = el("div", { class: "clickable acc-head" }, [marker, `${type}${stem}`]);
    const frag = el("div", { class: "acc-body" }, []);
    frag.hidden = true;
    head.addEventListener("click", () => void toggleFragment(client, stem, marker, frag));
    list.appendChild(el("li", { class: "acc-item" }, [head, frag]));
  }
  body.appendChild(el("div", { class: "entry-points" }, [
    el("h3", {}, [`Memory-ingangen (${frags.length}) — fragmenten die hierheen leiden`]),
    list,
  ]));
}

async function toggleFragment(client: DataClient, stem: string, marker: HTMLElement, frag: HTMLElement): Promise<void> {
  const open = !frag.hidden;
  frag.hidden = open;
  marker.textContent = open ? "▸" : "▾";
  if (open || frag.dataset.loaded) return; // collapsing, or DOM already built
  frag.dataset.loaded = "1";
  const path = `09-memory/${stem}.md`;
  frag.appendChild(el("div", { class: "loading" }, ["laden…"]));
  try {
    const doc = await client.doc(path);
    clear(frag);
    renderMarkdownInto(frag, doc.content, client, doc.path || path);
  } catch (e) {
    clear(frag);
    delete frag.dataset.loaded; // allow a retry on the next expand
    frag.appendChild(el("div", { class: "error" }, [`kon niet laden: ${(e as Error).message}`]));
  }
}

let drawer: HTMLElement | null = null;
let clientRef: DataClient | null = null;

interface DrawerParts {
  host: HTMLElement;
  title: HTMLElement;
  body: HTMLElement;
  back: HTMLButtonElement;
  fwd: HTMLButtonElement;
}

function updateNav(): void {
  if (!drawer) return;
  (drawer.querySelector(".insp-back") as HTMLButtonElement).disabled = !history.canBack;
  (drawer.querySelector(".insp-fwd") as HTMLButtonElement).disabled = !history.canForward;
}

function closeDrawer(): void {
  drawer?.classList.remove("open");
  history.reset(); // no stale history across drawer sessions
  updateNav();
}

function goBack(): void {
  const p = history.back();
  if (p && clientRef) void renderDoc(clientRef, p);
}

function goForward(): void {
  const p = history.forward();
  if (p && clientRef) void renderDoc(clientRef, p);
}

function ensureDrawer(): DrawerParts {
  if (!drawer) {
    const back = el("button", { class: "insp-nav insp-back", title: "terug (Alt+←)" }, ["←"]) as HTMLButtonElement;
    const fwd = el("button", { class: "insp-nav insp-fwd", title: "vooruit (Alt+→)" }, ["→"]) as HTMLButtonElement;
    back.addEventListener("click", goBack);
    fwd.addEventListener("click", goForward);
    const close = el("button", { class: "insp-close", title: "sluiten" }, ["×"]);
    close.addEventListener("click", closeDrawer);
    const title = el("div", { class: "insp-title" }, []);
    const body = el("div", { class: "insp-body" }, []);
    drawer = el("aside", { class: "inspect" }, [
      el("div", { class: "insp-head" }, [back, fwd, title, close]),
      body,
    ]);
    document.body.appendChild(drawer);
    document.addEventListener("keydown", (e) => {
      if (!drawer?.classList.contains("open") || !e.altKey) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); goBack(); }
      if (e.key === "ArrowRight") { e.preventDefault(); goForward(); }
    });
  }
  return {
    host: drawer,
    title: drawer.querySelector(".insp-title") as HTMLElement,
    body: drawer.querySelector(".insp-body") as HTMLElement,
    back: drawer.querySelector(".insp-back") as HTMLButtonElement,
    fwd: drawer.querySelector(".insp-fwd") as HTMLButtonElement,
  };
}

// Render a document into the drawer without touching history (history is the
// caller's concern: root open, wikilink visit, or back/forward move).
async function renderDoc(client: DataClient, path: string): Promise<void> {
  clientRef = client;
  const { host, title, body } = ensureDrawer();
  host.classList.add("open");
  updateNav();
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

/** Root open from a lens: starts a fresh drawer history. */
export async function openInspect(client: DataClient, path: string): Promise<void> {
  history.visitRoot(path);
  await renderDoc(client, path);
}

/** In-drawer navigation (wikilinks): pushes onto the back stack. */
async function navigateInspect(client: DataClient, path: string): Promise<void> {
  history.visit(path);
  await renderDoc(client, path);
}

// Break the inspect <-> markdown import cycle: markdown.ts calls back here for
// in-viewer wikilink navigation (with history; lenses use openInspect above).
bindOpenInspect(navigateInspect);
