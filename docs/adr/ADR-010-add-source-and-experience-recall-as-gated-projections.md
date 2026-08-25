---
id: "ADR-010"
title: "Add source and experience recall as separately gated projections"
status: "Proposed"
date: "2026-08-25"
binding: false
gate: "TASK-220"
documents_shipped: false
verified_in: []
supersedes: []
superseded_by: null
format: "madr"
topics:
  - source-recall
  - experience-memory
  - outcome-telemetry
  - retrieval-evaluation
components:
  - retrieval
  - session-lifecycle
  - index-store
symbols:
  - source_hits
  - record_outcome
  - experience_hits
context_scope: "selective"
---

<!-- markdownlint-disable MD025 -->

# ADR-010 Add source and experience recall as separately gated projections

## Status

Proposed, 2026-08-25. This record is deliberately not Accepted: TASK-220 must
produce the evidence packet and the owner must explicitly accept it first.

## Status History

```yaml
status_history:
  - date: 2026-08-25
    status: Proposed
    changed_by: Codex
    reason: Owner requested test-first implementation and evidence before either layer can enter a main release
    changed_via: adr-kit
```

## Context and Problem Statement

KennisBank currently retrieves curated wiki articles and current memory. Raw
transcripts and sources remain available for focused verification, but there is
no general retrieval projection that can recover an unknown source and return
an exact evidence location. Usage telemetry records exposure and some reads,
but not whether the exposed item helped or harmed the task. Consequently the
system can retrieve what it knows, but cannot reliably reconstruct why it knows
it or learn from observed outcomes.

Two proposals address different gaps:

* source recall indexes raw evidence and returns exact passages and provenance;
* experience recall stores outcome-linked episodes, lessons, and failure
  warnings derived from that evidence.

Treating both as one more memory rank is unsafe. Raw evidence is not current
truth, an observed session outcome is not item-level causality, and generated
consolidation can corrupt useful episodic detail. ADR-008 also records a recent
measured rejection of an L2 scene layer: a new derived layer must not recreate
that architecture without its own pre-registered evidence.

The local ADR context index returned no governing record for this proposal.
ADR-008 is the adjacent Accepted decision and constrains the evidence bar: no
new retrieval tier enters the hot path merely because an oracle suggests value.

## Decision Drivers

* Raw evidence must remain recoverable and auditable after consolidation.
* A useful experience must distinguish observation, interpretation, outcome,
  and attribution strength.
* The normal interactive path must not pay for optional deeper recall.
* Evaluation must be written before implementation and include reject gates.
* Local-only operation and fail-open client integration remain mandatory.
* Existing wiki and memory ranking must remain the control arm.
* New procedures and skills require repeated evidence and owner approval.

## Considered Options

* Add raw sources and experiences to the existing `kb-index.db` ranking.
* Add one combined third vector database for raw and experience content.
* Add two separately routed, rebuildable projections with independent gates.
* Keep the current system and use direct file search when evidence is needed.

## Decision Outcome

Chosen proposal: **add two separately routed, rebuildable projections with
independent gates**, subject to TASK-220 passing and explicit owner acceptance.

Source recall uses a derived local index over approved raw roots. It is entered
only in explicit, verification, reconstruction, or measured low-confidence
fallback modes. Every hit carries stable source identity, hash, passage
location, and surrounding context. It cannot write or promote memory.

Experience storage uses append-only events and outcome evidence as its durable
record. Derived experience items carry situation, approach, observed result,
lesson, applicability, uncertainty, and evidence links. Candidate, unknown,
superseded, and retracted items cannot masquerade as validated lessons.

The projections are separate from the existing wiki/memory index and from each
other. They may reuse the local SQLite/sqlite-vec implementation, but not a
unified score or hosted dependency. Default hot-path routing stays disabled
until the evaluation packet passes.

### Confirmation

Implementation and value are verified in this order:

1. contract tests and golden fixtures are committed while the feature modules
   are absent or failing;
2. source and experience implementations make those tests pass;
3. paired arms compare current recall, source recall, and experience recall on
   frozen holdout data;
4. live-vault evidence is reported only as aggregate metrics and source ids,
   never committed raw private content;
5. adversarial review tries to falsify provenance, usefulness, latency, and
   attribution claims;
