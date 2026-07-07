# CONFIGURATION

Reference of every configurable knob in LLmWiki-KennisBank. For each entry: name, default, where to change it, what it affects.

Defaults use `$HOME`, but production installs should set `KENNISBANK_VAULT`
when the vault is not at `~/KennisBank`. `setup.sh` writes that explicit path
into selected agent configs so hooks and MCP servers do not drift back to the
default.

---

## 1. Path configuration

`setup.sh` is the single supported install and upgrade entrypoint. It reads
`KENNISBANK_VAULT` for the vault root and installs selected agent integrations
via `--agents`.

### VAULT

- **Default**: `$HOME/KennisBank`
- **Where set**: `KENNISBANK_VAULT`; fallback is `setup.sh` `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`
- **Read by**:
  - all Python scripts through `scripts/_vaultpath.py` or a self-locating `<vault>/.claude/scripts/` fallback
  - Claude hooks through `~/.claude/settings.json`
  - Codex hooks/MCP through `~/.codex/hooks.json` and `~/.codex/config.toml`
  - OpenCode MCP/plugin through `~/.config/opencode/opencode.json` and `~/.config/opencode/plugins/kennisbank.js`
- **Effect**: root of the knowledge vault. Everything below this path.
- **To change**: rerun setup with `KENNISBANK_VAULT=/new/path bash setup.sh --yes --agents ...`. Do not hand-edit generated agent configs unless you are repairing setup itself.

### RESEARCH

- **Default**: `$HOME/Claude/research`
- **Where set**: `setup.sh`, the `RESEARCH` variable
- **Read by**:
  - `skills/autoresearch/SKILL.md` (output directory, `mkdir -p ~/Claude/research`)
  - `commands/sessielog.md` (Step 2 scans for new research files)
  - `CLAUDE.md.template` (lazy hierarchy Layer 3)
- **Effect**: where `/autoresearch` writes output documents.
- **To change**: edit the `RESEARCH` variable in `setup.sh`, `skills/autoresearch/SKILL.md` (Output section, two references), `commands/sessielog.md` (Step 2), and `CLAUDE.md.template`.

### CLAUDE_COMMANDS

- **Default**: `$HOME/.claude/commands`
- **Where set**: `setup.sh`, the `CLAUDE_COMMANDS` variable
- **Read by**: `setup.sh` only (copy destination). Claude Code itself reads from `$HOME/.claude/commands/` to expose slash commands. This path is not user-configurable in Claude Code.
- **Effect**: where slash command definitions are installed.
- **To change**: only meaningful if Claude Code's command directory ever moves. Not a real knob.

### CLAUDE_SKILLS

- **Default**: `$HOME/.claude/skills`
- **Where set**: `setup.sh`, the `CLAUDE_SKILLS` variable
- **Read by**: `setup.sh` only (copy destination). Claude Code reads from `$HOME/.claude/skills/` to expose skills.
- **Effect**: where the autoresearch skill is installed.
- **To change**: same caveat as `CLAUDE_COMMANDS`. Not a real knob.

### Agent targets (`--agents`)

- **Default**: `claude,codex`
- **Where set**: `setup.sh` `AGENTS` variable or `--agents`
- **Values**: `claude`, `codex`, `opencode`, comma-separated combinations, or `all`
- **Effect**:
  - `claude`: installs `~/.claude/commands`, `~/.claude/skills`, and `~/.claude/settings.json` hooks.
  - `codex`: installs `~/.agents/skills`, `~/.codex/prompts`, `~/.codex/AGENTS.md`, `~/.codex/hooks.json`, and `~/.codex/config.toml` MCP.
  - `opencode`: installs `~/.config/opencode/commands`, `~/.agents/skills`, `~/.config/opencode/AGENTS.md`, `~/.config/opencode/opencode.json` MCP, and `~/.config/opencode/plugins/kennisbank.js`.
- **Validation**: `setup.sh` calls `scripts/install-agent-envs.py --validate` and fails when selected agent config is incomplete.

### Post-install model validation

- **Default**: enabled.
- **Where set**: `setup.sh`; skip explicitly with `--skip-model-check`.
- **Effect**: verifies the embedding model from `<vault>/.claude/kennisbank-embed.json` and the LLM backend from `<vault>/.claude/kennisbank-llm.json`. Ollama backends use local `ollama` smoke calls; OpenRouter backends use a minimal authenticated `chat/completions` smoke call.
- **Failure semantics**: setup exits non-zero. This is intentional: an install is not complete when selected local model backends are unreachable.

---

## 2. CLAUDE.md vault context variables

`<vault>/CLAUDE.md` is generated from `CLAUDE.md.template` and read by the model at session start. Variables are textual conventions, not parsed config. The model reads them and acts accordingly.

### LEARNINGS_FILE

- **Default**: not set. Template suggests `$HOME/Claude/learnings.md` as an example.
- **Where set**: `<vault>/CLAUDE.md`, "Key learnings file" section.
- **Read by**: `commands/sessielog.md` Step 5 (the model checks the file for this variable and uses it if present).
- **Effect**: when set, `/sessielog` appends Do-Not-Repeat entries and technical patterns to that file.
- **To change**: edit the line `LEARNINGS_FILE=...` in your local `CLAUDE.md`. If unset, Step 5 of `/sessielog` is skipped.

### `[YOUR NAME]` placeholder

- **Default**: literal `[YOUR NAME]` (must be replaced after setup).
- **Where set**: `CLAUDE.md.template` line 4, copied to `<vault>/CLAUDE.md`.
- **Read by**: model at session start.
- **Effect**: identifies the vault owner in session context.

### `[YOUR PROJECTS]` placeholder

- **Default**: literal `[YOUR PROJECTS ...]`.
- **Where set**: `CLAUDE.md.template` line 24.
- **Read by**: model at session start.
- **Effect**: lists active projects so the model can route session logs to the right context.

---

## 3. Stale-check threshold

### THRESHOLD_DAYS / `--days`

