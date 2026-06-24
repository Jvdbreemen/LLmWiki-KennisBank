# Changelog

All notable changes to LLmWiki-KennisBank are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **CC transcript-archief (`scripts/archive-transcript.py`, SessionEnd-hook).** Archiveert elk transcript naar `01-raw/transcripts/`, fail-open en idempotent. Overleeft `cleanupPeriodDays`.
- **`/destilleer`-commando + `scripts/distill-notify.py` (SessionStart).** Piggyback-destillatie: melding van openstaande transcripts plus een commando dat ze via `import-cc-history.py --source` naar `/wiki` ketent. Watermark in `.distilled`.
- **`import-cc-history.py --source <dir>`.** Importeert een platte transcript-archiefmap.

## [0.7.0] - 2026-06-21

Swappable embedding backend and push-based wiki retrieval, plus cost-gated
graph upkeep and two contribute-skill safeguards.

### Added

- **Swappable embedding provider (`scripts/_embeddings.py`).** Config-driven
  backend (`ollama` | `openai` | `voyage`) behind a single `embed()` interface,
  so the embedding model is a one-file choice instead of a code change. Cross-
  model-safe cache keying via `embed_id()` (provider:model) plus dimension; a
  model switch invalidates the cache by design. Length-guarded `cosine()`,
  shared cache. Config via `kennisbank-embed.json` or `KB_EMBED_*` env; API key
  referenced by env-var NAME only, never stored.
- **Prompt-time wiki retrieval hook (`scripts/kb-retrieve.py`).** UserPromptSubmit
  hook embeds the prompt once and injects the top-N matching wiki articles above
  a threshold as `additionalContext` — push, not pull. Fail-open always: any
  error, missing backend, empty cache, or trivial prompt yields no output and
  exit 0. Cheap pre-filter skips short/slash/trivial prompts before the embed.
  Tuned threshold 0.60 for `qwen3-embedding:8b` (real match 0.73-0.80,
  noise <= 0.51).
- **Embedding index builder (`scripts/build-embed-index.py`).** SessionStart
  hook that warms/refreshes the wiki embedding cache off the per-prompt path.
  Self-locating, incremental, prunes vanished files.
- **`kennisbank-embed.example.json`** — sanitized default (ollama/qwen3, empty
  `api_key_env`), deployed by `setup.sh` (skips if a live config is present
  unless `--force`).

### Changed

- **`scripts/semantic-tiling.py` refactored onto `_embeddings`** — shares the
  cache and keeps the same thresholds/behaviour.
- **`/sessielog` wires incremental `/graphify --update` into Step 2** (before
  auto-crosslink), so new article nodes exist when crosslinks are added — fixes
  the stale-graph "geen nodes gevonden in graph.json" miss.
- **`/sessielog` daily-batch graph gate (cost control).** `--update` runs only
  on the first session where `graph.json` is >20h old; every session still
  appends changed paths to `.needs-rebuild` for free. auto-crosslink runs only
  when `--update` ran. Self-pacing off `graph.json` mtime, no cron.
- **`CONFIGURATION.md`** section 4 rewritten for the `_embeddings.py` backend
  (`KB_EMBED_*`), the retrieval hook, and the index builder (`KB_RETRIEVE_*`).
- **`tests/test_setup_deploy.py`** asserts the new scripts and config deploy.

### Fixed

- **`kennisbank-contribute`: branch-first gotcha.** Documents the failure mode
  where contribute edits committed to local `$DEFAULT` make a branch-off-DEFAULT
  PR show no diff and leave `$DEFAULT` ahead of origin with PR-bound commits a
  stray push would leak — plus the recovery (branch at HEAD, reset `$DEFAULT`
  to origin) and the rule.
- **`kennisbank-contribute`: localization auto-skip.** The scan now normalizes
  deploy-localized path/vault-name rewrites back to portable form and re-diffs;
  pure-localization files (symmetric `+N -N` diffstat) are skipped, so a
  contribute run over a long-deployed vault no longer surfaces every path-
  localized file as a candidate (which "default: all" would ship as a broken,
  path-leaking PR).

## [0.6.1] - 2026-06-20

Tooling self-update: the lifecycle skills now manage every skill, not just
autoresearch. Plus a test-coverage tightening.

### Changed

- **Skills deploy map generalized to `skills/*/`.** `kennisbank-upgrade` now
  refreshes every installed skill (including `kennisbank-upgrade` and
  `kennisbank-contribute` themselves), backing up each skill it overwrites;
  `kennisbank-contribute` can isolate and PR improvements to any repo-known
  skill. Personal/local-only skills (no `skills/<name>/` counterpart in the
  repo at BASE) are gated out via `git cat-file -e` and are never contributed.
