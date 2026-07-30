---
id: TASK-118
title: >-
  Critical: embedding endpoint is attacker-controllable and the no-cloud guard
  is vacuous
status: Done
assignee: []
created_date: '2026-07-30 09:52'
updated_date: '2026-07-30 18:12'
labels: []
dependencies: []
ordinal: 116700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the comprehensive review security audit and independently reproduced. Two defects compose into total confidentiality loss on the one asset the project promises to keep local. FIRST, the guard does nothing: tests/test_kb_recall_nocloud.py:33 scans FILES = ["kb-recall.py", "_kbindex.py"] for external hosts, and both files contain ZERO URLs (verified), so the assertion loop body never executes and the test has always passed vacuously. The modules that actually open sockets are all outside the list: _embeddings.py (api.openai.com, api.voyageai.com), _llm.py (openrouter.ai), install-agent-envs.py. The test docstring excludes _embeddings.py deliberately "because it holds opt-in cloud endpoints", which misses that it is the only module kb-retrieve.py calls on every prompt. SECOND, the sink is unguarded and needs no credential: _embeddings.py:138-145 handles the ollama branch BEFORE the API-key check at :147-149 and takes the endpoint verbatim from $VAULT/.claude/kennisbank-embed.json. Reproduced with a loopback listener and no OPENAI_API_KEY: writing {"provider":"ollama","endpoint":"http://<host>"} caused embed() to POST the full prompt text to that host, and memory-doctor.cloud_warnings() returned []. Two sinks: every prompt (kb-retrieve.py:347,369 passes data["prompt"] straight to embed()), and the whole vault (changing provider or model changes embed_id(), invalidating the cache at :279, so the next index build re-embeds every article and memory and sends the first 4000 bytes of each). Attack path: an ingested document or fetched page becomes a wiki article, is later retrieved into the agent context, and instructs the agent to write that config file. The agent has Write. No key, no warning on any surface, no test that would go red. Note memory-doctor._is_local_endpoint (:31-47) is already exactly the right check (strict urlparse plus ipaddress.is_loopback, immune to the localhost.evil.com trick) but is called only on the LLM endpoint at :67, never on the embedding endpoint.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 _embeddings.embed refuses a non-loopback endpoint for a local-only provider, overridable only by an explicit env opt-in, and says so on stderr
- [x] #2 A cloud provider prints a CLOUD warning on the embedding path as _llm.generate already does on the generation path
- [x] #3 memory-doctor.cloud_warnings() covers the embedding endpoint, reusing _is_local_endpoint rather than a fourth parser
- [x] #4 The no-cloud guard scans the modules that actually network, not two files without URLs
- [x] #5 A test asserts the scan is not vacuous: at least one URL must be found or the guard fails
- [x] #6 A runtime test proves a redirected config is refused without a request being issued
- [ ] #7 pytest suite green
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Locality is now enforced at the sink instead of by scanning source text. _embeddings.endpoint_allowed() refuses a non-loopback endpoint for a local-only provider before any request is issued, overridable only by an explicit KB_EMBED_ALLOW_REMOTE, and prints a CLOUD warning for a cloud provider the way _llm.generate already did on the generation path. is_local_endpoint uses strict urlparse plus ipaddress.is_loopback, so subdomain and query-string spoofs do not pass. memory-doctor.cloud_warnings() now also inspects the embed chain, which it never did. Verified end to end against a loopback listener with a TEST-NET-2 endpoint in kennisbank-embed.json: before the fix the full prompt text arrived at the remote host and cloud_warnings() was empty; after it, embed() returns None, ZERO requests reach the listener, stderr carries the refusal, and cloud_warnings() reports the non-local embed endpoint. The guard itself was rewritten: it now scans the modules that actually open sockets (_embeddings.py and _llm.py joined the list), carries a test_scan_is_not_vacuous meta-assertion so a URL-free file list can never again pass silently, adds a runtime test that a redirected config is refused, and pins three hostname spoofs. Worth recording: the repaired scan immediately caught a spoof example I had put in a docstring, which is the guard doing its job - the example moved into the test where it belongs.
<!-- SECTION:FINAL_SUMMARY:END -->