- **Default**: `60`
- **Where set**: `scripts/stale-check.py` line 75 (`parser.add_argument("--days", type=int, default=60, ...)`).
- **CLI override**: `python3 stale-check.py --days N`
- **Read by**: `commands/stale.md` (which calls the script without `--days`, so always uses default).
- **Effect**: any wiki article whose `updated:` (or `date:`) frontmatter is older than this many days is reported as stale.
- **To change**: edit the `default=60` argument in `stale-check.py`, or pass `--days` on the command line, or edit `commands/stale.md` to pass `--days` explicitly.

---

## 3b. Provenance-lint (`scripts/kb-lint.py`)

### Sessie-herkomst validatie

- **Where set**: `scripts/kb-lint.py` (constanten `SKIP_FILES`, `SESSION_PREFIX`, `HARD_TYPES`).
- **CLI**: `python3 kb-lint.py` (mens-leesbaar), `--json` (voor `doctor.sh`, sectie 13d), `--strict` (fail-closed gate).
- **Read by**: `commands/wiki.md` stap 4.5 (`--strict` als harde stop direct na schrijven) en `scripts/doctor.sh` sectie 13d (FAIL-tier op HARD findings).
- **Effect**: elk artikel in `02-wiki/` (behalve `index.md` en `log.md`) moet minstens één resolvende `[[raw-sessie-...]]`- of `[[05-bronnen/...]]`-wikilink hebben. Finding-types: `missing` (geen enkele verwijzing), `dangling` (dode wikilink) — beide **HARD** (niet-auditeerbaar) — en `path-only` (herkomst alleen als pad-tekst, **advisory**).
- **Exit-contract**: `1` = operationele fout (geen `02-wiki/`; fail-open, geen valse block). Default: `2` bij welke waarschuwing dan ook, `0` schoon. `--strict`: `2` **alleen** bij HARD (missing/dangling); path-only geeft `0` (advisory blokkeert niet). Het JSON-rapport draagt een `hard`-teller die doctor 13d naar FAIL vs WARN mapt.
- **To change**: voeg bestandsnamen toe aan `SKIP_FILES` om structuurbestanden uit te sluiten; verplaats een type tussen HARD en advisory via `HARD_TYPES`; het herkomst-formaat zelf staat in `templates/tpl-wiki-artikel.md` en `commands/wiki.md` stap 4.

---

## 4. Embedding backend, semantic tiling, and retrieval (`scripts/_embeddings.py`)

The embedding backend is a config-driven, swappable provider shared by
`semantic-tiling.py`, the retrieval hook (`kb-retrieve.py`), and the index builder
(`build-embed-index.py`). The model can be a local Ollama model (default) or an
API provider, selected in `.claude/kennisbank-embed.json` (deployed by `setup.sh`
from `kennisbank-embed.example.json`) or via `KB_EMBED_*` env vars. Env vars
override the config file; both override the built-in defaults.

### Provider / model / endpoint / API key (`KB_EMBED_*`)

- **Provider** (`KB_EMBED_PROVIDER`, default `ollama`): `ollama` (local HTTP API,
  `POST /api/embeddings`), `openai` (any OpenAI-compatible `/embeddings`
  endpoint), or `voyage` (Voyage AI). Anthropic/Claude has no native embeddings
  API; Voyage is their recommended path. OpenRouter's embeddings support is
  thin/unconfirmed, so verify a gateway serves `/embeddings` before pointing
  `provider=openai` at it.
- **Model** (`KB_EMBED_MODEL`, default per provider; ollama → `qwen3-embedding:8b`,
  multilingual, 119 languages). For `ollama` the legacy `OLLAMA_EMBED_MODEL` var is
  still honored when `KB_EMBED_MODEL` is unset.
- **Endpoint** (`KB_EMBED_ENDPOINT`): base-URL override (default per provider).
- **API key** (`KB_EMBED_API_KEY_ENV`): the NAME of the env var holding the key;
  the key itself is never stored in the config or the repo.
- **Where set**: `scripts/_embeddings.py` (`_resolve()` / `embed()`).
- **Read by**: `scripts/_embeddings.py`, used by `semantic-tiling.py`,
  `kb-retrieve.py`, and `build-embed-index.py`.
- **To change**: edit `.claude/kennisbank-embed.json` (see its `_switching`
  examples) or set the `KB_EMBED_*` env vars. Run `ollama pull <model>` first for
  local models. For an English-only vault the lighter `nomic-embed-text` works
  (then also set the tiling thresholds to `0.90` / `0.80`, since `nomic` spreads
  higher).
- **Note**: switching model/provider invalidates the embedding cache by design
  (cross-model cosine is silently wrong: different dimensions and vector spaces).
  Cache entries are keyed on `embed_id()` (`provider:model`) plus dimension.

### TILING_THRESHOLD_ERROR (duplicate threshold)

- **Default**: `0.85` (tuned for the default `qwen3-embedding:8b`)
- **Where set**: `scripts/semantic-tiling.py` (`THRESHOLD_ERROR = float(os.environ.get("TILING_THRESHOLD_ERROR", "0.85"))`).
- **Effect**: cosine similarity at or above this is reported as `ERROR -- mogelijke duplicaten`.
- **To change**: set the `TILING_THRESHOLD_ERROR` environment variable. Thresholds are model-specific: the default `qwen3-embedding:8b` spreads lower (0.85 fits), while `nomic-embed-text` spreads high and wants `0.90`. Recalibrate per embedding model if you switch.

### TILING_THRESHOLD_REVIEW (related threshold)

- **Default**: `0.62` (tuned for the default `qwen3-embedding:8b`)
- **Where set**: `scripts/semantic-tiling.py` (`THRESHOLD_REVIEW = float(os.environ.get("TILING_THRESHOLD_REVIEW", "0.62"))`).
- **Effect**: cosine similarity in `[THRESHOLD_REVIEW, THRESHOLD_ERROR)` is reported as `REVIEW -- verwante artikelen`.
- **To change**: set the `TILING_THRESHOLD_REVIEW` environment variable. Same model-specific caveat as above (for `nomic-embed-text` use `0.80`).

