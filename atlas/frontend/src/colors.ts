// Categorical palette for community-detection clusters. Distinct, readable on
// the dark canvas. Memory nodes get a fixed warm colour to stand apart.
const PALETTE = [
  "#4f9cf9", "#f5a623", "#58d68d", "#bb8fce", "#ec7063",
  "#5dade2", "#f7dc6f", "#48c9b0", "#e59866", "#af7ac5",
  "#7fb3d5", "#f1948a", "#82e0aa", "#d7bde2", "#f8c471",
];

export function communityColor(community: number | null | undefined): string {
  if (community === null || community === undefined) return "#8a90a0";
  return PALETTE[((community % PALETTE.length) + PALETTE.length) % PALETTE.length];
}
