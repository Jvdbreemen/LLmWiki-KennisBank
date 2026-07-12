// Tiny DOM builder. Everything goes through textContent — no innerHTML anywhere
// in the app, so no lens payload can inject markup.
import { currentGeneration, isCurrent } from "./lifecycle";

type Attrs = { class?: string; title?: string; type?: string; placeholder?: string };

export function el(
  tag: string,
  attrs: Attrs = {},
  children: (Node | string)[] = [],
): HTMLElement {
  const node = document.createElement(tag);
  if (attrs.class) node.className = attrs.class;
  if (attrs.title) node.title = attrs.title;
  if (attrs.type) (node as HTMLInputElement).type = attrs.type;
  if (attrs.placeholder) (node as HTMLInputElement).placeholder = attrs.placeholder;
  for (const c of children) {
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

export function clear(host: HTMLElement): void {
  host.replaceChildren();
}

export function message(host: HTMLElement, cls: string, text: string): void {
  clear(host);
  host.appendChild(el("div", { class: cls }, [text]));
}

// Run an async loader with uniform loading/error framing. Guards against a
// stale render: if the user switched lenses while `load()` was in flight, the
// captured generation is no longer current and the result is discarded.
export async function withLoader<T>(
  host: HTMLElement,
  loading: string,
  load: () => Promise<T>,
  render: (data: T) => void,
): Promise<void> {
  const gen = currentGeneration();
  message(host, "loading", loading);
  try {
    const data = await load();
    if (!isCurrent(gen)) return;
    render(data);
  } catch (e) {
    if (!isCurrent(gen)) return;
    message(host, "error", `onbeschikbaar: ${(e as Error).message}`);
  }
}