- `tests/test_setup_deploy.py` also asserts `autoresearch` is installed, making
  the deploy test a complete guard for all three skills.

## [0.6.0] - 2026-06-20

Multilingual embedding default, configurable tiling thresholds, a deploy-gap
fix, and two new lifecycle skills for upgrading a vault and contributing
improvements upstream.

### Added

- **`kennisbank-upgrade` skill** — upgrades a deployed vault to the latest
  official release tag: checks the upstream tag, shows the changelog, guards
  against clobbering local edits, backs up the current deploy, copies the new
  tooling, stamps `$VAULT/.claude/.kennisbank-version`, and verifies with
  `doctor.sh`.
- **`kennisbank-contribute` skill** — isolates local tooling edits in a
  deployed vault (scripts, templates, commands, skill), filters out personal
  vault content, and opens an upstream PR.
- **`qwen3-embedding:8b` as the default embedding model** (multilingual, 119
  languages) with `nomic-embed-text` as the lighter English-only fallback via
  `OLLAMA_EMBED_MODEL`.
- **Configurable tiling thresholds** `TILING_THRESHOLD_ERROR` /
  `TILING_THRESHOLD_REVIEW`, with robust NL-decimal parsing and a safe fallback
  instead of a crash on bad input.

### Fixed

- **`setup.sh` now deploys `scripts/*.sh`**, so `doctor.sh` ships with every
  install instead of relying on a manual copy.
- **`doctor.sh` respects `OLLAMA_EMBED_MODEL`** and reports the actual default
  (`qwen3-embedding:8b`) instead of hardcoding `nomic-embed-text`.

## [0.5.0] - 2026-06-14

Second review round: regression tests + CI, configurable taxonomy, an env var that points every script at the vault, a documentation-drift sweep, and a code-duplication cleanup.

### Added

- **Test suite (stdlib `unittest`, no third-party dependency).** `tests/` covers `split_frontmatter`/`parse_frontmatter` (`test_frontmatter.py`), `slugify` (`test_slugify.py`), `categorize` (`test_categorize.py`), the `categories.json` loader (`test_categories_json.py`), the zip-slip/symlink guard (`test_zip_guard.py`), `_vaultpath` resolution (`test_vaultpath.py`) and the shared `_common.py` helpers (`test_common.py`). Hyphenated scripts are loaded via `tests/_loader.py`. Run with `python3 -m unittest discover -s tests`.
- **GitHub Actions CI** (`.github/workflows/ci.yml`): on every push and pull request it compiles all scripts (`python3 -m py_compile scripts/*.py`), syntax-checks the shell (`bash -n setup.sh scripts/doctor.sh`) and runs the unittest suite. Free for public repos, pure standard library, no install step.
- **Configurable taxonomy for `build-karpathy-index.py`.** The category rules, prefix hints, generic-tag set and "Overig/Other" labels load from a `categories.json` placed next to the script or in the vault root; the built-in set is the fallback. `categories.example.json` ships the current set as a documented template so an outsider can define their own categories without editing the Python.
- **`KENNISBANK_VAULT` environment variable** via the new `scripts/_vaultpath.py` (single `vault_root()` source of truth). `stale-check.py`, `semantic-tiling.py`, `intake-scan.py` and `doctor.sh` now resolve the vault through it instead of hardcoding `~/KennisBank`, with the same default. Point the whole script layer at another vault with one variable, e.g. `KENNISBANK_VAULT=/tmp/test python3 scripts/stale-check.py`. The `--dry-run` flag was added to `auto-crosslink.py`, the last writing script that lacked an escape hatch.
- `scripts/_common.py`: shared `slugify`, `_utcnow_iso`, `_today_iso` and `print_summary` helpers for the three importers.

### Changed

