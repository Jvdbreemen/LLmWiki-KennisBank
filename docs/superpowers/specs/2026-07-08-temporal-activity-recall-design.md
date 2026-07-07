# Temporal Activity Recall Design

Date: 2026-07-08  
Status: accepted for local implementation  
Epic: TASK-25

## Decision

KennisBank adds a local Temporal Activity Recall layer as a file/SQLite-first
index over existing vault evidence. The baseline is deterministic, auditable,
and local:

- activity sources remain the existing markdown/transcript/SQLite files in the
  vault;
- the derived index is `<vault>/.claude/kb-activity.db`;
- commands and MCP tools call the same Python API;
- Ollama or cloud LLMs are never required for date resolution, source
  provenance, indexing, or basic retrieval.

This deliberately does not introduce a hosted memory service or mandatory graph
database. A later graph layer may be justified only if a measured eval set shows
that topic/entity timelines cannot meet recall/order/source-ref thresholds with
the SQLite baseline.

## Research Synthesis

| System | Pattern worth taking | Pattern rejected or deferred | KennisBank decision |
|---|---|---|---|
| Mem0 | Memory lifecycle, extraction/consolidation/retrieval separation, and benchmark thinking for temporal/multi-hop questions. | Hosted memory as a runtime requirement; opaque store ownership. | Keep lifecycle separation, add `kb-activity-eval.py`, keep storage local. |
| Zep/Graphiti | Temporal context graph, provenance to source episodes, facts that change over time, hybrid retrieval over entities/facts. | Mandatory graph DB/Neo4j in the default path. | Model bitemporal activity fields now; use SQLite entity/topic tables and FTS5 first. |
| Letta/MemGPT | Stateful agent memory split between always-visible core memory and queried archival/recall memory; explicit memory mutation tools. | Letting the model be the sole authority for what happened when. | Temporal recall is queried on demand via commands/MCP; event_time/source_ref stay deterministic. |
| ClawMem | On-device memory for coding agents, hooks plus MCP server, no API keys/cloud dependency. | Treating generic semantic recall as sufficient for "what happened last week" questions. | Use the same local MCP shape, but add first-class temporal tools: `what_did_i_do`, `timeline`, `weeklog`, `topic_timeline`. |

Primary references:

- Mem0 documentation: https://docs.mem0.ai/introduction
- Mem0 paper: https://arxiv.org/abs/2504.19413
- Graphiti/Zep overview: https://help.getzep.com/graphiti/getting-started/overview
- Zep temporal knowledge graph paper: https://arxiv.org/html/2501.13956v1
- Letta stateful agents: https://docs.letta.com/guides/core-concepts/stateful-agents/
- Letta archival memory: https://docs.letta.com/guides/core-concepts/memory/archival-memory/
- ClawMem: https://github.com/yoloshii/clawmem

## Data Flow

```text
01-raw/sessies/*.md
01-raw/transcripts/*.jsonl
09-memory/**/*.md
02-wiki/**/*.md
.claude/kb-usage.db
        |
        v
canonical ActivityEvent extraction
        |
        v
<vault>/.claude/kb-activity.db
  activity_events
  activity_entities
  activity_topics
  activity_artifacts
  source_watermarks
  rollup_cache
  activity_fts
        |
        v
shared Python API
  what_did_i_do()
  timeline()
  topic_timeline()
  weeklog()
        |
        +--> commands/weeklog.md, commands/timeline.md, commands/watdeedik.md
        +--> MCP tools in kb-mcp.py
        +--> eval harness kb-activity-eval.py
```

## Canonical Activity Event

Every event has these fields:

- `id`: stable SHA-256 based ID from source kind, source path, span, kind, time
  and summary.
- `source_kind`: `raw_session`, `transcript`, `memory`, `wiki`, `usage`.
- `source_path`: vault-relative path.
- `source_ref`: vault-relative path plus span, e.g.
  `01-raw/sessies/raw-sessie-2026-07-03.md#L12`.
- `event_time`: when the work happened. Local vault dates use
  `Europe/Amsterdam`.
- `captured_at`: when the source was captured/modified/indexed.
- `timezone`: explicit timezone name.
- `actor`, `agent`, `project`, `repo`.
- `activity_kind`: `session`, `tool_use`, `decision`, `task_change`,
  `memory_capture`, `wiki_update`, `release`, `commit`, `fix`,
  `external_research`, `memory_use`, or fallback activity kinds.
- `title`, `summary`.
- `topic_tags`, `entities`, `artifacts`, `decisions`.
- `confidence`: deterministic confidence from source quality.
- `provenance_span`: file or line span.
- `unknown_time`: true when event_time had to fall back to file/capture time.

