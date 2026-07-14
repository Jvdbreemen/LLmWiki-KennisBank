import { describe, expect, it } from "vitest";
import { DocHistory } from "./history";

describe("DocHistory", () => {
  it("starts empty: no back, no forward", () => {
    const h = new DocHistory();
    expect(h.canBack).toBe(false);
    expect(h.canForward).toBe(false);
    expect(h.back()).toBeNull();
    expect(h.forward()).toBeNull();
  });

  it("visit pushes the current doc on the back stack", () => {
    const h = new DocHistory();
    h.visitRoot("a.md");
    h.visit("b.md");
    expect(h.canBack).toBe(true);
    expect(h.back()).toBe("a.md");
    expect(h.canBack).toBe(false);
  });

  it("back then forward round-trips", () => {
    const h = new DocHistory();
    h.visitRoot("a.md");
    h.visit("b.md");
    h.visit("c.md");
    expect(h.back()).toBe("b.md");
    expect(h.back()).toBe("a.md");
    expect(h.canForward).toBe(true);
    expect(h.forward()).toBe("b.md");
    expect(h.forward()).toBe("c.md");
    expect(h.canForward).toBe(false);
    expect(h.canBack).toBe(true);
  });

  it("visit clears the forward stack (branching, browser-style)", () => {
    const h = new DocHistory();
    h.visitRoot("a.md");
    h.visit("b.md");
    h.back();
    expect(h.canForward).toBe(true);
    h.visit("d.md");
    expect(h.canForward).toBe(false);
    expect(h.back()).toBe("a.md");
  });

  it("visitRoot starts a fresh session: no stale history", () => {
    const h = new DocHistory();
    h.visitRoot("a.md");
    h.visit("b.md");
    h.visitRoot("x.md");
    expect(h.canBack).toBe(false);
    expect(h.canForward).toBe(false);
  });

  it("reset clears everything", () => {
    const h = new DocHistory();
    h.visitRoot("a.md");
    h.visit("b.md");
    h.reset();
    expect(h.canBack).toBe(false);
    expect(h.canForward).toBe(false);
    expect(h.back()).toBeNull();
  });
});
