// Markdown rendering for the inspect viewer, adopting the markdown-it + sanitizer
// pipeline that HedgeDoc / Wiki.js use (see the vault analysis). markdown-it
// produces an HTML string, DOMPurify sanitizes it, and only then does it reach
// the DOM — the one sanctioned innerHTML, on sanitized content. Everything is
// bundled locally (no CDN), so it stays CSP-safe and offline.
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import footnote from "markdown-it-footnote";
import taskLists from "markdown-it-task-lists";
import "highlight.js/styles/github-dark.css";

import type { DataClient } from "./data-client";

const WIKI_SCHEME = "atlaswiki:";

function stripFrontmatter(md: string): string {
  if (!md.startsWith("---")) return md;
  const end = md.indexOf("\n---", 3);
  if (end === -1) return md;
  return md.slice(md.indexOf("\n", end + 1) + 1);
}

function resolveWikiTarget(raw: string): string {
  let t = raw.split("#")[0].trim().replace(/^\//, "");
  if (!t) return "";
  if (!t.includes("/")) t = t.startsWith("raw-sessie") ? `01-raw/sessies/${t}` : `02-wiki/${t}`;
  return t.endsWith(".md") ? t : `${t}.md`;
}

function resolveAssetPath(docDir: string, src: string): string {
  const clean = src.split("#")[0].split("?")[0].trim().replace(/^\//, "");
  const relative = clean.startsWith("./") || clean.startsWith("../") || !clean.includes("/");
  const stack = relative && docDir ? docDir.split("/") : [];
  for (const p of clean.split("/")) {
    if (p === "" || p === ".") continue;
    if (p === "..") stack.pop();
    else stack.push(p);
  }
  return stack.join("/");
}

// [[target]] / [[target|label]] -> a markdown link on a private scheme the link
// renderer turns into an in-viewer wikilink.
function preprocessWikilinks(md: string): string {
  return md.replace(/\[\[([^\]]+)\]\]/g, (_m, inner: string) => {
    const [tgt, lbl] = inner.split("|");
    const path = resolveWikiTarget(tgt);
    return `[${(lbl ?? tgt).trim()}](${WIKI_SCHEME}${path})`;
  });
}

function buildMd(client: DataClient, docDir: string): MarkdownIt {
  const md: MarkdownIt = new MarkdownIt({
    html: false,
    linkify: false, // linkify-it can ReDoS on long technical strings; explicit
                    // [text](url) links still render.
    // No syntax highlighter: highlight.js froze the main thread (ReDoS) on some
    // code blocks in the real vault. Code renders escaped for now; a safe
    // per-block, time-boxed highlighter can be added later.
    highlight: (str) => `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`,
  });
  // NB: no auto inline-math plugin. Vault articles are full of shell `$VAR`
  // syntax, which an inline-KaTeX plugin misreads as math and can hang on.
  // Math/diagrams will be added later, scoped to explicit fenced/$$ blocks only.
  md.use(footnote).use(taskLists, { label: true });

  // images -> loopback /asset for vault-local paths; remote http not fetched.
  const defImage = md.renderer.rules.image!;
  md.renderer.rules.image = (tokens, idx, opts, env, self) => {
    const token = tokens[idx];
    const srcIdx = token.attrIndex("src");
    const src = srcIdx >= 0 ? token.attrs![srcIdx][1] : "";
    if (/^https?:/i.test(src)) {
      return `🖼 ${md.utils.escapeHtml(token.content || src)}`;
    }
    const url = client.assetUrl(resolveAssetPath(docDir, src));
    if (url && srcIdx >= 0) token.attrs![srcIdx][1] = url;
    token.attrPush(["class", "insp-img"]);
    return defImage(tokens, idx, opts, env, self);
  };

  // links -> wikilink (in-viewer) or external (new tab); other schemes neutralised.
  md.renderer.rules.link_open = (tokens, idx, opts, _env, self) => {
    const token = tokens[idx];
    const hrefIdx = token.attrIndex("href");
    const href = hrefIdx >= 0 ? token.attrs![hrefIdx][1] : "";
    if (href.startsWith(WIKI_SCHEME)) {
      token.attrs!.splice(hrefIdx, 1);
      token.attrPush(["class", "wikilink"]);
      token.attrPush(["data-path", href.slice(WIKI_SCHEME.length)]);
    } else if (/^(https?:|mailto:)/i.test(href)) {
      token.attrPush(["target", "_blank"]);
      token.attrPush(["rel", "noopener noreferrer"]);
      token.attrPush(["class", "extlink"]);
    } else if (hrefIdx >= 0) {
      token.attrs!.splice(hrefIdx, 1); // unknown scheme: drop the href
    }
    return self.renderToken(tokens, idx, opts);
  };
  return md;
}

export function renderMarkdownInto(
  host: HTMLElement, md: string, client: DataClient, docPath: string,
): void {
  const docDir = docPath.includes("/") ? docPath.slice(0, docPath.lastIndexOf("/")) : "";
  const engine = buildMd(client, docDir);
  const raw = engine.render(preprocessWikilinks(stripFrontmatter(md)));
  const clean = DOMPurify.sanitize(raw, {
    ADD_ATTR: ["data-path", "target", "class", "rel"],
  });
  host.innerHTML = clean; // sanitized above; the only innerHTML in the app
  // delegated wikilink navigation; { once via replace } avoids listener buildup.
  host.onclick = (e) => {
    const link = (e.target as HTMLElement).closest?.(".wikilink") as HTMLElement | null;
    const path = link?.dataset.path;
    if (path) void openInspectRef(client, path);
  };
}

// Late import avoids a cycle with inspect.ts.
let openInspectRef: (client: DataClient, path: string) => Promise<void>;
export function bindOpenInspect(fn: typeof openInspectRef): void {
  openInspectRef = fn;
}
