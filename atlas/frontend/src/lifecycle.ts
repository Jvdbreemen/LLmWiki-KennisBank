// Lens teardown registry. A lens that starts a long-running loop (the canvas
// force-graph) registers a cleanup here; the shell runs it before switching
// lenses so no detached animation loop keeps pegging the main thread.
let cleanup: (() => void) | null = null;

// Render generation: bumped on every lens switch. An async lens captures the
// generation at start and must not write to the DOM if it is no longer current
// (its awaits resolved after the user already switched away).
let generation = 0;
export function newGeneration(): number {
  return ++generation;
}
export function currentGeneration(): number {
  return generation;
}
export function isCurrent(gen: number): boolean {
  return gen === generation;
}

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
