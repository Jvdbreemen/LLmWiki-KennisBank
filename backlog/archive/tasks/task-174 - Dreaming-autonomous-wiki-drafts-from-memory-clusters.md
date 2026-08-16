---
id: TASK-174
title: Dreaming — autonomous wiki drafts from memory clusters
status: To Do
assignee: []
created_date: '2026-08-15 11:00'
updated_date: '2026-08-15 22:40'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner directive, 2026-08-15: research the dreaming pattern and use it to come
up with NEW wiki articles when the memory clusters point at one. This upgrades
the earlier version of this task (automate the distillation proposal) from
surfacing a suggestion to autonomously WRITING the draft.

The field's versions of dreaming, for the research half:

- **Honcho's dream pass** (AGPL — ideas only): pattern identification,
  hypothesis testing, conflict resolution, run asynchronously to optimize
  representations. The triad's other two legs already exist here
  deterministically (conflict-scan / kb-state-audit; the supersede pass);
  this task is the pattern-identification leg.
- **Generative Agents' reflection**: periodically synthesize higher-level
  insights from clusters of related low-level records — the canonical shape.
- **EverMemOS MemScenes** (arXiv 2601.02163, Apache 2.0): LLM-consolidated
  thematic scenes over episodic cells. Directly relevant measurement lesson
  from this vault's own TASK-134: graph-community clustering was NOT good
  enough to clear the winner rule, and the oracle said the tier pays only
  with much better clusters. So the clusterer for dreaming should start from
  LLM-consolidated themes, not graph communities — the arm the L2 experiment
  never ran.
- **EverOS's offline evolution** (Apache 2.0): "merges episode clusters and
  refines profiles between sessions" — readable prior art for the scheduling
  and merge mechanics.

Mechanism (KennisBank-native):

- **Off-hours, off the hot path** (idle or scheduled; never session start).
  Local model only. Silent when nothing qualifies (principle #4).
- **Cluster the current memory layer** into candidate themes (LLM
  consolidation over embedding neighborhoods; vectors already live in
  kb-index.db, the TASK-134 harness knows how to read them).
- **The trigger is a gap**: a cluster qualifies when it is dense AND no wiki
  article covers it — checked against the provenance/coupling keys and
  wikilink graph, not guessed. Dense-and-covered clusters instead propose an
  UPDATE to the existing article (smaller, separate output).
- **Write the draft into the vault** as a real markdown article marked
  `status: draft`, with full provenance: source memory wikilinks, model_id +
  prompt version (TASK-90 E5), and the cluster's coherence score. Drafts are
  visible in Obsidian and in the wiki status counts immediately.
- **The merge into the curated wiki stays human.** The owner's no-human rule
  was stated for the MEMORY layer; the wiki is the layer the human reads, and
  a draft in the vault is already fully autonomous production — promotion of
  draft → published article is the one remaining editorial act. Recorded as
  an assumption the owner can override.
- **Anti-noise gate**: a bounded number of drafts per run, a coherence
  threshold, and the TASK-165 lesson (Dutch summaries of English sources
  cost retrieval) — drafts carry their sources rather than re-summarising
  them, in English per the repo language policy.

Measured before default-on (the TASK-177 pattern): a hand-checked sample of
generated drafts with the acceptance rate recorded; if the human would have
rejected most, the trigger threshold rises or the default flips off, and that
is the finding.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Research note in docs/research comparing the four dreaming variants (Honcho, Generative Agents, EverMemOS, EverOS) and stating which mechanics this design takes from each and why
- [ ] #2 A dream pass runs off-hours, clusters current memories via LLM consolidation (not graph communities), and identifies gap-clusters against the wikilink/provenance graph
- [ ] #3 Qualifying clusters produce draft articles in the vault: status draft, source-memory wikilinks, model and prompt-version provenance, coherence score
- [ ] #4 Dense-but-covered clusters produce update proposals to the existing article, not duplicate drafts
- [ ] #5 Draft-to-published promotion remains a human act; nothing autonomous edits a published article
- [ ] #6 Bounded output per run; silent when nothing qualifies; session start and recall untouched
- [ ] #7 Hand-checked acceptance rate on real drafts recorded before default-on; below threshold the default flips off and that is the finding
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
<!-- SECTION:NOTES:END -->

## Close-out (2026-08-16) — parked

Parked, owner directive intact and untouched: no research note comparing the four dreaming variants exists, no clustering or draft-writing code exists, and 'dream' appears in the repo only inside the two research reviews that motivated the task. This description is itself the design document — it carries the TASK-134 clustering lesson (graph communities did not clear the winner rule; start from LLM-consolidated themes, per docs/research/l2-scene-retrieval-2026-08.md), the TASK-165 language lesson, the human-promotion assumption, and the anti-noise gates — so archive it intact or move that design into a docs/design note first. Prior-art pointers (Honcho dream pass, Generative Agents reflection, EverMemOS MemScenes, EverOS offline evolution) are also recorded in docs/research/agent-memory-field-review-and-strategy.md. Not do-now: AC#1 alone (the comparative research note) is more than an hour, and the pass itself is a full feature with a measured default-on gate.

**Evidence:** 'dream' matches nothing in the repo outside docs/research/agent-memory-field-review-and-strategy.md and docs/research/honcho-memory-architecture.md; no dream-pass script in scripts/, no four-variant research note in docs/research/ (glob of all 18 files checked); commit 1b2f855 records the owner directive ('three owner directives — autonomous memory, dreaming, and the usage sensor they stand on'); CHANGELOG.md:38-40 lists it as queued.

**Remaining work (when reopened):** Write the four-variant research note (AC#1); build the off-hours dream pass: LLM-consolidation clustering over kb-index.db vectors, gap detection against the wikilink/provenance graph, bounded draft articles with status: draft and full provenance, update proposals for dense-but-covered clusters; keep draft-to-published human; hand-check an acceptance-rate sample before default-on and let the number decide the default.
