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

// Resolve a [[wikilink]] target to a vault-relative doc path.
function resolveWikiTarget(raw: string): string {
  let t = raw.split("#")[0].trim().replace(/^\//, "");
  if (!t) return "";
  if (!t.includes("/")) {
    t = t.startsWith("raw-sessie") ? `01-raw/sessies/${t}` : `02-wiki/${t}`;
  }
  return t.endsWith(".md") ? t : `${t}.md`;
}

// Resolve a relative image src against the article's directory into a
// vault-relative path (normalising ./ and ../ segments).
function resolveAssetPath(docDir: string, src: string): string {
  const clean = src.split("#")[0].split("?")[0].trim().replace(/^\//, "");
  const relative =
    clean.startsWith("./") || clean.startsWith("../") || !clean.includes("/");
  const stack = relative && docDir ? docDir.split("/") : [];
  for (const p of clean.split("/")) {
    if (p === "" || p === ".") continue;
    if (p === "..") stack.pop();
    else stack.push(p);
  }
  return stack.join("/");
}

// Inline tokenizer, in precedence order: ![alt](src) image, [[wikilink]]
// (navigates the viewer), [label](http…) external link (new tab, http/https/
// mailto only). Local image src is served via /asset; remote images are not
// fetched (local-first) and fall back to a link. Unknown schemes stay literal.
const INLINE_RE =
  /!\[([^\]]*)\]\(([^)]+)\)|\[\[([^\]]+)\]\]|\[([^\]]+)\]\(([^)]+)\)/g;

function appendInline(
  parent: HTMLElement, text: string, client: DataClient, docDir: string,
): void {
  let last = 0;
  for (const m of text.matchAll(INLINE_RE)) {
    const at = m.index ?? 0;
    if (at > last) parent.appendChild(document.createTextNode(text.slice(last, at)));
    if (m[1] !== undefined) {
      // image
      const alt = m[1];
      const src = m[2].trim();
      if (/^https?:/i.test(src)) {
        parent.appendChild(document.createTextNode(`🖼 ${alt || src}`)); // remote: not fetched
      } else {
        const url = client.assetUrl(resolveAssetPath(docDir, src));
        if (url) {
          const img = document.createElement("img");
          img.src = url;
          img.alt = alt;
          img.className = "insp-img";
          parent.appendChild(img);
        }
      }
    } else if (m[3] !== undefined) {
      const [tgt, lbl] = m[3].split("|");
      const path = resolveWikiTarget(tgt);
      const a = el("span", { class: "wikilink", title: path }, [(lbl ?? tgt).trim()]);
      a.addEventListener("click", () => void openInspect(client, path));
      parent.appendChild(a);
    } else {
      const label = m[4];
      const url = m[5].trim();
      if (/^(https?:|mailto:)/i.test(url)) {
        const a = document.createElement("a");
        a.textContent = label;
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.className = "extlink";
        parent.appendChild(a);
      } else {
        parent.appendChild(document.createTextNode(m[0])); // unknown scheme: literal
      }
    }
    last = at + m[0].length;
  }
  if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
}

function renderMarkdown(host: HTMLElement, md: string, client: DataClient, docPath: string): void {
  clear(host);
  const docDir = docPath.includes("/") ? docPath.slice(0, docPath.lastIndexOf("/")) : "";
  const lines = stripFrontmatter(md).split("\n");
  let i = 0;
  let para: string[] = [];
  const flush = () => {
    if (para.length) {
      const p = el("p", {}, []);
      appendInline(p, para.join(" "), client, docDir);
      host.appendChild(p);
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
      for (const it of items) {
        const li = el("li", {}, []);
        appendInline(li, it, client, docDir);
        ul.appendChild(li);
      }
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
    renderMarkdown(body, doc.content, client, doc.path || path);
  } catch (e) {
    clear(body);
    body.appendChild(el("div", { class: "error" }, [`kon niet laden: ${(e as Error).message}`]));
  }
}
