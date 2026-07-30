---
id: TASK-114
title: Review the agent-authored revisions to c4-container.md and c4-context.md
status: Done
assignee:
  - '@claude'
created_date: '2026-07-30 05:44'
updated_date: '2026-07-30 18:03'
labels:
  - docs
  - c4
  - review
dependencies: []
ordinal: 116700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two verification passes revised the container and context documents on top of commit 94000ec, producing 469 insertions and 210 deletions across the two files. The revisions were made by automated passes that also misreported their own provenance (each claimed the file pre-existed the session when it had just been written), so the content needs a human read before it is trusted, even though the substantive corrections it carries were independently verified.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The diff of both files against 94000ec is read and each substantive change is either accepted or reverted, with the reasoning recorded
- [x] #2 The container document's five-container set (Script Layer, Vault Data Store, MCP Server, Atlas Desktop Application, GitHub Actions CI Runner) is confirmed or corrected, including the two deliberate boundary calls it defends: index-launch.py staying inside the Script Layer, and the four databases sharing one container with the markdown vault
- [x] #3 The context document's two attribution findings are checked: that VALUES.md claims an up-front warning for cloud calls where only a configuration-time warning exists in setup.sh:225, and the second finding recorded in the same section
- [x] #4 Both documents' provenance claims are corrected: neither may state that it pre-existed the session that wrote it
- [x] #5 The outcome is committed on docs/c4-architecture, or the files are restored to 94000ec, so the working tree is clean either way
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reviewed as a committed diff (94000ec..efc8927, 469 insertions, 210 deletions), verified against primary source rather than against the documents' own assertions.

The provenance criterion turned out to be moot, and that is worth recording rather than quietly ticking. Neither document contains a provenance claim. The confabulation ('this file already existed before this session') appeared only in the automated passes' summaries to the operator, never in the files. Nothing to correct. The only self-referential statements are a synthesis list and two honest scope notes, and all eleven paths cited in that list exist.

Substantive corrections applied, all verified in code first:

1. claude-cli restored to the consent boundary in the context document. CLOUD_PROVIDERS = {"openrouter", "claude-cli"} (scripts/_llm.py:30) and the provider shells out to , so the diff's deletion had narrowed the boundary to exclude a genuine cloud path. This was the most consequential finding: claude-cli is offered by neither setup.sh (which lists ollama and openrouter only, :207-210) nor install-agent-envs.py:1095, so it is the one cloud provider with no configuration-time warning at all, and it was precisely the one the diff dropped from the consent statement.
2. 'OpenRouter is the one place cloud generation is possible at all' was false and introduced by the diff. Replaced with the two-provider statement and its citation.
3. The unchecked hedge about a per-call warning is now answered instead of deferred: scripts/_llm.py:164-168 warns on stderr before every cloud call, for any CLOUD_PROVIDERS member. The coverage is inverted from what the setup-time warning implies, and that inversion is what makes claude-cli safe to use at all. Also noted that VALUES.md calls it a warning gate while neither site gates; both only echo.
4. Two support facts in the container document's 8.3 were wrong. The worker does not exit on a stale lock: STALE_SEC is read only by acquire_lock() on the non-worker path (index-launch.py:105), where it lets a later launch reclaim a lock left by a killed worker. And _hooks_manifest.py is not the worker's config: it lists hook scripts only (:12-22), and the worker's entire configuration surface is one _settings.get('memory_capture') read (:119-127). Both corrected in the summary table and in 8.3. The argument they were supporting survives intact; only the supporting facts were wrong.
5. Two counting errors fixed: 'the six c4-component-*.md files' (there are seven) and 'a fifth KennisBank container' (with five real containers it would be the sixth, and it sat directly above 8.3's 'not a sixth container').

The five-container set is confirmed as defensible. One premise in the task's own wording does not hold and should not be read as a defect: components do not map one-to-one onto containers. Measurement and Outward Integration is split across containers 1 and 3, Agent Integration's commands and skills land in no KennisBank container because that reasoning loop runs inside the harness, and Distribution and Quality Gate spans container 5, container 2 and neither. The document never claimed one-to-one; its own column is slice-qualified.

Left alone deliberately: _copilot.py is attributed to two components (c4-container.md:85 and :89). Pre-existing, predates this diff, and has no container-level consequence. Worth a separate task if it bothers anyone; not worth widening this one.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Reviews the automated container and context revisions committed at efc8927 and corrects what the review found, verified against source rather than against the documents' claims.

The headline finding is privacy-relevant. The diff had removed claude-cli from the context document's consent boundary and asserted that OpenRouter is the only route to cloud generation. Both are wrong: CLOUD_PROVIDERS is {openrouter, claude-cli} (scripts/_llm.py:30) and claude-cli shells out to the claude binary. It is also the provider with the weakest configuration-time protection, because neither setup.sh nor install-agent-envs.py offers it, so it is reachable only through kennisbank-llm.json or KB_LLM_PROVIDERS. Restored to the consent boundary, with the false claim replaced.

The document's open hedge about whether a per-call cloud warning exists is now answered rather than deferred: scripts/_llm.py:164-168 warns before every cloud call for any cloud provider, which is broader coverage than the setup-time warning at setup.sh:225, and it is the only warning a claude-cli user ever sees.

Two supporting facts in the container document's section 8.3 were wrong and are corrected: the detached worker does not exit on a stale lock (STALE_SEC belongs to acquire_lock on the non-worker path), and _hooks_manifest.py is not its config file (its surface is a single memory_capture settings read). The argument those facts supported is sound and stands.

Two counting errors fixed: six versus seven component documents, and a fifth versus sixth container.

The provenance criterion was moot: neither document ever claimed to pre-date the session that wrote it. That fiction lived only in the agents' summaries.

Nothing was reverted wholesale; the diff's substance is sound apart from the items above.

Tests: tests/test_docs_consistency.py, 5 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
