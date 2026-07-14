// Sidecar readiness gate. The frozen (PyInstaller) sidecar needs seconds to
// boot; a single fetch at app start loses that race and shows a permanent
// "Failed to fetch". Poll until the first probe succeeds, then hand off.
export interface WaitOptions {
  timeoutMs?: number;   // total budget before giving up
  intervalMs?: number;  // base delay between probes (grows 1.5x, capped at 2s)
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Poll `probe` until it resolves. Returns its value, or throws the last
 *  probe error once the time budget is exhausted. */
export async function waitUntilReady<T>(
  probe: () => Promise<T>,
  { timeoutMs = 30_000, intervalMs = 400, sleep = defaultSleep }: WaitOptions = {},
): Promise<T> {
  const deadline = Date.now() + timeoutMs;
  let delay = intervalMs;
  for (;;) {
    try {
      return await probe();
    } catch (e) {
      if (Date.now() >= deadline) throw e;
      await sleep(Math.min(delay, Math.max(0, deadline - Date.now())));
      delay = Math.min(delay * 1.5, 2000);
    }
  }
}
