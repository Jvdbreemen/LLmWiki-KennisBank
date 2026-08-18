# C4 Code Level: Scripts

## Overview

- **Name**: KennisBank Scripts Layer
- **Description**: The core Python script layer providing CLI tools, library modules, and daemon processes for the KennisBank knowledge management system. Implements retrieval, indexing, memory management, LLM routing, and administrative operations.
- **Location**: [`scripts/`](../../scripts/)
- **Language**: Python 3.9+
- **Purpose**: Orchestrate all backend operations—knowledge indexing, retrieval, memory lifecycle management, session coordination, and third-party integrations (GitHub Copilot, Claude).

## Architecture

The scripts layer comprises **three tiers**:

### 1. Foundation Modules (_*.py)
Stdlib-only or minimal dependencies, providing core abstractions used everywhere:
- **Path/config resolution**: vault discovery, settings management
- **Data parsing**: frontmatter, documents, LLM JSON responses
- **Pluggable backends**: LLM routing, embedding providers
- **Data structures**: memory schema, activity models, index schema

### 2. Feature Modules (_*.py, larger)
Domain logic combining multiple foundation modules:
- **Knowledge indexing** (`_kbindex.py`, `_embeddings.py`)
- **Memory system** (`_memory.py`, `_reconcile.py`, `_maintenance.py`)
- **Activity tracking** (`_activity.py`)
- **Usage & ranking** (`_usage.py`, `_rank.py`)
- **Integrations** (`_copilot.py`, `_llm.py`)

### 3. CLI/Daemon Scripts (kb-*.py, build-*.py, etc.)
Entry points for user interaction and scheduled work:
- **Retrieval hooks** (`kb-retrieve.py`, `kb-recall.py`)
- **Index builders** (`build-kb-index.py`, `build-embed-index.py`)
- **Maintenance jobs** (`memory-sweep.py`, `kb-state-audit.py`)
- **Importers** (`import-*.py`, `kb-copilot-capture.py`)
- **Session coordination** (`kb-session-start.py`, `kb-session-end.py`)
- **User queries** (`kb-ask.py`, `kb-search.py`)

---

## Code Elements

### Foundation Modules

#### _vaultpath.py
**Purpose**: Single source of truth for vault-root resolution. All scripts resolve the vault consistently.

