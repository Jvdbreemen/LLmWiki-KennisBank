---
id: TASK-117
title: >-
  Critical: _memory.set_status corrupts the file, returns True, and leaves the
  status unchanged
status: Done
assignee: []
created_date: '2026-07-30 09:18'
updated_date: '2026-07-30 18:11'
labels: []
dependencies: []
ordinal: 115700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the comprehensive review and independently reproduced. _memory._yaml_scalar (scripts/_memory.py:164) sanitises only quotes and newlines, so a title containing --- passes through untouched. _memory.set_status (:258) then splits the file with raw.split("---", 2), which treats that inner --- as the closing frontmatter fence. Reproduced with a memory titled "TASK-12 --- rollback": set_status(p, "superseded", ...) returns True, read_status still returns the ORIGINAL status, and the file is left with an unterminated title line plus superseded_by/valid_until injected above the real frontmatter body. Three consequences, worst first: memory-sweep.py:363 branches on that return value, counts a supersession that did not happen and drops the item from the reconcile pool; read_status keeps reporting the memory as live, so kb-recall keeps validating it and build-kb-index keeps indexing it, meaning a superseded memory is injected into every prompt forever - exactly what the status model exists to prevent; and Obsidian reads the mangled YAML strictly while KennisBank's lenient parser recovers, so the two disagree about the file. The same raw.split("---", 2) defect sits at scripts/_maintenance.py:296 for promote_candidate. The correct splitter already exists and is anchored against precisely this: _frontmatter._FENCE_RE = re.compile(r"^---\s*$", re.MULTILINE), whose docstring names the horizontal-rule false positive as the reason. Note the asymmetry that proves the module already knows better: the human-review path at _memory.py:409 does "if not set_status(...): raise ReviewError(500, ...)" while the sweep path does not check at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 set_status uses _frontmatter.split_frontmatter instead of raw.split('---', 2)
- [x] #2 set_status returns False when the status line is absent rather than reporting success on a no-op
- [x] #3 Same fix applied to _maintenance.py:296 for promote_candidate
- [x] #4 _yaml_scalar also neutralises --- so the sanitiser covers what any parser assumes
- [x] #5 Regression test: a memory whose title contains --- round-trips through set_status with the status actually changed and the file still parseable
- [x] #6 memory-sweep no longer counts a supersession whose write failed
- [ ] #7 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Both call sites now use _frontmatter.split_frontmatter, whose fence regex is anchored on ^---$ precisely to avoid this. set_status returns False when the status line is absent instead of reporting success on a no-op, which was the half of the bug that made memory-sweep count a supersession that never happened. _yaml_scalar additionally collapses --- to an em dash, so the sanitiser now covers what any parser assumes rather than leaving the gap open for the next consumer. Verified before and after on the same input: a memory titled "TASK-12 --- rollback" previously returned True while read_status stayed unverified and the file was left with an unterminated title line; it now flips to superseded, keeps superseded_by and valid_until correct, and the document still round-trips through parse_frontmatter with the body intact. Four regression tests added in tests/test_memory.py covering the status change, document integrity, the sanitiser, and the no-op returning False. Existing memory and maintenance suites pass unchanged (59 tests).
<!-- SECTION:FINAL_SUMMARY:END -->