### Embedding character cap

- **Default**: `4000` characters.
- **Where set**: `scripts/semantic-tiling.py` line 36 (`return content[:4000]`).
- **Effect**: input text is truncated before embedding. Larger articles compare on their first 4000 characters only.

### CACHE_FILE

- **Default**: `$HOME/KennisBank/.claude/embeddings-cache.json`
- **Where set**: `scripts/_embeddings.py` (`CACHE_FILE`), shared by tiling, retrieval, and the index builder.
- **Effect**: stores embeddings keyed by file path, content hash, `embed_id()` (provider:model), and vector dimension. Switching model/provider transparently invalidates cached vectors (no manual wipe), since entries with a different `embed_id` no longer match. Stale entries (files no longer in `02-wiki/`) are pruned on every run.

### WIKI_DIR

- **Default**: `$HOME/KennisBank/02-wiki`
- **Where set**: `scripts/semantic-tiling.py` line 20.
- **Effect**: the directory scanned recursively (`**/*.md`) for comparison candidates. `index.md` is excluded.

### Retrieval hook (`scripts/kb-retrieve.py`, UserPromptSubmit)

- **Effect**: embeds the user's prompt and injects the top matching wiki articles (above a threshold) as `additionalContext`. Registered as a global `UserPromptSubmit` hook so the wiki is consulted in every session, in any project. Fail-open: any error, or a trivial/short/slash-command prompt, injects nothing.
- **`KB_RETRIEVE_TOP_N`** (config `retrieve_top_n`, default `3`): max articles injected.
- **`KB_RETRIEVE_THRESHOLD`** (config `retrieve_threshold`, default `0.60`): minimum cosine to inject. Model-specific; empirical on `qwen3-embedding:8b`: true match 0.73-0.80, noise <= 0.51. Re-tune after a model switch.
- **`KB_RETRIEVE_TIMEOUT`** (default `20`s): embed-call timeout.

### Index builder (`scripts/build-embed-index.py`, SessionStart)

- **Effect**: warms/refreshes the wiki embedding cache once per session, off the per-prompt path, and warms the local model. Incremental (only changed files or a model switch trigger real embed calls); prunes vanished files; clears the graphify `.needs-rebuild` flag. Registered as a global `SessionStart` hook.

### Geheugen-index (`scripts/build-kb-index.py`, SessionStart)

- **Effect**: bouwt/verfrist `kb-index.db` (de hybride sqlite-vec + FTS5 zoekindex over wiki + memory) eenmaal per sessie, buiten het per-prompt-pad. Incrementeel: alleen gewijzigde bestanden of een model-switch triggert echte embed-aanroepen; verwijderde bestanden worden gepruned. Hergebruikt de JSON embed-cache (`emb.get_cached`) zodat vectoren niet opnieuw berekend worden. Registered as a global `SessionStart` hook naast `build-embed-index.py`. Gegate op `embed_index` (wiki-laag) en `memory_capture` (memory-laag).

### Autonome capture-sweep (`scripts/sweep-launch.py`, SessionStart)

- **Effect**: dun launcher voor de autonome memory-sweep; gegate op `memory_capture`. Neemt een single-flight lockfile (`<vault>/.claude/.sweep.lock`, PID + mtime, stale-reclaim na 1u) zodat nooit twee sweeps gelijktijdig draaien. Spawnt `memory-sweep.py` DETACHED (niet-blokkerend: Windows DETACHED_PROCESS|CREATE_NO_WINDOW, POSIX start_new_session) en daarna `build-kb-index.py` (sweep-voor-index-ordening zodat verse memories meteen in de index landen). Eindigt met exit 0 fail-open. De zware LLM-sweep draait los van SessionStart en houdt de sessiestart onzichtbaar/snel. Draait naast de directe `build-kb-index.py`-hook (die de wiki-laag via `embed_index` bedient onafhankelijk van `memory_capture`; de dubbele run is benign want incrementeel en idempotent).
- **Backfill-cap**: `scripts/memory-sweep.py` ondersteunt `--max-per-transcript N` (default 20) zodat `/kennisbank:rebuild-memory` of een directe `--all`-run een mega-transcript niet onbeperkt facetten laat schrijven. De normale per-sessie sweep blijft op `max_chunks=6`; de cap raakt alleen het aantal geschreven memories per source_session.

### Transcript-archief (`scripts/archive-transcript.py`, SessionEnd)

- **Effect:** kopieert het transcript van elke beëindigde sessie naar
  `$VAULT/01-raw/transcripts/<datum>-<project>-<sid8>.jsonl`. Deterministisch,
  fail-open, idempotent. Overleeft `cleanupPeriodDays` omdat de vault een
  backup-locatie is. Lege/`-p`-transcripts (< 200 bytes) worden overgeslagen.

### Destillatie-melding (`scripts/distill-notify.py`, SessionStart)

- **Effect:** telt transcripts in `01-raw/transcripts/` die niet in de
  `.distilled`-watermark staan en injecteert een melding "N wachten op
  destillatie". Geen LLM. Met `--mark <stem...>` (door `/destilleer`) worden
  exact de verwerkte stems aan de watermark toegevoegd.

### Geheugen-gezondheid-melding (`scripts/memory-notify.py`, SessionStart)

- **Effect:** leest de sweep-heartbeat (`<vault>/.claude/memory-sweep-status.json`)
  en telt unverified memories ouder dan 48u via `memory-doctor.py`. Meldt ALLEEN
  als er iets te rapporteren is: model onbereikbaar, sweep-fouten, of ouderdom.
  Niets mis → geen output (stil). Fail-open.

### Presearch hook (`scripts/kb-presearch.py`, PreToolUse)