- **`build-karpathy-index.py` now uses the shared `_frontmatter.py` parser** instead of its own private frontmatter parser (and the optional PyYAML path). One parser, one regex (`_frontmatter.py`'s anchored `^---\s*$`), consistent with the rest of the script layer. Index and log output are unchanged. `categorize()` is untouched.
- **De-duplicated the three importers.** `slugify`, `_utcnow_iso`/`_today_iso` and the summary/dry-run print block were defined identically in `import-folder.py`, `import-claudeai-export.py` and `import-cc-history.py`; they now import from `scripts/_common.py`. Now-unused imports (`json`, `timezone`) were dropped where the dedup left them dangling. Behaviour is identical.

### Fixed

- **Documentation-drift sweep** of the six points found in the review: `AGENTS.md` "every check line ends in OK" corrected to the `[PASS]`/`[FAIL]` format, "four new slash commands" corrected to six, the stale `THRESHOLD_DAYS` reference replaced by the actual `--days` flag; `TROUBLESHOOTING.md` dropped the removed `ollama embed` CLI path in favour of the HTTP API; `POST-INSTALL.md` "four Python utility scripts" corrected to nine; `CONFIGURATION.md` replaced the brittle `setup.sh` line-number references with variable names.
- `scripts/semantic-tiling.py`: removed the unused `import subprocess` (leftover from the CLI era) and now skips the auto-generated `log.md` (in addition to `index.md`) so generated index content is no longer fed into the near-duplicate embeddings.
- `scripts/stale-check.py`: dropped the dead second date format (`%Y-%m-%dT%H:%M:%S`, unreachable because the value is sliced to `[:10]`) and the no-op `fmt[:len(fmt)]`.

## [0.4.0] - 2026-05-14

Release after a full multi-agent code review of v0.3.0. Two CRITICAL fixes (broken `semantic-tiling.py` and a silent `doctor.sh` false-green), four HIGH fixes (`setup.sh` hardening, importer security, frontmatter parser correctness), plus a quick-wins bundle.

### Added

- `setup.sh --force` (`-f`) flag. Default behavior is now no-clobber: existing scripts, templates, commands, skill files and `CLAUDE.md` are kept and reported (`behouden:`). With `--force` they are overwritten (`gekopieerd:`), with a loud warning when an existing customised `CLAUDE.md` is replaced.
- `scripts/_frontmatter.py`: shared helper with `split_frontmatter` and `parse_frontmatter`, used by `import-folder.py`, `stale-check.py` and `semantic-tiling.py`. Anchored multiline regex avoids the previous horizontal-rule false positive.
- `commands/sessielog.md` Stap 1 now invokes `scripts/build-karpathy-index.py` so the Karpathy index in `02-wiki/log.md` is rebuilt after every sessie-log. Previously the script was installed by `setup.sh` but never called by any command.
- README now documents the four `/import` variants (`cc`, `claudeai <path>`, `folder <path>`, `cowork`) inline in the commands table.

### Changed

- `setup.sh` runs from any working directory via `SCRIPT_DIR` detection (was: required CWD to be the repo root).
- `setup.sh` enables `shopt -s nullglob` so empty source globs no longer fail under `set -e`.
- Importer filenames in `import-cc-history.py` and `import-claudeai-export.py` now include an 8-character stable-id suffix (derived from `session_id`/`uuid`, with `sha1` fallback). Same-day same-title sessions no longer overwrite each other silently. **Migration note**: re-running an import after upgrade produces new filenames; old files from earlier runs remain in `01-raw/sessies/` and may need manual cleanup or a one-time rename.
- `commands/import.md` removed a dead reference to a non-existent `/sessielog --force` flag.
- `templates/tpl-wiki-artikel.md` default status is now `concept` (was `actief`), matching the "bij twijfel: status concept" rule in `commands/wiki.md`.
- `scripts/build-karpathy-index.py` emits `## [YYYY-MM-DD] OPERATION | Title` (was `SESSION`), aligning the script with README, `POST-INSTALL.md`, `CHANGELOG.md` and the module docstring.

### Fixed

- **CRITICAL** `scripts/doctor.sh` now verifies all six installed commands (`sessielog`, `wiki`, `intake`, `stale`, `sessiestart`, `import`). Previous versions checked only four and silently reported PASS when `sessiestart` or `import` failed to install. Doctor's PASS count grows from 32 to 34.
- **CRITICAL** `scripts/semantic-tiling.py` uses the Ollama HTTP API (`POST http://localhost:11434/api/embeddings`) instead of the removed `ollama embed` CLI subcommand. The previous implementation always returned `None` on current Ollama releases, producing zero near-duplicate matches without any error.
- **HIGH** `scripts/import-claudeai-export.py` validates every zip member before `extractall`. Absolute paths, `..` traversals and symlink-typed entries (`S_IFLNK`) are rejected; a malicious zip yields a clean `[error]` line on stderr with exit code 2 instead of a Python traceback.
- **HIGH** Frontmatter parsers in three scripts no longer truncate body content at a `---` horizontal rule. Anchored regex `^---\s*$` (multiline) replaces the previous `text.find("\n---", 3)` pattern.
- **HIGH** `scripts/intake-scan.py` boolean was `or` where `and` was intended in `detect_type`. Binary files (`.exe`, `.zip`, etc.) no longer fall through to `read_text` attempts.
- `AGENTS.md`, `POST-INSTALL.md`, `CONFIGURATION.md` docs-sync: "four global slash commands" updated to "six"; obsolete "once `--yes` is merged" qualifier dropped (already merged in 0.2.0); a stale `THRESHOLD_DAYS` discrepancy callout removed from `CONFIGURATION.md`.
- `POST-INSTALL.md` em dashes converted to hyphens (project style: no em dashes).
- `.gitignore` covers `graphify-out/`, `.venv/`, `.idea/`, `.vscode/`, `*.egg-info/`.

### Background

This release packages ten commits from a single review-and-fix pass driven by a multi-agent code review pipeline. The doctor false-green and the broken `semantic-tiling.py` are the two findings users were most likely to hit silently on a fresh install. The importer security fix protects against malicious zip exports (low real-world risk for trusted exports, but the script accepts arbitrary `--input`). The frontmatter parser unification eliminates a class of silent body-truncation bugs that would only show up on long-form wiki articles containing horizontal rules.

## [0.3.0] — 2026-05-09

### Added

- `scripts/build-karpathy-index.py` builds `02-wiki/index.md` and `02-wiki/log.md` in the format that Understand-Anything's `parse-knowledge-base.py` requires (`## Section` headings + `[[wikilink]]` rows for index, `## [YYYY-MM-DD] OPERATION | Title` rows for log). It scans `02-wiki/` frontmatter (using PyYAML when available, with a minimal fallback parser) and clusters articles into 5–12 categories via, in priority order: a `category` frontmatter field, the first non-generic tag, or the `wiki-<domain>-...` filename prefix. `wiki-memory` types are pinned to a trailing `Memory-snapshots` section. Log entries come from `01-raw/sessies/raw-sessie-YYYY-MM-DD-*.md` filenames, with titles read from frontmatter when present. Flags: `--dry-run`, `--force` (writes `.bak` before overwrite), `--vault-root`, `--wiki-dir`, `--sessies-dir`. Refuses to overwrite without `--force`; honours dry-run.
- README and POST-INSTALL document the optional `/understand-knowledge` (Understand-Anything plugin) workflow as Step 8: install plugin, build index, run skill, browse dashboard. Existing graphify integration stays unchanged; the two are complementary (graphify uses semantic embeddings + hyperedges, Understand-Anything uses wikilinks + per-batch LLM analysis with categorised layers and a guided tour).

### Changed

- `POST-INSTALL.md` step numbering shifted: graphify stays at Step 7, the new knowledge-graph dashboard step is Step 8, autoresearch is Step 9, backfill is Step 10.

### Background

The integration grew out of a hands-on test of Understand-Anything against a real KennisBank vault. The detector requires `index.md` and `log.md` and does not generate them itself; `/wiki` does not write a centralised index either. `build-karpathy-index.py` closes that gap so users do not run into the same `Not a Karpathy-pattern wiki` error during their first `/understand-knowledge` invocation.

## [0.2.0] — 2026-05-08

### Added

- `AGENTS.md`, `TROUBLESHOOTING.md`, `POST-INSTALL.md`, `CONFIGURATION.md`, `OBSIDIAN.md` — install, troubleshooting, post-install walkthrough, configuration reference, Obsidian setup.
- `scripts/doctor.sh` — 12-check health verifier for vault, scripts, templates, commands, skill installation.
- `commands/import.md` (`/import` slash command) plus three importers: `scripts/import-cc-history.py`, `scripts/import-claudeai-export.py`, `scripts/import-folder.py` (with `--list-cowork-candidates`).
- `commands/sessiestart.md` (`/sessiestart` slash command) — briefing flow at session start.
- `setup.sh` flags: `--yes`, `--no-commands`, `--no-skill`, `--help` for non-interactive install.

### Fixed

- Documentation discrepancies surfaced by the publish-check: `THRESHOLD_DAYS` removed (never existed), `MIN_CONFIDENCE` and `MAX_NEW_LINKS` documented, `LEARNINGS_FILE` clarified as a convention not a config, doctor's Python warning relaxed, README numbering repaired.

## [0.1.0] — 2026-04-26

### Added

- Initial release. Core slash commands (`/sessielog`, `/wiki`, `/intake`, `/stale`), four utility scripts (`auto-crosslink.py`, `intake-scan.py`, `semantic-tiling.py`, `stale-check.py`), session-log and wiki-article templates, vault scaffolding via `setup.sh`, `/autoresearch` skill, `CLAUDE.md.template`.

[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.1
[0.6.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.6.0
[0.5.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.5.0
[0.4.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.4.0
[0.3.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.3.0
[0.2.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.2.0
[0.1.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.1.0
