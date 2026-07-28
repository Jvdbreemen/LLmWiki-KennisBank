// TASK-91 F2: fuzzyFilter is de pure kern van het Cmd+K-palet.
import { describe, expect, it } from "vitest";

import { fuzzyFilter, type PaletteEntry } from "./palette";

const entries: PaletteEntry[] = [
  { kind: "lens", key: "overview", title: "Overzicht" },
  { kind: "lens", key: "recall", title: "Recall" },
  { kind: "doc", key: "02-wiki/traefik.md", title: "Traefik", layer: "wiki" },
  { kind: "doc", key: "02-wiki/wireguard-cgnat.md", title: "WireGuard achter CGNAT", layer: "wiki" },
  { kind: "doc", key: "09-memory/2026-07-01-besluit.md", title: "Besluit: eigen graafbestand", layer: "memory" },
];

describe("fuzzyFilter", () => {
  it("lege query geeft de eerste entries terug", () => {
    expect(fuzzyFilter(entries, "", 3)).toHaveLength(3);
  });

  it("matcht op titel, case-insensitive", () => {
    const r = fuzzyFilter(entries, "wireguard");
    expect(r).toHaveLength(1);
    expect(r[0].title).toBe("WireGuard achter CGNAT");
  });

  it("matcht op pad/key", () => {
    const r = fuzzyFilter(entries, "09-memory");
    expect(r).toHaveLength(1);
    expect(r[0].kind).toBe("doc");
  });

  it("alle tokens moeten voorkomen", () => {
    expect(fuzzyFilter(entries, "wireguard traefik")).toHaveLength(0);
    expect(fuzzyFilter(entries, "wireguard cgnat")).toHaveLength(1);
  });

  it("deterministische ordening", () => {
    const r = fuzzyFilter(entries, "r");
    expect(r.length).toBeGreaterThan(1);
    expect(fuzzyFilter(entries, "r")).toEqual(r);
  });

  it("respecteert de limit", () => {
    expect(fuzzyFilter(entries, "", 2)).toHaveLength(2);
  });

  it("geen match geeft lege lijst", () => {
    expect(fuzzyFilter(entries, "bestaatniet")).toEqual([]);
  });
});