`event_time` and `captured_at` are intentionally separate. A late import of an
old session keeps the old activity date while still recording the modern capture
time. This mirrors the bitemporal lesson from temporal graph systems without
making graph infrastructure mandatory.

## Temporal Parsing

The parser is deterministic and testable with injected `now`:

- Dutch and English relative periods: `vandaag`, `gisteren`, `eergisteren`,
  `vorige week`, `deze week`, `vorige maand`, `afgelopen 7 dagen`, `today`,
  `yesterday`, `last week`.
- Absolute dates: `2026-07-03`, `3 juli 2026`, `July 3 2026`.
- Ranges: `tussen 2026-07-01 en 2026-07-07`,
  `from 2026-07-01 to 2026-07-07`, `van maandag tot vrijdag`.
- Topic extraction: `onderwerp "Codex MCP" vorige week` and
  `topic "OpenRouter" last week`.

`vorige week` uses the local ISO week model: Monday 00:00 inclusive to the next
Monday 00:00 exclusive, in `Europe/Amsterdam`.

Ambiguous numeric dates such as `03/07/2026` return a structured error with
suggestions instead of guessing.

## Retrieval Semantics

Range filtering is hard. No event outside `[start, end_exclusive)` is returned
unless a future API explicitly asks for context-before/context-after and marks it
as such.

Topic relevance is ranking/filtering within the period:

1. explicit entity match;
2. explicit topic/tag match;
3. alias match from `<vault>/.claude/activity-topic-aliases.json`;
4. FTS/plain text match over title, summary, entities, topics and source path;
5. optional semantic enrichment in a future task, never required for baseline.

Outputs include structured JSON for tests/MCP and compact markdown for commands.
Every event carries source refs. If an index is missing or stale, callers receive
a recoverable warning and a build command, not a traceback.

## Rollups

Daily/weekly rollups are derived cache entries, never source of truth. The cache
key includes the period/topic and a source signature built from indexed event IDs
and source watermarks. A stale source signature invalidates the cache.

The deterministic skeleton contains:

- event counts by `activity_kind`;
- key events;
- decisions;
- releases/commits/task changes;
- open loops/follow-ups;
- source refs.

LLM-generated prose can be layered later, but it must be marked generated and
must preserve underlying event IDs/source refs.

## Setup, Doctor and Agent Surface

`setup.sh` deploys the activity scripts and commands, builds/refreshed the index
before the final doctor gate, and installs prompt/command aliases for selected
agents. The SessionStart hookset includes `build-activity-index.py`; long runs
emit progress lines at least every 300 seconds.

`doctor.sh` checks:

- `kb-activity.py` and `build-activity-index.py` are deployed;
- `kb-activity.db` exists, is readable, has the expected schema version, and is
  not stale against source watermarks;
- `/weeklog`, `/timeline`, `/watdeedik` are installed;
- MCP temporal wrappers are present when MCP is configured.

`install-agent-envs.py` validates Codex/OpenCode prompts/commands and requires
MCP list-tools to include `recall`, `capture`, `what_did_i_do`, `timeline`,
`weeklog`, and `topic_timeline`.

## Evaluation

`scripts/kb-activity-eval.py` measures:

- date recall;
- period recall;
- topic timeline recall and ordering;
- negative controls for empty periods/topics;
- provenance coverage;
- pass/fail thresholds.

The repo ships a non-personal example eval set. Personal eval cases live under
`<vault>/06-claude/kb-activity-eval-set.json`.

## Failure Modes

1. Wrong date resolution.
   - Mitigation: deterministic parser, injected `now`, explicit timezone,
     structured errors for ambiguous dates, tests around week/month/DST/year
     boundaries.
2. Hallucinated summaries without provenance.
   - Mitigation: event outputs are source-first; rollups are derived from event
     IDs/source refs; no LLM is required for baseline summaries.
3. Slow backfill or index rebuild.
   - Mitigation: source watermarks, incremental upsert, WAL readers,
     `--full` rebuild for repair, progress output at least every 300 seconds.
4. Missing or corrupt index.
   - Mitigation: commands/MCP fail open with a repair instruction; setup builds
     the index; doctor detects missing/corrupt/stale states.
5. Topic drift or aliases missing.
   - Mitigation: local alias config, FTS/entity matching fallback, eval cases for
     topic timelines.

## Migration and Compatibility

Existing vaults without `kb-activity.db` continue to work. On upgrade,
`setup.sh` copies the new scripts/commands, builds the index, registers the
SessionStart rebuild hook, and doctor reports the index status. The database is
a derived cache and can be deleted safely:

```bash
python3 <vault>/.claude/scripts/build-activity-index.py --vault <vault> --full
```

No existing wiki, memory, transcript, command, or model config file is migrated
in place for this feature. The only new optional user config is
`<vault>/.claude/activity-topic-aliases.json`.