- **Effect:** voordat elke `WebSearch` of `WebFetch` wordt uitgevoerd, injecteert
  `kb-presearch.py` relevante geheugen- en wiki-fragmenten (`additionalContext`)
  zodat de agent eerst zijn lokale KennisBank raadpleegt vóór externe zoeking.
  Niet-blokkerend (permissionDecision defer); fail-open op elke fout. Gegate op
  `memory_recall`.

### Hookregistratie (`~/.claude/settings.json`)

De scripts worden door `setup.sh` naar `$VAULT/.claude/scripts/` gedeployed. Voeg
daarna onderstaande entries TOE aan de bestaande `hooks`-arrays in je
`~/.claude/settings.json` (Windows `py -3`-launcher; pas `<VAULT>` aan).

> LET OP: dit is GEEN volledige settings.json. Plak het niet als geheel; dat
> wist je bestaande hooks, env (incl. `KENNISBANK_VAULT`) en permissions. Voeg
> alleen deze entries toe aan de respectieve arrays. De `SessionStart`-array
> bevat al `build-embed-index.py` (en evt. caveman) -- zet `distill-notify.py`
> en `build-kb-index.py` erNAAST, niet eroverheen.

```jsonc
// toe te voegen ENTRIES (geen complete settings.json):
"SessionEnd": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/archive-transcript.py\"" }
  ]}
],
// onder de BESTAANDE SessionStart-array vier extra hook-blokken:
"SessionStart": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/distill-notify.py\"" }
  ]},
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/memory-notify.py\"" }
  ]},
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/build-kb-index.py\"" }
  ]},
  { "matcher": "", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/sweep-launch.py\"" }
  ]}
],
// PreToolUse presearch-hook (geheugen+wiki vóór WebSearch/WebFetch):
"PreToolUse": [
  { "matcher": "WebSearch|WebFetch", "hooks": [
    { "type": "command", "command": "py -3 \"<VAULT>/.claude/scripts/kb-presearch.py\"" }
  ]}
]
```

Op macOS/Linux: vervang `py -3` door `python3`.

---

### Hook registration (`scripts/register-hooks.py`)

`setup.sh` registers the **full hookset** via `register-hooks.py --manifest`, covering:

- **SessionStart**: `build-embed-index.py` (warm wiki embed cache), `distill-notify.py` (note pending transcripts), `build-kb-index.py` (refresh memory index), `sweep-launch.py` (launch memory sweep)
- **SessionEnd**: `archive-transcript.py` (archive transcript to vault)
- **UserPromptSubmit**: `kb-retrieve.py` (inject matching wiki snippets, hybrid cosine|FTS5)
- **PreToolUse** (matcher `WebSearch|WebFetch`): `kb-presearch.py` (inject memory+wiki before external search)

Registration is idempotent and non-destructive: existing hooks, permissions, and env are preserved. Re-running `setup.sh` is safe for new **and existing** vaults — it refreshes the tooling without clobbering user data or overwriting customisations. Interpreter is **interpreter-aware**: uses `py -3` on Windows, `python3` elsewhere; a self-heal on stale paths preserves the original interpreter. Skip registration with `setup.sh --no-hooks`.

**Version stamp.** `setup.sh` creates `<vault>/.claude/.kennisbank-schema-version` (current: `0.9.0`) — de migratie-schema-versie. Dit is een **apart** bestand van `.kennisbank-version` (de release-tag-stamp die de `kennisbank-upgrade`/`kennisbank-contribute`-skills beheren); ze worden bewust niet gedeeld. If a hook is stubbornly missing after re-run, force a re-registration by removing the schema-version stamp and re-running:

```bash
rm ~/KennisBank/.claude/.kennisbank-schema-version
bash ~/KennisBank/setup.sh --yes
```

**Manual registration (reference only).** Normally not needed — `bash setup.sh` does it fully. If you want to register manually or post-hoc:

```
python3 ~/KennisBank/.claude/scripts/register-hooks.py --manifest ~/.claude/settings.json ~/KennisBank
```

For individual hooks, see the JSON blocks below as reference (interpreter shown as `py -3` on Windows; use `python3` on macOS/Linux):

## 4a. LLM backend for the memory judge/extraction (`scripts/_llm.py`)

Separate from the embedding backend (section 4): the memory sweep uses a
generative LLM to extract candidate memories, judge current-vs-quarantine,
reconcile, and supersede. Mirrors the embedding config — config-driven,
pluggable, fail-soft.

### Provider chain / model / endpoint (`KB_LLM_*`)

- **Default**: providers `["ollama"]`, model `gemma4:latest`, endpoint `http://localhost:11434`. `setup.sh` bootstraps this into `<vault>/.claude/kennisbank-llm.json` when absent.
- **Where set** (first match wins): env `KB_LLM_PROVIDERS` (comma list), `KB_LLM_MODEL`, `KB_LLM_ENDPOINT`, `KB_LLM_API_KEY_ENV`; then `<vault>/.claude/kennisbank-llm.json` (`{"providers":[...], "model":"...", "models":{prov:model}, "endpoint":"..."}`), bootstrapped from `kennisbank-llm.example.json`; then the code default above.
- **Provider chain**: `providers` is ORDERED; `generate()` tries each until one returns a non-empty string. `ollama` is local (default). `openrouter` and `claude-cli` are **opt-in** cloud providers: putting them in the chain is explicit consent, and each cloud step logs LOUDLY to stderr, never silently. `claude-cli` shells the existing `claude` binary (uses your Claude Code auth, no key).
- **OpenRouter**: uses OpenRouter's OpenAI-compatible `POST /api/v1/chat/completions` endpoint with `Authorization: Bearer <key>`. Set `"providers": ["openrouter"]`, `"endpoint": "https://openrouter.ai/api/v1"`, `"model": "<provider/model>"`, and `"api_key_env": "OPENROUTER_API_KEY"`. The key is read from that environment variable first, then from user-local `~/.config/kennisbank/secrets.json`. The key is never written to the vault.
- **PIN YOUR MODEL (common gotcha)**: the code default is the tag `gemma4:latest`. If your local Ollama has a differently-tagged model (e.g. `gemma4:12b`), the sweep probe fails and the heartbeat (`<vault>/.claude/memory-sweep-status.json`) reports `model_unreachable: true` even though Ollama is running — capture then silently produces nothing. Check `ollama list` and pin the tag you actually have in `kennisbank-llm.json`.
- **To change**: set the env vars, or edit `<vault>/.claude/kennisbank-llm.json`. `setup.sh` creates the file when missing and preserves existing values unless `--force` is used.
- **Interactive setup**: asks for `ollama` (default) or `openrouter`. For OpenRouter, setup asks for model slug, API-key env-var name, and optionally stores the entered key in `~/.config/kennisbank/secrets.json`.

