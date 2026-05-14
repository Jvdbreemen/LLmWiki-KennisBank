# Changelog

All notable changes to LLmWiki-KennisBank are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.4.0
[0.3.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.3.0
[0.2.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.2.0
[0.1.0]: https://github.com/Jvdbreemen/LLmWiki-KennisBank/releases/tag/v0.1.0
