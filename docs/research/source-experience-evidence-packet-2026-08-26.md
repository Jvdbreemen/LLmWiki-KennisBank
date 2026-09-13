# Source-recall and experience-memory evidence packet

Date: 2026-08-26
Branch: `codex/source-recall-experience-evidence`
Policy: source and experience routes remain opt-in; outcome-aware ranking remains disabled.

## Executive decision

| layer | technical contract | product-value evidence | decision |
|---|---|---|---|
| source recall | passes hermetic plumbing, provenance labels, stale/no-hit states, staged rebuild, and fail-open routing | only 3 real local smoke cases; no reviewed negative set or paired downstream answer labels | **hold** |
| experience recall | passes typed events, evidence-bound extraction, validated-only recall, failure advisory labels, proposal-only promotion, staged rebuild, and lifecycle diagnostics | no reviewed live experience holdout and no paired action-correctness labels | **hold** |
| outcome-aware ranking | intentionally not implemented as a production ranking factor | no evidence that it improves decisions without harmful bias | **reject for this release** |

“Hold” is not a claim that the layers are useful. It means the implementation
is testable and safe to evaluate, while the evidence needed to justify default
use is absent. This is the intended result of the preregistered gate.

## Observed source evidence

The configured vault was audited read-only. It contains 16,255 approved text
files, of which 15,337 lack session/timestamp/source metadata and 2,784 hash
groups are duplicates. This makes a full-vault RAG benchmark look larger than
its real evidence quality. The source smoke report indexed three selected local
windows: lexical-only hit@1 was 0.33 and hybrid vector+lexical hit@1 was 1.00;
provenance precision was 1.00. Those queries were partly extractive and had no
negative controls, so this is plumbing evidence, not usefulness evidence.

The frozen source gate requires at least 50 positive and 10 negative reviewed
queries, exact provenance, no-hit specificity, normal-path latency deltas,
rebuild preservation, and a paired answer-correctness improvement of at least
0.10. The current sample cannot satisfy those requirements.

## Observed experience evidence

The live memory audit found 4,808 memory files. All had `source_session` and
`evidence_basis` fields, 2,418 also had a `source_chunk`, and no raw body fields
were present in the memory records. This confirms the design distinction: a
memory can point to evidence without containing the raw source body. A separate
source-recall projection therefore has a legitimate grounding role when a user
asks for deeper support, but that role is not yet shown to improve answers.

The live vault had no `kb-experience.db` and no reviewed experience holdout.
Consequently the experience gate has no valid sample for validated-hit rate,
failure-advisory precision, false-warning rate, action correctness, or normal
path latency. The implementation reports `hold`; it does not manufacture
successes from absent observations.

## Reproducible implementation evidence

- `tests/test_source_holdout.py`, `test_source_holdout_cli.py`,
  `test_build_source_index.py`, `test_source_recall.py`, and groundcheck tests
  cover source identity, redaction, hash freshness, no-hit labels, and staged
  failure preservation.
- `tests/test_experience_store.py`, `test_experience_extract.py`,
  `test_experience_recall.py`, `test_experience_promotion.py`, and
  `test_experience_maintenance.py` cover typed append-only events, unknown and
  mixed outcomes, evidence-bound records, candidate leakage prevention,
  repeated-support proposals, owner rejection, lifecycle signals, and full or
  incremental rebuild behavior.
- `tests/test_projection_doctor.py` proves read-only source/experience health
  reporting. `tests/test_kb_mcp.py` and `test_kb_mcp_wire.py` prove the two
  explicit MCP surfaces and their read-only annotations.
- `tests/test_setup_deploy.py` and `test_agent_envs_install.py` prove that
  setup/upgrade discovery, configured vault pinning, and the client surfaces
  remain compatible. The combined agent/setup selection passed 33 tests with 4
  deselected in 305.82 seconds; the MCP/documentation selection passed 29 tests
  in 25.88 seconds; the lifecycle/doctor selection passed 6 tests.
- The complete focused feature suite passed **167 tests in 344.86 seconds**
  with the correct writable Windows basetemp.

The first whole-repository run was not a valid suite result because its
explicit basetemp pointed at a non-existent `D:\Users\Robert\AppData` path:
it produced 20 setup errors, one baseline WSL `bash.exe` timing failure, and
1,733 passes. Re-running the 34 affected baseline tests with the actual
writable temp root produced 33 passes and the same pre-existing
`test_proc_bounded.py` WSL timing failure. This does not weaken the focused
feature evidence, but it means the branch is not presented as a green
whole-repository release candidate.

## Required next measurement

1. A human reviews and freezes 50 source positives, 10 source negatives, and
   60 experience cases across success, failure, conflict/stale, unknown, and
   unrelated categories.
2. Run the six-arm packet with the strongest existing wiki/memory baseline and
   paired answer/action correctness labels.
3. Inspect provenance precision, stale/redacted behavior, repeated-failure
   survival, false warnings, and p50/p95 normal-path deltas.
4. Enable a route only if its own gate returns `go`; never infer approval from
   the other layer or from retrieval hit-rate alone.