## 4b. Vault-onderhoud layer env vars

The five env vars below control the behavior of the vault-onderhoud scripts
(`safe-edit.py`, `find-similar.py`, `kb-search.py`, `conflict-scan.py`,
`context-budget.py`) and the `/wiki` command's hybrid-autonomy edit guard.

### KB_EDIT_MAX_LINES

- **Default**: `20`
- **Where set**: `scripts/safe-edit.py`.
- **Effect**: maximum number of lines that `safe-edit.py` may change in a single
  `/wiki` edit pass. Edits that would touch more lines than this are held back and
  proposed to the user for review instead of being applied automatically. Raise for
  larger automated rewrites; lower for stricter human-in-the-loop control.
- **To change**: set the environment variable before running a session, or patch
  the default in `safe-edit.py`.

### KB_EDIT_MAX_DROP

- **Default**: `3`
- **Where set**: `scripts/safe-edit.py`.
- **Effect**: maximum number of non-blank lines that `safe-edit.py` may delete in
  one pass. Deletions beyond this count trigger the same review-hold as
  `KB_EDIT_MAX_LINES`. Protects against silent content loss when `/wiki` rewrites
  an article.
- **To change**: set the environment variable or patch the default in `safe-edit.py`.

### KB_REWRITE_THRESHOLD

- **Default**: `0.62`
- **Where set**: `scripts/find-similar.py`.
- **Effect**: cosine similarity threshold used by `find-similar.py` to decide
  whether the best-matching wiki article is close enough to treat as an existing
  article (rewrite path) rather than a new one. When `above_threshold` is false,
  `/wiki` falls through to creating a new article instead.
  Tuned for `qwen3-embedding:8b`; recalibrate after a model switch.
- **To change**: set the environment variable. Same embedding-model caveat as the
  tiling thresholds.

### KB_CONFLICT_SIM

- **Default**: `0.62`
- **Where set**: `scripts/conflict-scan.py`.
- **Effect**: cosine similarity threshold for `conflict-scan.py` (and by extension
  the `/reconcile` command) to classify two wiki passage pairs as potentially
  contradictory. Pairs above this threshold and with diverging factual claims are
  surfaced; pairs below are skipped. Tuned for `qwen3-embedding:8b`.
- **To change**: set the environment variable. Recalibrate per embedding model.

### KB_CONTEXT_LEVEL

- **Default**: `1`
- **Where set**: `scripts/context-budget.py`.
- **Effect**: selects the progressive context layer loaded at session start
  (via `context-budget.py` and `/sessiestart`).
  - `0` — L0: identity only (first ~40 lines of `CLAUDE.md`).
  - `1` — L1: default (L0 + active state: recent sessions, status counts, open loops).
  - `2` — L2: extended (L0 + L1 + relevant articles via `kb-search.py`, requires `--query`).
  - `3` — L3: full (L0 + L1 + L2 + full article bodies for the matched articles).
  Higher levels consume more tokens; use L0 or L1 for long coding sessions, L3
  for deep knowledge-work sessions.
- **To change**: set the environment variable or pass the level explicitly to
  `context-budget.py`.

### Usage-telemetrie (`scripts/_usage.py`, `scripts/kb-usage-scan.py`)

- **Default**: aan (`usage_telemetry`-toggle in `kennisbank-settings.json`).
- **Where set**: `scripts/_usage.py` (store, `<vault>/.claude/kb-usage.db`); SessionEnd-hook `kb-usage-scan.py` in het hooks-manifest.
- **Effect**: kb-retrieve logt geïnjecteerde stems; de SessionEnd-scan markeert stems die in assistant-tekst/tool-calls voorkwamen als gebruikt. Voedt de gebruiks-boost in `_rank.usage_factor` (×1.10 ≤30d, ×1.05 ≤90d, beide lagen) en de warm-skip in `stale-check.py` (recent gebruikt = niet staal).
- **To change**: toggle uit via `/kennisbank:settings` of `_settings.py set usage_telemetry false`; boost-waarden in `_rank.py`.

### Drempel-kalibratie (`scripts/kb-calibrate.py`)

- **Default set**: `<vault>/06-claude/kb-calibrate-set.json` (voorbeeld in `kb-calibrate-set.example.json`).
- **CLI**: `python3 kb-calibrate.py [--set pad] [--json]`. Exit 0 = schone scheiding, 2 = overlap (set of model scheidt de klassen niet).
- **Effect**: embedt gelabelde paren (duplicate/related/unrelated) met het ACTIEVE model en stelt de duplicate- en related-grens voor, met OK/HERIJK-oordeel per huidige knop (dedup/rewrite/reconcile/conflict/retrieve). Draai na elke modelwissel, vóór je de drempels vertrouwt.
- **To change**: onderhoud de parenset; het harnas schrijft zelf geen drempels (mens beslist).

### Retrieval-scoring en graafbuur (`scripts/_rank.py`, `kb-recall.py`)

