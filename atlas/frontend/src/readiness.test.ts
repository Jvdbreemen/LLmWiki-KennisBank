import { describe, expect, it } from "vitest";
import { waitUntilReady } from "./readiness";

const noSleep = () => Promise.resolve();

describe("waitUntilReady", () => {
  it("returns the probe value on first success", async () => {
    const v = await waitUntilReady(() => Promise.resolve("ok"), { sleep: noSleep });
    expect(v).toBe("ok");
  });

  it("keeps polling through failures until the probe succeeds", async () => {
    let calls = 0;
    const probe = () => {
      calls += 1;
      return calls < 5 ? Promise.reject(new Error("refused")) : Promise.resolve(calls);
    };
    const v = await waitUntilReady(probe, { sleep: noSleep, timeoutMs: 10_000 });
    expect(v).toBe(5);
  });

  it("throws the last error once the budget is exhausted", async () => {
    let now = 0;
    const origNow = Date.now;
    Date.now = () => now;
    try {
      const sleep = (ms: number) => { now += ms; return Promise.resolve(); };
      await expect(
        waitUntilReady(() => Promise.reject(new Error("still down")), {
          timeoutMs: 3000, intervalMs: 400, sleep,
        }),
      ).rejects.toThrow("still down");
    } finally {
      Date.now = origNow;
    }
  });

  it("backs off but stays within the deadline", async () => {
    let now = 0;
    const origNow = Date.now;
    Date.now = () => now;
    try {
      const delays: number[] = [];
      const sleep = (ms: number) => { delays.push(ms); now += ms; return Promise.resolve(); };
      await waitUntilReady(
        () => (now >= 2000 ? Promise.resolve("up") : Promise.reject(new Error("down"))),
        { timeoutMs: 30_000, intervalMs: 400, sleep },
      );
      expect(delays[0]).toBe(400);
      expect(delays[1]).toBe(600);
      expect(Math.max(...delays)).toBeLessThanOrEqual(2000);
    } finally {
      Date.now = origNow;
    }
  });
});