6. the owner reviews the packet and explicitly accepts, rejects, or requests a
   new experiment.

## Decision Contract

### Must

* Keep raw source files authoritative and derived databases rebuildable.
* Keep source, memory/wiki, and experience results visibly distinct.
* Record `unknown` when outcome evidence is insufficient.
* Preserve exact evidence links through supersession and retraction.
* Keep normal recall unchanged while experimental routes are disabled.
* Run extraction and consolidation off the prompt hot path.
* Pre-register and enforce minimum sample sizes and reject thresholds.

### Must Not

* Flatten all layers into one ranking without a separate accepted decision.
* Infer item-level causality from a session-level outcome.
* Promote an LLM-generated lesson without source and outcome evidence.
* Enable autonomous deletion, skill creation, or outcome-based ranking here.
* Send raw source or experience data to a hosted service by default.
* Claim downstream task improvement from retrieval-only measurements.

### Exceptions

Explicit diagnostic commands may query candidate or unknown experiences when
their status is included in the response. They remain excluded from normal
recall and cannot pass a validation gate.

### Verification

* `tests/test_source_recall.py`
* `tests/test_build_source_index.py`
* `tests/test_outcome_ledger.py`
* `tests/test_experience_store.py`
* `tests/test_experience_recall.py`
* `tests/test_layer_eval.py`
* `docs/research/source-experience-evaluation-plan.md`
* TASK-220 evidence report and the full repository test suite

## Consequences

### Positive

* Answers can recover exact raw evidence without pretending it is current
  consolidated truth.
* Repeated successes and failures can become inspectable experience records.
* Negative or inconclusive evidence can reject either feature independently.
* The design remains local, auditable, and compatible with current fail-open
  clients.

### Negative

* Two projections add schemas, rebuild work, migration, and maintenance.
* Outcome attribution remains noisy until enough real sessions accumulate.
* Raw-source indexing increases local storage and privacy exposure.
* Passing retrieval metrics does not prove that future tasks finish better;
  longitudinal outcome evidence remains a later gate.

## Pros and Cons of the Options

### Add both to the existing ranking

* Good, because it reuses one query and one index.
* Bad, because incomparable semantics and score distributions compete directly
  and normal recall pays the latency and regression risk.

### Add one combined third vector database

* Good, because deployment has one new file.
* Bad, because raw evidence and validated experience still require different
  lifecycle, status, routing, and authority rules; one database does not remove
  that complexity.

### Add separately routed projections

* Good, because each layer can be measured, disabled, rebuilt, and rejected
  independently.
* Bad, because it requires explicit routing and more operational checks.

### Keep direct file search only

* Good, because no new persistent state is added.
* Bad, because unknown-source retrieval remains slow and outcome-linked reuse
  remains absent.

## Open Questions

- [ ] Does source recall clear its absolute and baseline-relative retrieval gates on the frozen live-vault holdout?
- [ ] Does experience recall improve retrieval of validated success and failure patterns without exceeding the false-warning gate?
- [ ] Is either layer valuable enough to enable a fallback route, or should it remain explicit-only?
- [ ] Is there enough longitudinal outcome evidence to test task improvement, or must outcome-aware ranking remain deferred?

## Related Decisions

* ADR-008 removes the rejected L2 scene retrieval layer and sets the adjacent
  evidence precedent.
* ADR-009 fixes the default embedding model used by local derived indexes.

## References

* `docs/research/agent-memory-field-review-and-strategy.md`
* `docs/research/l2-scene-retrieval-2026-08.md`
* `docs/research/source-experience-evaluation-plan.md`
* TASK-172, TASK-173, TASK-175, TASK-177, TASK-179, and TASK-211 through
  TASK-222.
* Reflexion: https://arxiv.org/abs/2303.11366
* ExpeL: https://arxiv.org/abs/2308.10144
* ProjectMem: https://arxiv.org/abs/2606.12329
* SWE-Exp: https://arxiv.org/abs/2507.23361
* Memp: https://arxiv.org/abs/2508.06433
* EverOS: https://github.com/EverMind-AI/EverOS/blob/main/docs/how-memory-works.md
* Useful Memories Become Faulty: https://arxiv.org/abs/2605.12978

