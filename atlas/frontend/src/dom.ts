// Tiny DOM builder. Everything goes through textContent — no innerHTML anywhere
// in the app, so no lens payload can inject markup.
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

// Run an async loader with uniform loading/error framing.
export async function withLoader<T>(
  host: HTMLElement,
  loading: string,
  load: () => Promise<T>,
  render: (data: T) => void,
): Promise<void> {
  message(host, "loading", loading);
  try {
    const data = await load();
    render(data);
  } catch (e) {
    message(host, "error", `onbeschikbaar: ${(e as Error).message}`);
  }
}