- **Defaults**: halfwaardetijden `HALF_LIFE_DAYS` (voorkeur 180, feit/procedure 365, beslissing 730 dagen), `RECENCY_FLOOR 0.6`, importance-factor 0.9-1.1 (neutraal 3 = ×1.0).
- **Where set**: `scripts/_rank.py` (module-constanten).
- **Effect**: memory-hits worden herwogen op relevance × recency × importance; wiki blijft ongewogen. De één-hop graafbuur-expansie voegt de meest-verwezen wikilink-buur van de wiki-hits toe als extra `(buur)`-entry in de hook-injectie.
- **Uitzetten expansie**: env `KB_RETRIEVE_EXPAND=0` of `"retrieve_expand": 0` in `kennisbank-settings.json`.
- **To change**: pas de constanten aan en hermeet met `kb-eval.py` (voor en na; een daling is een regressie).

### Recall-eval (`scripts/kb-eval.py`)

- **Default sets**: `<vault>/06-claude/kb-eval-set.json` (wiki) + `<vault>/06-claude/kb-memory-eval-set.json` (geheugen); voorbeelden in `kb-eval-set.example.json` en `kb-memory-eval-set.example.json`.
- **CLI**: `python3 kb-eval.py [--set pad] [--layer wiki|memory] [--json] [--verbose]`. Zonder `--set` draait het beide sets in één run.
- **Fidelity (belangrijk)**: het harnas meet PER LAAG, niet gefuseerd — de wiki-set wiki-only, de geheugen-set memory-only. Dat spiegelt de hook, die wiki en geheugen als twee gescheiden blokken injecteert (`_wiki_block` / `_memory_block`) en nooit fuseert. Een gefuseerde meting geeft vals signaal (memories verdringen wiki-artikelen in één ranked lijst terwijl ze in productie in aparte blokken staan).
- **Effect**: meet recall@1/3/5 en MRR per laag tegen vragen met verwachte documenten. Draai voor en na elke wijziging aan drempels, embeddingmodel of ranking; een daling is een regressie.
- **To change**: onderhoud beide eval-sets in de vault (voeg vragen toe bij nieuwe kennisdomeinen); de metriek-k's staan als `KS` in het script.

### RECONCILE_THRESHOLD / TOP_K (write-time invalidatie)

- **Default**: `0.75` / `2`
- **Where set**: `scripts/_reconcile.py` (module-constanten).
- **Effect**: bij het wegschrijven van een nieuw kandidaat-memory worden de
  top-`TOP_K` bestaande memories (status current of unverified) met cosine
  boven `RECONCILE_THRESHOLD` aan de reconcile-judge voorgelegd
  (ADD/SUPERSEDE/NOOP). De band loopt tot de dup-drempel (`0.92` in
  `_sweeputil.is_duplicate`): daarboven wordt een kandidaat als exacte
  her-capture geskipt zonder LLM-call (idempotentie van `--all`-rebuilds).
  Tegenspraken die boven 0.92 embedden vangt de supersede-pass (0.85,
  current-only) als vangnet. Tuned voor `qwen3-embedding:8b`.
- **Bi-temporeel**: `valid_from` = sessiedatum uit de transcriptnaam (fallback:
  capture-datum); superseden/expiren stempelt `valid_until`. Zie het
  frontmatter-contract in `scripts/_memory.py`.
- **To change**: pas de constanten in `_reconcile.py` aan. Herkalibreer per
  embeddingmodel, samen met de dup- en supersede-drempels.

---

## 5. autoresearch skill

### Output path

- **Default**: `$HOME/Claude/research/YYYY-MM-DD-[slug].md`
- **Where set**: `skills/autoresearch/SKILL.md`, "Output aanmaken" section (two references: the `mkdir` line and the "Outputpad" line). Also referenced in the "Rapport aan gebruiker" section.
- **To change**: edit `skills/autoresearch/SKILL.md` in all three places, plus `setup.sh` `RESEARCH`, plus `commands/sessielog.md` Step 2, plus `CLAUDE.md.template` Layer 3.

### Round count

- **Default**: maximum `3` rounds.
- **Where set**: `skills/autoresearch/SKILL.md`, "Research-loop" section (`Maximaal 3 rounds`) and "Constraints" section.
- **Effect**: Round 1 is broad, Round 2 is gap-filling, Round 3 is optional synthesis. The model stops earlier if confidence is high.
- **To change**: edit both the loop description and the constraint line in `SKILL.md`.

### Source cap

- **Default**: maximum `15` sources.
- **Where set**: `skills/autoresearch/SKILL.md`, "Constraints" section.
- **Effect**: model halts web fetching at this count.

### Confidence labels

- **Default**: `hoog | matig | laag` (Dutch).
- **Where set**: `skills/autoresearch/SKILL.md`, frontmatter section.
- **To change**: edit the frontmatter template and the explanatory paragraph that follows.

### Trigger phrases

- **Default**: `/autoresearch [topic]`, `"research [topic]"`, `"deep dive [topic]"`, `"onderzoek [topic]"`.
- **Where set**: `skills/autoresearch/SKILL.md` frontmatter `description` field.
- **Effect**: Claude Code matches user input against these to decide when to load the skill.

---

## 6. Slash command language

### Command prose language

- **Default**: Dutch (all six commands and the autoresearch skill are written in Dutch).
- **Where set**:
  - `commands/intake.md`
  - `commands/sessielog.md`
  - `commands/stale.md`
  - `commands/wiki.md`
  - `commands/sessiestart.md`
  - `commands/import.md`
  - `skills/autoresearch/SKILL.md`
- **Effect**: section headings, instructions to the model, and report templates are Dutch. The CLAUDE.md template comments that "commands follow prompt language" -- meaning the model adapts user-facing output, but the instruction text itself stays Dutch unless edited.
- **To change**: rewrite the six `commands/*.md` files and `skills/autoresearch/SKILL.md` in the target language. Filenames (`raw-sessie-...`) and slug conventions referenced in code do not need translating.

### Session log filename pattern

