// Read-only inspect drawer: click a node/hit/item in any lens to read the file.
// Markdown is rendered to DOM element-by-element (headings, code fences, lists,
// paragraphs) — never innerHTML, so file content cannot inject markup.
import type { DataClient } from "./data-client";
import { clear, el } from "./dom";

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

// Minimal, safe markdown -> DOM. Handles the structure that matters for reading.
function stripFrontmatter(md: string): string {
  if (!md.startsWith("---")) return md;
  const end = md.indexOf("\n---", 3);
  if (end === -1) return md;
  return md.slice(md.indexOf("\n", end + 1) + 1);
}

function renderMarkdown(host: HTMLElement, md: string): void {
  clear(host);
  const lines = stripFrontmatter(md).split("\n");
  let i = 0;
  let para: string[] = [];
  const flush = () => {
    if (para.length) {
      host.appendChild(el("p", {}, [para.join(" ")]));
      para = [];
    }
  };
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      flush();
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++; // skip closing fence
      host.appendChild(el("pre", {}, [el("code", {}, [code.join("\n")])]));
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      flush();
      host.appendChild(el(`h${h[1].length}`, {}, [h[2]]));
      i++;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      flush();
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      const ul = el("ul", {}, []);
      for (const it of items) ul.appendChild(el("li", {}, [it]));
      host.appendChild(ul);
      continue;
    }
    if (line.trim() === "") { flush(); i++; continue; }
    para.push(line);
    i++;
  }
  flush();
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
    renderMarkdown(body, doc.content);
  } catch (e) {
    clear(body);
    body.appendChild(el("div", { class: "error" }, [`kon niet laden: ${(e as Error).message}`]));
  }
}