- `vault_root() → Path`
  - Returns the vault root, respecting `KENNISBANK_VAULT` env var, installed script detection, or `~/KennisBank` default.
  - **Location**: [_vaultpath.py:48](../../scripts/_vaultpath.py#L48)
  - **Dependencies**: os, pathlib
  - **Key behavior**: Installed scripts stay anchored to their vault even when KENNISBANK_VAULT is unset (prevents cross-vault bleed, TASK-181).

- `_script_vault() → Path | None`
  - Detects if this script is installed in `<vault>/.claude/scripts/`.
  - **Location**: [_vaultpath.py:28](../../scripts/_vaultpath.py#L28)

#### _common.py
**Purpose**: Shared utilities duplicated verbatim across scripts.

**Functions**:
- `env_int(name: str, default: int) → int`
  - Fail-soft numeric env-var reader; malformed values return default (TASK-185).
  - **Location**: [_common.py:24](../../scripts/_common.py#L24)

- `env_float(name: str, default: float) → float`
  - Float twin of env_int with same fallback contract.
  - **Location**: [_common.py:37](../../scripts/_common.py#L37)

- `pid_alive(pid) → bool`
  - Canonical liveness probe for process-level locks (TASK-183). Accounts for Windows zombie semantics.
  - **Location**: [_common.py:46](../../scripts/_common.py#L46)

- `outside_window(age: float, window: float) → bool`
  - Symmetric staleness check: |age| > window. Guards against clock skew.
  - **Location**: [_common.py:89](../../scripts/_common.py#L89)

- `slugify(text: str, max_len: int = 50) → str`
  - Filename-safe slug from arbitrary text. Normalizes whitespace/punctuation.
  - **Location**: [_common.py:101](../../scripts/_common.py#L101)

- `_utcnow_iso() → str` / `_today_iso() → str`
  - UTC timestamp helpers for ISO dating.
  - **Location**: [_common.py:111-116](../../scripts/_common.py#L111)

- `print_summary(summary: dict, as_json: bool) → None`
  - Render import summary (JSON or one-line text).
  - **Location**: [_common.py:119](../../scripts/_common.py#L119)

#### _settings.py
**Purpose**: Toggle-based settings system for background automation. Single JSON file on vault root.

**Key Data**:
- `DEFAULTS: dict` — canonical toggles: `auto_archive`, `distill_notify`, `embed_index`, `memory_capture`, `graph_retrieval`, etc.
- Storage: `<vault>/kennisbank-settings.json`

**Functions**:
- `get(key: str, default: bool) → bool`
  - Read a toggle; missing file/key or parse error returns default. Never raises.
  - **Location**: [_settings.py:86](../../scripts/_settings.py#L86)

- `set(key: str, value: bool) → None`
  - Write toggle atomically (tempfile + os.replace). Preserves unknown keys.
  - **Location**: [_settings.py:98](../../scripts/_settings.py#L98)

- `init() → bool` / `migrate() → bool`
  - Initialize or migrate settings file idempotently.
  - **Location**: [_settings.py:119-160](../../scripts/_settings.py#L119)

#### _frontmatter.py
**Purpose**: Parse minimal YAML frontmatter from markdown files.

**Functions**:
- `split_frontmatter(text: str) → tuple[str, str]`
  - Split into (frontmatter_yaml, body). Anchored on closing `---` fence.
  - **Location**: [_frontmatter.py:11](../../scripts/_frontmatter.py#L11)

- `parse_frontmatter(text: str) → tuple[dict, str]`
  - Parse YAML keys into dict. Lists parsed from `[a, b]` form. Quotes stripped.
  - **Location**: [_frontmatter.py:35](../../scripts/_frontmatter.py#L35)

#### _llm.py
**Purpose**: Pluggable LLM routing with local-first design. Tries provider chain in order; first non-empty wins.

**Key Data**:
- Providers: `LOCAL_PROVIDERS = {"ollama"}`, `CLOUD_PROVIDERS = {"openrouter", "claude-cli"}`
- `OLLAMA_DEFAULT_MODEL = "qwen3.5:4b"` — coexists with embedding model on one GPU.
- `OLLAMA_NUM_CTX = 4096` (configurable via `KB_LLM_NUM_CTX`).
- Cloud calls logged loudly to stderr (privacy/transparency, #4).

**Functions**:
- `providers() → list[str]`
  - Return ordered provider chain from env, config, or default.
  - **Location**: [_llm.py:121](../../scripts/_llm.py#L121)

- `model_for(provider: str) → str`
  - Get model name for provider from env, config, or default.
  - **Location**: [_llm.py:132](../../scripts/_llm.py#L132)

- `generate(prompt: str, system: str = "", timeout: float = 120.0) → str | None`
  - Generate text. Tries provider chain. Cloud providers issue loud warnings.
  - **Location**: [_llm.py:201](../../scripts/_llm.py#L201)

- `is_local() → bool`
  - Check if primary provider is local.
  - **Location**: [_llm.py:155](../../scripts/_llm.py#L155)

- `_call(provider, model, endpoint, api_key_env, prompt, system, timeout) → str | None`
  - Single provider call. Handles ollama, openrouter, claude-cli.
  - **Location**: [_llm.py:168](../../scripts/_llm.py#L168)

#### _embeddings.py
**Purpose**: Pluggable embedding backend with cross-model safety guards. Supports ollama, openai, voyage.

**Key Data**:
- `OLLAMA_DEFAULT_EMBED_MODEL = "qwen3-embedding:4b"`
- `OLLAMA_NUM_CTX = 2048` (configurable via `KB_EMBED_NUM_CTX`)
- `EMBED_DOC_CAP = 4000` chars (coupled to num_ctx to prevent Ollama failures)
- `embed_id() → str` — format "provider:model[+doc_prefix]" used for cache validation

**Functions**:
- `embed_id() → str`
  - Stable identity of active backend for cache-keying.
  - **Location**: [_embeddings.py:173](../../scripts/_embeddings.py#L173)

- `provider() → str`
  - Get active embedding provider.
  - **Location**: [_embeddings.py:169](../../scripts/_embeddings.py#L169)

- `cosine(a, b) → float`
  - Cosine similarity with length guard. Mismatched lengths return 0.0 (cross-model truncation trap).
  - **Location**: [_embeddings.py:188](../../scripts/_embeddings.py#L188)

- `cache_file() → Path`
  - Embeddings cache path, resolved at call time (not import time, TASK-196).
  - **Location**: [_embeddings.py:72](../../scripts/_embeddings.py#L72)

#### _frontmatter.py & _liteparse.py
**Purpose**: Document parsing utilities.

**_frontmatter.py functions**:
- `split_frontmatter(text: str) → tuple[str, str]`
- `parse_frontmatter(text: str) → tuple[dict, str]`

**_liteparse.py functions**:
- `is_supported_document(path: Path | str) → bool`
- `parse_document(vault: Path, source: Path, ...) → dict`
- `render_source_markdown(fm: dict, body: str, ...) → str`
- **Location**: [_liteparse.py:81-188](../../scripts/_liteparse.py#L81)

#### _llmjson.py
**Purpose**: Robustly extract first JSON object/array from LLM output.

**Functions**:
- `first_object(raw: str) → dict | None`
- `first_array(raw: str) → list | None`
- **Location**: [_llmjson.py:156-161](../../scripts/_llmjson.py#L156)
- **Key behavior**: Handles common LLM JSON quirks (single quotes, mismatched brackets).

#### _extract.py
**Purpose**: Extract knowledge candidates from transcripts via LLM.

**Functions**:
- `extract_candidates(transcript_text: str, max_n: int = 8) → list`
  - Generate memory candidates from transcript. Filters refusals/meta-answers.
  - **Location**: [_extract.py:68](../../scripts/_extract.py#L68)

- `looks_like_refusal(text: str) → bool`
  - Detect LLM refusal patterns (deterministic, no model call).
  - **Location**: [_extract.py:62](../../scripts/_extract.py#L62)

**Key Data**:
- `EXTRACT_PROMPT_VERSION = 2` — bumped on every EXTRACT_SYSTEM change.
- `REFUSAL_MARKERS` — list of patterns indicating model cannot answer.

#### _judge.py
**Purpose**: Judge extracted memories for importance and type.

**Functions**:
- `judge(candidate: str, context: str = "") → dict`
  - Judge a memory candidate. Returns importance (1-5), type, volatility, etc.
  - **Location**: [_judge.py:46](../../scripts/_judge.py#L46)

#### _memory.py
**Purpose**: Memory schema, frontmatter contract, and classification helpers.

**Key Data**:
- `STATUSES = ("unverified", "current", "superseded", "retracted", "expired")`
- `MEMORY_TYPES = ("feit", "voorkeur", "procedure", "beslissing")`
- `VOLATILITIES = ("state", "event")` — state = replaceable, event = permanent
- `EVIDENCE_BASES = ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent")`

**Functions**:
- `coerce_memory_type(value) → str` — sanitize type; unknown → "feit"
- `coerce_volatility(value, body: str) → str` — determine update axis (state/event) with fallback to config detection
- `coerce_importance(value) → int` — clamp to 1..5; unparseable → 3
- `looks_like_config(text: str) → bool` — detect if memory asserts a current setting
- `looks_like_config_key(key) → bool` — check if loose key is setting-like
- `provenance_tag(evidence_basis, status: str) → str` — short herkomst/status tag
- **Location**: [_memory.py:51-197](../../scripts/_memory.py#L51)

---

### Feature Modules

#### _activity.py
**Purpose**: Activity indexing (SQLite-backed event log) and temporal/period parsing.

**Key Types**:
- `ActivityEvent` — dataclass: id, source_file, activity_class, timestamp, text, entities, topics
- `TemporalRange` — dataclass: start, end, granularity (day/week/month/year), original, topic, confidence

**Major Functions**:

*Activity DB*:
- `activity_db_path(vault: Path | None = None) → Path`
- `connect_activity_db(vault: Path | None = None, readonly: bool = False) → sqlite3.Connection`
- `ensure_schema(conn: sqlite3.Connection) → None`
- `upsert_event(conn: sqlite3.Connection, event: ActivityEvent) → None`
- `build_activity_index(vault: Path, force: bool = False, dry_run: bool = False, ...) → dict`
- **Location**: [_activity.py:162-903](../../scripts/_activity.py#L162)

*Entity/Topic Extraction*:
- `extract_entities(text: str, path: str = "") → list[str]` — pull @-mentions, file paths, URLs
- `extract_topics(text: str, path: str = "") → list[str]` — infer topics from path + text
- `extract_artifacts(text: str) → list[str]` — markdown artifact links
- `classify_activity(text: str, fallback: str = "activity") → str` — categorize event type
- **Location**: [_activity.py:293-340](../../scripts/_activity.py#L293)

*Temporal Parsing (sophisticated, multi-layer)*:
- `parse_period(text: str, now: datetime | None = None, tz: ZoneInfo = LOCAL_TZ, default: str = "today") → TemporalRange`
  - Layer 1 (deterministic): date tokens ("today", "5d ago", "last week", locales in 8+ languages)
  - Layer 2 (dateparser library): generic English phrases
  - Layer 3 (LLM fallback, opt-in via `activity_llm_fallback` setting): exotic/compositional phrasing
  - **Location**: [_activity.py:1354](../../scripts/_activity.py#L1354)

*Queries*:
- `query_events(vault: Path, period: TemporalRange, topic: str = "", ...) → list[ActivityEvent]`
  - Query events with filtering.
  - **Location**: [_activity.py:1787](../../scripts/_activity.py#L1787)

- `what_did_i_do(vault: Path, period: TemporalRange, ...) → dict`
  - Summarize activity in period. Returns counts by class, sorted events.
  - **Location**: [_activity.py:1911](../../scripts/_activity.py#L1911)

#### _kbindex.py
**Purpose**: Knowledge base indexing via SQLite with vector extensions (sqlite-vec).

**Key Functions**:

*Vector Index (kb-index.db)*:
- `index_path() → Path` — returns `<vault>/.claude/kb-index.db`
- `connect(path=None) → sqlite3.Connection` — open index (CREATE if missing)
- `ensure_schema(conn, dim: int, embed_id: str) → None` — create schema with metadata
- `meta_get/meta_set(conn, key, value)` — read/write metadata
- `is_valid_for(conn, embed_id: str) → bool` — check if index is for current embedding model
- `upsert(conn, path: str, layer: str, status: str, hash: str, vector, text: str) → None`
  - Insert/update document vector with metadata.
  - **Location**: [_kbindex.py:180](../../scripts/_kbindex.py#L180)

- `search(conn, query_vector, query_text: str = "", limit: int = 5, status_filter: str = "current", ...) → list`
  - Hybrid search: cosine on vectors + FTS on text, combined via RRF.
  - **Location**: [_kbindex.py:307](../../scripts/_kbindex.py#L307)

- `prune(conn, keep_paths: set, layers=None) → int`
  - Remove indexed documents not in keep_paths.
  - **Location**: [_kbindex.py:235](../../scripts/_kbindex.py#L235)

- `count(conn) → int`
  - Return indexed document count.
  - **Location**: [_kbindex.py:176](../../scripts/_kbindex.py#L176)

*Graph Index (kb-graph.db)*:
- `graph_connect(path=None) → sqlite3.Connection`
- `ensure_graph_schema(conn) → None`
- `replace_graph(conn, nodes, edges) → tuple[int, int]`
  - Upsert full graph (nodes, edges). Returns (node_count, edge_count).
  - **Location**: [_kbindex.py:543](../../scripts/_kbindex.py#L543)

- `graph_neighbors(conn, source_file: str, limit: int = 5, ...) → list`
  - Retrieve neighbors by weighted graph (used in L2 retrieval).
  - **Location**: [_kbindex.py:583](../../scripts/_kbindex.py#L583)

#### _embeddings.py (extended)
**Functions** (not yet listed):
- `load_cache() → dict` — load embeddings cache from file
- `save_cache(data: dict) → None` — atomically persist cache
- `embed(text: str, force_provider: str | None = None) → list[float] | None`
  - Embed text, checking cache first. Returns None on failure (fail-soft).

#### _usage.py
**Purpose**: Track which memories were injected (retrieval feedback loop).

**Functions**:
- `log_injected(stems, session_id: str = "", today: str | None = None) → int`
  - Log that memory stems were injected into a prompt.
  - **Location**: [_usage.py:107](../../scripts/_usage.py#L107)

- `mark_used(stems, today: str | None = None) → int`
  - Mark stems as used (positive signal).
  - **Location**: [_usage.py:157](../../scripts/_usage.py#L157)

- `mark_noise(stems, today: str | None = None) → int`
  - Mark stems as noise (negative signal).
  - **Location**: [_usage.py:174](../../scripts/_usage.py#L174)

- `stats_for(stems) → dict`
  - Get usage stats (injected, used, noise, last_used_days_ago).
  - **Location**: [_usage.py:237](../../scripts/_usage.py#L237)

#### _rank.py
**Purpose**: Multi-factor ranking for memory retrieval (recency, importance, trust, usage, noise, coupling).

**Functions**:
- `recency_factor(age_days: int, memory_type: str = "feit") → float`
- `importance_factor(importance) → float`
- `trust_factor(evidence_basis) → float` — higher for human-in-loop, lower for agent
- `usage_factor(last_used_iso: str, today: date | None = None) → float`
- `noise_factor(noise: int, injected: int) → float`
- `coupling_factor(shared_with: int) → float`
- `rerank(hits: list, meta_fn, today: date | None = None, ...) → list`
  - Rerank hits by combining all factors.
  - **Location**: [_rank.py:38-138](../../scripts/_rank.py#L38)

#### _reconcile.py
**Purpose**: Reconcile new extracted memories against existing ones.

**Functions**:
- `similar_existing(vec, items: list, threshold: float = RECONCILE_THRESHOLD) → dict | None`
  - Find existing memory similar to new one by cosine.
  - **Location**: [_reconcile.py:123](../../scripts/_reconcile.py#L123)

- `judge_reconcile(new_text: str, old_text: str) → str`
  - Judge whether new memory should ADD, SUPERSEDE, or SKIP against old.
  - **Location**: [_reconcile.py:142](../../scripts/_reconcile.py#L142)

- `may_supersede(new_valid_from: str, old_valid_from: str) → bool`
  - Check if new is valid long enough to supersede old.
  - **Location**: [_reconcile.py:159](../../scripts/_reconcile.py#L159)

- `reconcile(new_body: str, new_valid_from: str, vec, items: list, ...) → str`
  - Orchestrate full reconciliation logic. Returns "add" | "supersede" | "skip".
  - **Location**: [_reconcile.py:168](../../scripts/_reconcile.py#L168)

#### _maintenance.py
**Purpose**: Background maintenance passes: deduplication, supersession, rechecking, clustering.

**Functions**:
- `current_items(get_cached_fn=None, statuses=("current",)) → list`
  - Load all current memories. Caches vectors to avoid re-embedding.
  - **Location**: [_maintenance.py:222](../../scripts/_maintenance.py#L222)

- `neighbour_map(items: list, threshold: float) → dict`
  - Build similarity graph (cosine-based neighbors).
  - **Location**: [_maintenance.py:300](../../scripts/_maintenance.py#L300)

- `exact_duplicate_pass(dry_run: bool = False) → int`
  - Find and mark exact duplicate memories.
  - **Location**: [_maintenance.py:494](../../scripts/_maintenance.py#L494)

- `supersede_pass(threshold: float = SUPERSEDE_THRESHOLD, judge_fn=None, ...) → int`
  - Find near-duplicates and ask judge if new should supersede old.
  - **Location**: [_maintenance.py:581](../../scripts/_maintenance.py#L581)

- `recheck_pass(judge_fn=None, limit: int = 20, items=None) → int`
  - Re-evaluate unverified memories; promote good ones to current.
  - **Location**: [_maintenance.py:626](../../scripts/_maintenance.py#L626)

#### _copilot.py
**Purpose**: GitHub Copilot CLI integration (ADR-0003). Idempotent, non-destructive config mutation.

**Functions**:
- `find_binary() → str | None` — locate copilot binary
- `binary_version(binary: str | None = None, timeout: int = 20) → tuple | None` — get (major, minor, patch)
- `copilot_home() → Path` — get Copilot config home (respects COPILOT_HOME)
- `detect(vault: Path | None = None) → dict` — machine-readable detection snapshot
- `setup(vault: Path, dry_run: bool = False, ...) → dict` — idempotently inject KennisBank config into Copilot
- `status(vault: Path | None = None) → dict` — report current state
- **Location**: [_copilot.py:92-300](../../scripts/_copilot.py#L92)

#### _groundcheck.py
**Purpose**: Fact-checking via semantic search + LLM judgment.

**Functions**:
- `check_fact(fact: str, vault: Path | None = None, ...) → dict`
  - Retrieve relevant context for fact and ask judge if it's grounded.
  - **Location**: [_groundcheck.py:*](../../scripts/_groundcheck.py)

**Purpose**: Scene (context cluster) management.

**Functions**:

#### _progress.py, _transcript.py, _provenance.py
**Purpose**: Supporting modules for progress tracking, transcript handling, and provenance.

---

### CLI Entry Points

#### Retrieval Hooks
These are invoked by the Claude Code harness on UserPromptSubmit (synchronously, must be fast).

- **kb-retrieve.py** (~438 lines)
  - Main hook: embed prompt, search index, inject top hits as additionalContext.
  - Fail-open: any error → no output, exit 0.
  - Cross-model safe: only use cache entries matching active embed_id.
  - **Location**: [kb-retrieve.py](../../scripts/kb-retrieve.py)

- **kb-recall.py** (~462 lines)
  - Memory-specific recall: search over current memories only.
  - Reuses query vector from hook caller.
  - **Location**: [kb-recall.py](../../scripts/kb-recall.py)

#### Session Coordination
- **kb-session-start.py** (~579 lines)
  - Orchestrate startup work: warmup embeds, checkpoint recovery, orientation, activity snapshot.
  - Runs independence jobs concurrently; data dependencies in phases.
  - **Location**: [kb-session-start.py](../../scripts/kb-session-start.py)

- **kb-session-end.py**
  - End-of-session: checkpoint writes, activity finalization.

- **kb-session-log.py** 
  - Write session log summary to vault.

#### Index Builders
- **build-kb-index.py** (~12KB)
  - Full rebuild of vector index from markdown files in vault.
  - Prunes deleted files, re-embeds all current files.
  - **Location**: [build-kb-index.py](../../scripts/build-kb-index.py)

- **build-embed-index.py** (~3KB)
  - Build cache of embeddings (warm-up).
  - **Location**: [build-embed-index.py](../../scripts/build-embed-index.py)

- **build-activity-index.py** (~1.5KB)
  - Rebuild activity log from source files.
  - **Location**: [build-activity-index.py](../../scripts/build-activity-index.py)


- **build-graph-index.py** (~4.6KB)
  - Build knowledge graph (wiki links, cross-references).
  - **Location**: [build-graph-index.py](../../scripts/build-graph-index.py)

- **build-karpathy-index.py** (~834 lines)
  - Build Karpathy papers/research knowledge base.
  - **Location**: [build-karpathy-index.py](../../scripts/build-karpathy-index.py)

#### Maintenance & Sweeps
- **memory-sweep.py** (~648 lines)
  - Autonomous memory lifecycle: extract from transcripts, judge, reconcile, upsert.
  - Runs concurrently with retrieval (read-only over main index).
  - **Location**: [memory-sweep.py](../../scripts/memory-sweep.py)

- **embed-sweep.py** (~366 lines)
  - Refresh embeddings for out-of-date documents (model change, re-embed).
  - **Location**: [embed-sweep.py](../../scripts/embed-sweep.py)

- **kb-state-audit.py** (~336 lines)
  - Check memory state: detect duplicates, orphans, config-like bodies.
  - Reports issues without modifying.
  - **Location**: [kb-state-audit.py](../../scripts/kb-state-audit.py)

- **memory-doctor.py** (~401 lines)
  - Diagnostic and repair tool for memory system.
  - **Location**: [memory-doctor.py](../../scripts/memory-doctor.py)

- **stale-check.py**
  - Identify out-of-date memories (by age, usage).
  - **Location**: [stale-check.py](../../scripts/stale-check.py)

#### Importers
- **import-copilot.py**
  - Import Copilot conversation history.
  - **Location**: [import-copilot.py](../../scripts/import-copilot.py)

- **import-claudeai-export.py** (~365 lines)
  - Import Claude.ai export (JSON).
  - **Location**: [import-claudeai-export.py](../../scripts/import-claudeai-export.py)

- **import-chatgpt-export.py** (~365 lines)
  - Import ChatGPT export.
  - **Location**: [import-chatgpt-export.py](../../scripts/import-chatgpt-export.py)

- **import-cc-history.py** (~343 lines)
  - Import Claude Code session history.
  - **Location**: [import-cc-history.py](../../scripts/import-cc-history.py)

- **import-folder.py**
  - Generic folder import.
  - **Location**: [import-folder.py](../../scripts/import-folder.py)

#### User Queries
- **kb-ask.py**
  - Manual export bridge for cloud agents. Retrieve relevant context, print formatted for pasting.
  - **Location**: [kb-ask.py](../../scripts/kb-ask.py)

- **kb-search.py**
  - Full-text and semantic search over memories.
  - **Location**: [kb-search.py](../../scripts/kb-search.py)

- **kb-verify.py**
  - Ground a fact against the knowledge base.
  - **Location**: [kb-verify.py](../../scripts/kb-verify.py)

- **kb-lint.py** (~321 lines)
  - Lint memory files for format/content issues.
  - **Location**: [kb-lint.py](../../scripts/kb-lint.py)

- **kb-normalize.py**
  - Normalize memory markdown to canonical style.
  - **Location**: [kb-normalize.py](../../scripts/kb-normalize.py)

#### Graph & Relationships
- **graph-link-layer.py**
  - Extract and index wiki links.
  - **Location**: [graph-link-layer.py](../../scripts/graph-link-layer.py)

- **graph-provenance-ring.py**
  - Build provenance chains (who cites whom).
  - **Location**: [graph-provenance-ring.py](../../scripts/graph-provenance-ring.py)

- **graph-scope-prune.py**
  - Prune graph to 02-wiki-only scope (for public/release versions).
  - **Location**: [graph-scope-prune.py](../../scripts/graph-scope-prune.py)

#### Installation & Setup
- **install-agent-envs.py** (~1170 lines)
  - Install KennisBank agent environment (Copilot hooks, MCP server, Claude CLI integration).
  - **Location**: [install-agent-envs.py](../../scripts/install-agent-envs.py)

- **register-hooks.py**
  - Register KennisBank hooks with Claude Code.
  - **Location**: [register-hooks.py](../../scripts/register-hooks.py)

#### Evaluation & Analysis
- **kb-eval.py** (~333 lines)
  - Run retrieval quality evaluation on gold-standard queries.
  - **Location**: [kb-eval.py](../../scripts/kb-eval.py)

- **kb-eval-gen.py**
  - Generate eval queries from transcripts.
  - **Location**: [kb-eval-gen.py](../../scripts/kb-eval-gen.py)

- **judge-model-sweep.py** (~418 lines)
  - Evaluate different judge model configs.
  - **Location**: [judge-model-sweep.py](../../scripts/judge-model-sweep.py)

- **rerank-eval.py**
  - Evaluate ranking factor combinations.
  - **Location**: [rerank-eval.py](../../scripts/rerank-eval.py)

- **recall-ablation.py**
  - Ablation study on recall components.
  - **Location**: [recall-ablation.py](../../scripts/recall-ablation.py)

#### Other Utilities
- **kb-mcp.py** (~442 lines)
  - MCP server for Claude integration (local, stdio).
  - **Location**: [kb-mcp.py](../../scripts/kb-mcp.py)

- **kb-activity.py** / **kb-activity-eval.py**
  - Activity log queries and evaluation.
  - **Location**: [kb-activity.py](../../scripts/kb-activity.py)

- **context-budget.py** (~428 lines)
  - Analyze context window usage and costs.
  - **Location**: [context-budget.py](../../scripts/context-budget.py)

- **find-similar.py** (~5.5KB)
  - Find semantically similar memories.
  - **Location**: [find-similar.py](../../scripts/find-similar.py)

- **memory-notify.py** / **distill-notify.py**
  - Notification systems for memory events.
  - **Location**: [memory-notify.py](../../scripts/memory-notify.py)

- **semantic-tiling.py**
  - Chunk documents by semantic boundaries (for embedding).
  - **Location**: [semantic-tiling.py](../../scripts/semantic-tiling.py)

- **safe-edit.py** (~374 lines)
  - Safely edit memory files (atomic, with backups).
  - **Location**: [safe-edit.py](../../scripts/safe-edit.py)

- **parse-document.py**
  - CLI wrapper for liteparse.
  - **Location**: [parse-document.py](../../scripts/parse-document.py)

---

## Dependencies

### Internal Code Dependencies

**Tier 1 (Foundation)**: Used everywhere
- `_vaultpath` → vault resolution
- `_common` → utilities
- `_settings` → toggles
- `_frontmatter` → markdown parsing

**Tier 2 (Core)**: Used by indexing, retrieval, memory
- `_llm` → generation
- `_embeddings` → vectors
- `_memory` → schema
- `_extract` → candidate extraction
- `_judge` → judgment
- `_llmjson` → JSON parsing

**Tier 3 (Domain)**: Larger modules building on Tier 1-2
- `_activity` → activity indexing (uses _common, _vaultpath, _settings, _memory)
- `_kbindex` → knowledge index (uses _embeddings, _vaultpath, _memory)
- `_usage` → usage tracking (uses _vaultpath)
- `_rank` → ranking (uses _memory, _usage)
- `_reconcile` → reconciliation (uses _memory, _llm)
- `_maintenance` → maintenance (uses all above)
- `_copilot` → Copilot integration (uses _vaultpath, _settings)
- `_groundcheck` → fact-checking (uses _embeddings, _kbindex, _llm)
- `_provenance` → source tracking

**Tier 4 (CLI)**: Entry points using Tier 1-3
- `kb-retrieve.py`, `kb-recall.py` → retrieval (use _embeddings, _kbindex, _usage, _rank)
- `kb-session-start.py` → session coord (uses _embeddings, _memory, _activity)
- `memory-sweep.py` → sweep (uses _extract, _judge, _reconcile, _maintenance)
- `build-*.py` → index builders (use _kbindex, _embeddings, _activity)
- `install-agent-envs.py` → setup (uses _copilot, _settings, _vaultpath)

### External Dependencies

**Minimal Stdlib-Only Modules**:
- `_vaultpath.py`, `_common.py`, `_settings.py`, `_frontmatter.py`, `_llm.py` (use only stdlib)

**SQLite + Extensions**:
- `_activity.py`, `_kbindex.py`, `_usage.py` (sqlite3, sqlite-vec for vector indexing)

**HTTP/LLM Backends**:
- `_llm.py`: ollama, openrouter (HTTP), claude-cli (subprocess)
- `_embeddings.py`: ollama, openai, voyage (HTTP)

**Optional Libraries**:
- `dateparser` — layer 2 of temporal parsing (imported lazily, optional)
- `liteparse` — document parsing framework

**Third-Party Integrations**:
- GitHub Copilot CLI (copilot binary, mcp-config.json)
- Claude Code (hook system, MCP stdio)
- Ollama (local LLM/embedding server)

---

## Relationships

### Data Flow

```
User Input (transcript, query, session)
    ↓
Extract Candidates (_extract.py)
    ↓ [candidate memories]
Judge (_judge.py) → reconcile (_reconcile.py)
    ↓ [scored memories]
Upsert (SQLite) → _memory.py frontmatter
    ↓
Build index (_kbindex.py): hash, embed, store vector + FTS
    ↓ [indexed vector store + graph]
Retrieval hook (kb-retrieve.py): embed query → search → inject
    ↓
Ranking (_rank.py): multi-factor rerank (recency, importance, trust, usage, noise)
    ↓ [top results to LLM]
Usage tracking (_usage.py): log injected → mark used/noise
    ↓ [feedback loop]
```

### Code Diagram: Module Dependencies

```
Tier 1 (Foundation)
├─ _vaultpath.py
├─ _common.py
├─ _settings.py
└─ _frontmatter.py
    ↓ (used by all)

Tier 2 (Pluggable Backends)
├─ _llm.py (generation, uses _vaultpath, _common)
├─ _embeddings.py (vectors, uses _vaultpath, _common, _frontmatter)
├─ _llmjson.py (JSON parsing, stdlib only)
├─ _extract.py (uses _llm, _llmjson)
├─ _judge.py (uses _llm)
└─ _memory.py (schema, uses _common, _frontmatter)

Tier 3 (Domain Logic)
├─ _activity.py (indexing, uses Tier 1-2, _memory)
├─ _kbindex.py (vector index, uses Tier 1-2, sqlite-vec)
├─ _usage.py (tracking, uses Tier 1, sqlite3)
├─ _rank.py (ranking, uses _memory, _usage)
├─ _reconcile.py (reconciliation, uses _memory, _llm)
├─ _maintenance.py (passes, uses all Tier 3)
├─ _copilot.py (integration, uses Tier 1)
├─ _groundcheck.py (fact-checking, uses _embeddings, _kbindex, _llm)
└─ _provenance.py (source tracking)

Tier 4 (CLI/Entry Points)
├─ kb-retrieve.py (uses _embeddings, _kbindex, _usage, _rank)
├─ kb-recall.py (uses _embeddings, _kbindex)
├─ kb-session-start.py (uses _embeddings, _activity, _memory, _usage)
├─ memory-sweep.py (uses _extract, _judge, _reconcile, _maintenance)
├─ build-kb-index.py (uses _kbindex, _embeddings)
├─ build-activity-index.py (uses _activity)
└─ install-agent-envs.py (uses _copilot, _settings, _vaultpath)
```

### Critical Paths (Performance-Sensitive)

1. **Hot Path: Retrieval Hook (2s budget)**
   - kb-retrieve.py → embed(prompt) → _kbindex.search() → rank → inject
   - Dependencies: _embeddings (must be warm), _kbindex (must be current)
   - Fail-open: any error → no output

2. **Off-Path: Memory Sweep**
   - memory-sweep.py → extract → judge → reconcile → _kbindex.upsert()
   - Concurrent with retrieval (read-only to main index)
   - Can be slow; runs in background

3. **Index Build**
   - build-kb-index.py → embed all docs → _kbindex.upsert() → build graph
   - Hours-long, not on critical path
   - Offline operation

---

## Notes

### Design Patterns

1. **Pluggable Backends**: _llm.py, _embeddings.py use config-driven provider chains. First success wins.
2. **Fail-Open Retrieval**: kb-retrieve.py must never block the hot path. Any error → silent, no output.
3. **Atomic Writes**: _settings.py, safe-edit.py use tempfile + os.replace for atomicity.
4. **Memoization**: _embeddings.py caches config reads to avoid repeated stat/parse.
5. **Lazy Imports**: dateparser, liteparse imported on-demand to keep startup fast.
6. **SQLite-Backed State**: _activity.py, _kbindex.py, _usage.py all use local SQLite for resilience.

### Key Tradeoffs

1. **Local vs. Cloud**: _llm.py, _embeddings.py default to local (ollama) but allow opt-in cloud (privacy-first, TASK-4).
2. **Deterministic vs. ML**: _activity.py temporal parsing layers 1-2 are deterministic; layer 3 (LLM) is opt-in fallback.
3. **Speed vs. Accuracy**: _kbindex.search() uses hybrid (cosine + FTS + RRF) for both speed and quality.
4. **Memory vs. CPU**: Model co-location (embedding + judge on one GPU) wins over separate load/unload cycles.

### Known Constraints

1. **Embedding Context**: OLLAMA_NUM_CTX=2048 for embedder (4GB on RTX 3080). Docs >4000 chars fail silently.
2. **Judge Context**: OLLAMA_NUM_CTX=4096 for judge. Reasoning models spend budget on thinking, not answer (measured 30-56s).
3. **Temporal Parsing**: Dateparser library (layer 2) is locale-aware but sometimes over-eager (false positives on version numbers).
4. **Concurrent Writers**: Only sweep and index builds write to kb-index.db; retrieval reads only (prevents lock contention).

### Testing & Evaluation

- `tests/test_*.py` — unit tests (pytest, no external services)
- `kb-eval.py` — gold-standard eval on retrieval quality
- `judge-model-sweep.py` — compare judge models
- `rerank-eval.py` — evaluate ranking factors
- `kb-state-audit.py` — detect memory state anomalies