- **Default**: `raw-sessie-YYYY-MM-DD-[onderwerp-slug].md`
- **Where set**: `commands/sessielog.md` Step 1.
- **Read by**: `scripts/stale-check.py` line 16 (`SESSIE_DATE_RE = re.compile(r"raw-sessie-(\d{4}-\d{2}-\d{2})")`).
- **Effect**: stale-check parses dates from this prefix to find session logs newer than a wiki article. If you change the prefix in `sessielog.md`, also update `SESSIE_DATE_RE`.

---

## 7. Memory path detection

### Pattern

- **Default**: `$HOME/.claude/projects/*/memory/MEMORY.md` (first match wins).
- **Where set**:
  - `CLAUDE.md.template` lines 33-34 and 44-47 (Layer 1 lazy hierarchy)
  - `skills/autoresearch/SKILL.md` Step 0, Layer 1
  - `README.md` "Memory path" section
- **Read by**: model at session start, and at the start of `/autoresearch`.
- **Effect**: locates Claude Code's per-project memory file. The path segment between `projects/` and `/memory/` is a slug of the working directory at the time the memory was first written.
- **Why session-dependent**: Claude Code creates one `MEMORY.md` per project working directory. If a session has never run from this project's directory, no memory file exists and the lazy check returns nothing. The glob picks the first match alphabetically, so multiple project memories produce nondeterministic selection.
- **To change**: not configurable in this repo. Replace the bash one-liner in `CLAUDE.md.template` and `SKILL.md` if you maintain memory differently.

---

## 8. graphify integration

### Graph input path

- **Default**: `$HOME/KennisBank/graphify-out/graph.json`
- **Where set**: `scripts/auto-crosslink.py` line 20 (`GRAPH_PATH = VAULT_ROOT / "graphify-out" / "graph.json"`).
- **Read by**: `scripts/auto-crosslink.py` only.
- **Effect**: source of edges for backlink suggestions. If the file is absent, `auto-crosslink.py` exits 0 silently with `graph.json niet gevonden ... crosslink overgeslagen`.
- **To change**: edit the constant in `auto-crosslink.py`. Also adjust where the graphify skill writes output if you point it elsewhere.

### Rebuild flag path

- **Default**: `$HOME/KennisBank/graphify-out/.needs-rebuild`
- **Where set**: `commands/sessielog.md` Step 3.
- **Read by**: external graphify skill (when run, it should consume and clear this flag).
- **Effect**: signals that wiki content changed and the graph is out of date. The flag is written as plain text containing changed file paths.
- **To change**: edit Step 3 of `commands/sessielog.md`.

### MIN_CONFIDENCE

- **Default**: `0.75`
- **Where set**: `scripts/auto-crosslink.py` line 22.
- **Effect**: graph edges below this `confidence_score` are ignored when proposing backlinks.
- **To change**: edit the constant.

### MAX_NEW_LINKS

- **Default**: `5`
- **Where set**: `scripts/auto-crosslink.py` line 23.
- **Effect**: per article, at most this many new `Zie ook` bullets are appended in one run.

### WIKI_DIR_PREFIX

- **Default**: `02-wiki/`
- **Where set**: `scripts/auto-crosslink.py` line 21.
- **Effect**: only nodes whose `source_file` starts with this prefix are considered crosslink targets. Change if you rename the wiki directory.

---

## 9. Customizing for non-default vault paths

### The `KENNISBANK_VAULT` environment variable (scripts)

The Python scripts and `doctor.sh` resolve the vault root the same way:

1. `$KENNISBANK_VAULT`, if set and non-empty (`~` and `$VARS` are expanded);
2. otherwise the default `$HOME/KennisBank`.

So pointing the whole script layer at another vault is one variable, not a
source edit:

```bash
export KENNISBANK_VAULT=/path/to/your/KennisBank
bash scripts/doctor.sh
python3 scripts/stale-check.py
```

This is honored by `scripts/stale-check.py`, `scripts/semantic-tiling.py`,
`scripts/auto-crosslink.py`, `scripts/intake-scan.py` and `scripts/doctor.sh`
(shared helper: `scripts/_vaultpath.py`). The importers keep their own
`--vault` flag. `build-karpathy-index.py` keeps its `--vault-root` flag.

`setup.sh` scaffolds the vault at `KENNISBANK_VAULT` when that variable is set.
It also writes the chosen path into Claude, Codex, and OpenCode integration
files. For non-default paths, rerun setup instead of hand-editing prompt files:

```bash
KENNISBANK_VAULT=/path/to/your/Kluis bash setup.sh --yes --agents all
```

### Runtime prompt files

Commands and skills are prompt files executed by the agent. They should resolve
the vault from `KENNISBANK_VAULT` or from the installed agent instructions. A
literal `~/KennisBank/.claude/scripts/...` call in a command is a regression.
The test suite includes a guard for hardcoded script paths in `commands/*.md`.

### Recommended approach

Set `KENNISBANK_VAULT` and rerun `setup.sh`. Avoid symlink-based installs unless
you are repairing a legacy deployment.

---

## 10. Multiple vaults / per-project context

### What works

- One vault per user account works. Scripts and generated agent configs honor `$KENNISBANK_VAULT` (default `$HOME/KennisBank`).
- Per-project subdivision inside the vault works via `03-projecten/` subdirectories. Wiki articles can tag a project in frontmatter; `commands/wiki.md` accepts an `$ARGUMENTS` topic filter, but it filters by content match, not by project boundary.

### What does not work

- **Multiple parallel active vaults are not supported.** The Python scripts, generated hooks, and MCP configs resolve one active vault root via `$KENNISBANK_VAULT` or the path stamped by setup. Switching active vaults means rerunning setup for the new path.
- **Per-project vault overrides** are not auto-detected. `$KENNISBANK_VAULT` is a single global value; the importers also take `--vault` and `build-karpathy-index.py` takes `--vault-root`, but there is no per-project auto-detection from session context.
- **Concurrent vaults** would collide on the embeddings cache (`<vault>/.claude/embeddings-cache.json`) and on `MEMORY.md` glob ambiguity (section 7).

### Workarounds for multi-vault use

