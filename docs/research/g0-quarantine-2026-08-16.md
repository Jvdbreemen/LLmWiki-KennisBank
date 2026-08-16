# G0 — what the quarantine actually contains

**2026-08-16 — TASK-195, gate G0. Sixty unverified memories, stratified on the
`source_chunk` stamp (35/25, matching the 58/42 split of the 993), trap-1
local verdicts first, then exhaustive client-LLM adjudication of all sixty
with adversarial re-reads of every non-supported verdict.**

## Base rates

| exhaustive verdict | n | share | Wilson 95% |
| --- | --- | --- | --- |
| supported by its own transcript | 52 | 86.7% | 75–93% |
| partial — claim adds a specific the source lacks | 8 | 13.3% | 7–24% |
| **absent — invented, subject nowhere** | **0** | **0%** | 0–6% |

(The skeptic pass flipped one `partial` to `supported` by finding the merged
upstream PR the claim describes; refutations 1/9, the other eight confirmed.)

**The class the quarantine exists to catch is empty.** It is a warehouse of
correct knowledge held invisible by a capture judge that demands certainty in
the moment, feeding a review queue with one log line ever. Two thirds of
everything captured lands here, and none of it can be recalled.

## G1 calibration — Trap 1's local verdicts against the exhaustive reading

| trap-1 route | n supported | confirmed supported | confirmed supported-or-partial |
| --- | --- | --- | --- |
| stamp (exact chunk) | 33 | 27 (81.8%) | **33 (100%)** |
| windows (retrieval) | 18 | 18 (100%) | **18 (100%)** |
| total | 51 | 45 (88.2%, CI 76.6–94.5) | **51 (100%, lower bound 93%)** |

Escalation rate: 9/60 (15%) — and of those nine, the client found six fully
supported and three partial. Zero absent even in the escalated set.

Two findings inside the calibration:

- **The strict 0.95 reading fails; the not-absent reading passes at 51/51.**
  The registered bar did not define `partial`, and G0 was designed to settle
  exactly this. Settled with the owner: G1 = *nothing the exhaustive reading
  calls absent may be promoted*. Rationale in the design doc.
- **The stamp route is the looser judge, not the stricter one.** One exact
  chunk lets a slightly over-specific claim through more often (27/33 strict)
  than four retrieved windows do (18/18). More context appears to make the
  local model harder to satisfy, not easier. Worth re-measuring at larger n
  before anyone builds on it.

## What this changes for the pipeline

Trap 1 promotes on `supported` and touches nothing else — as designed, now
with its bar calibrated. Trap 2's expected workload drops to ~15% of the
queue, and its job shifts from "filter the junk" (there is none in sample) to
"rescue the escalated". Trap 3 (retraction) has, on this evidence, almost
nothing to do — which is itself the strongest argument for keeping its
double-agreement requirement: a rare act can afford an expensive check.

## Cost

Trap-1 local pass: 60 memories in 9m11s (qwen3.5:4b + windowed retrieval for
the unstamped). Client adjudication: 14 agents, ~1.0M tokens, ~8 minutes.


## The drain, and gate G3 — added after the backlog run

Trap 1 ran over the full quarantine on 2026-08-16 (kb-verify, one resumable
run, ~5 hours sharing the GPU with another session):

    993 judged -> 859 promoted (86.5%)
    left for Trap 2: `unsupported` 76, `partial` 28, `unparseable` 20, `not_found` 10

G0's base rate predicted 86.7% supported; the full population delivered 86.5%.
The calibration sample was representative to within two tenths of a point.
Every promotion carries its evidence quote, route, and prompt version in
`memory-promote-log.jsonl`; exactly 859 files were re-indexed afterwards with
zero failures.

**G3 — the recall pool grew by 56% (1532 -> 2391 current), measured:**

| metric | 1224-question set | freshness dev, newest | freshness dev, oldest |
| --- | --- | --- | --- |
| recall@1 | 0.234 → 0.269 (+0.035) | 0.286 → 0.357 | 0.100 → 0.100 |
| recall@3 | 0.590 → 0.626 (+0.036) | 0.429 → 0.429 | 0.233 → 0.233 |
| recall@5 | 0.758 → 0.752 (−0.006) | 0.643 → 0.571 | 0.333 → 0.333 |
| MRR | 0.427 → 0.453 (+0.026) | | |

Read honestly, both directions: the top-rank gains on the large set come from
eval-gold memories that were themselves quarantined — those questions could
not score at all before the drain. The −0.006 at recall@5 (seven questions of
1224) and the one-question wobble on the 14-question newest slice are
displacement: 859 new pool members outrank a previous gold occasionally. G3
was registered without a numeric threshold, so no pass/fail is claimed —
the numbers are simply here, and the direction is: substantially better where
it matters most, marginally noisier at the tail.

The quarantine's steady state changes shape: the rot warning drops from 993
to 134, new captures leave quarantine within a sweep cycle via the capped
pass, and the 134 escalated cases wait for Trap 2 — which now has a measured
job description: 76 of them are the verdict class that was wrong every time
it was checked from one passage, which is exactly why only the exhaustive
client reading may decide them.
