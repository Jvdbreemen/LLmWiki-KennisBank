// Lens teardown registry. A lens that starts a long-running loop (the canvas
// force-graph) registers a cleanup here; the shell runs it before switching
// lenses so no detached animation loop keeps pegging the main thread.
let cleanup: (() => void) | null = null;

export function onLensLeave(fn: () => void): void {
  cleanup = fn;
}

export function runLensLeave(): void {
  const fn = cleanup;
  cleanup = null;
  try {
    fn?.();
  } catch {
    /* teardown must never throw */
  }
}