| Approach | Trade-off |
|----------|-----------|
| `export KENNISBANK_VAULT=/path/to/vault` per shell/session before running scripts | Covers the Python scripts and `doctor.sh`, not the slash-command prompt bodies. |
| Symlink `$HOME/KennisBank` to the active vault, swap before each session | Manual, error-prone. No active-vault indicator. |
| Maintain separate clones of this repo with `setup.sh` pointing to different `VAULT` values, and run `setup.sh` per project | Heavy. Each setup overwrites `$HOME/.claude/commands/` for all projects. |
| Single vault, internal sectioning via `03-projecten/<project-name>/` and frontmatter tags | Recommended. The system was designed for this. |

---

## 11. Achtergrond-automatiek (settings-toggles)

De achtergrond-automatieken zijn individueel aan/uit te zetten via
`$VAULT/kennisbank-settings.json` (bron van waarheid, gelezen door
`scripts/_settings.py`).

| toggle | default | effect aan | effect uit |
|--------|---------|-----------|-----------|
| `auto_archive` | uit | SessionEnd archiveert het transcript naar `01-raw/transcripts/` | geen archief; gebruik `/sessielog` handmatig |
| `distill_notify` | aan | SessionStart meldt openstaande transcripts | geen melding; `/destilleer` blijft handmatig werken |
| `embed_index` | aan | SessionStart ververst de wiki-embeddingcache | retrieval draait op de bestaande (oudere) cache |
| `daily_graphify` | aan | 1x/dag automatisch `/graphify --update` (kost-gated op 20u) | alleen `.needs-rebuild` bijhouden; graph handmatig |
| `memory_capture` | aan | extractie + judge van memories naar `09-memory/` + onderhoud | geen automatische memory-extractie; `/wiki` blijft werken |
| `memory_recall` | aan | injecteer relevante memories in de context via hook + lokale MCP | geen memory-injectie; context bevat alleen wiki-retrieval |
| `usage_telemetry` | aan | registreer geinjecteerde + gebruikte kennis in `kb-usage.db` (ranking-boost, stale-warm-skip) | geen gebruiksmeting; ranking en stale-check vallen terug op leeftijd |

- **Wijzigen**: draai `/kennisbank:settings` (toont een tabel en zet toggles aan/uit), of bewerk het JSON-bestand (waarden zijn JSON-booleans).
- **Self-gating**: de hooks blijven statisch geregistreerd in `~/.claude/settings.json`; elk hookscript leest zijn toggle en eindigt fail-open (`exit 0`) als hij uit staat. Een toggle-wijziging werkt vanaf de volgende sessie.
- **Defaults bij ontbreken**: ontbreekt het bestand of een key, dan geldt de default-kolom hierboven. `setup` en `upgrade` schrijven expliciete waarden.
- **Interactie**: met `embed_index` uit wordt `graphify-out/.needs-rebuild` niet bij SessionStart geleegd; dat is benign, de flag wordt door de graphify-rebuild zelf geleegd.

---

## 12. Lokale MCP-server (kb-mcp.py)

`kb-mcp.py` exposeert je KennisBank (geheugen + wiki) als `recall`-tool aan lokale
MCP-clients (Cursor, LM Studio, Claude Desktop) via **stdio** — lokaal, geen netwerk.
Voor Codex/OpenCode is dit geen losse handmatige stap meer: `setup.sh --agents
codex` of `setup.sh --agents opencode` installeert `mcp==1.28.1` in dezelfde
Python-interpreter als de gegenereerde MCP-config en valideert daarna een echte
MCP initialize/list-tools handshake. `doctor.sh` faalt voortaan als Codex of
OpenCode KennisBank MCP geconfigureerd heeft maar de Python MCP runtime mist.

Handmatige MCP-registratie vereist nog steeds dat je dezelfde interpreter
vooraf voorziet van de SDK:

```
python3 -m pip install mcp==1.28.1
```

Registreer daarna bij je MCP-client met commando:

```
python3 "$HOME/KennisBank/.claude/scripts/kb-mcp.py"
```

(Windows: eerst `py -3 -m pip install mcp==1.28.1`, daarna
`py -3 "%USERPROFILE%/KennisBank/.claude/scripts/kb-mcp.py"`.)
De server opent `kb-index.db` read-only; embedt query's lokaal via Ollama. Zonder
het `mcp`-pakket meldt het script netjes dat de dep ontbreekt; hook-recall en
sweep blijven fail-open, maar een geconfigureerde MCP-agent geldt dan als
onvolledig geinstalleerd.

---

## Discrepancies found

1. **`THRESHOLD_DAYS` constant does not exist.** `README.md` (line 126) and the original task description reference editing `THRESHOLD_DAYS` in `stale-check.py`. The actual code uses `argparse` with `default=60`. The `--days N` CLI flag is correct.
2. **`README.md` stale description is partial.** It says `/stale` "detects articles older than 60 days with newer session data." The script also reports stale articles WITHOUT newer session logs (in a separate `stale_without_sessies` group). Both groups are output.
3. **`auto-crosslink.py` knobs are undocumented in README.** `MIN_CONFIDENCE = 0.75` and `MAX_NEW_LINKS = 5` are real knobs not mentioned anywhere in `README.md` or `CLAUDE.md.template`.
4. **`LEARNINGS_FILE` is text-only convention, not parsed config.** The variable is read by the model from `CLAUDE.md`, not by any script. This works because the model is the executor of `commands/sessielog.md` Step 5; mentioning it as a "configuration variable" can mislead readers into expecting code parsing.
5. **`embeddings-cache.json` location not in README.** The cache lives at `$HOME/KennisBank/.claude/embeddings-cache.json` but is undocumented outside the script source.
6. **graphify rebuild flag is written by a command, not by `setup.sh`.** `setup.sh` creates `graphify-out/` but the `.needs-rebuild` flag is written by `commands/sessielog.md` Step 3. README implies graphify is fully external; the rebuild signal is actually produced inside this repo.
