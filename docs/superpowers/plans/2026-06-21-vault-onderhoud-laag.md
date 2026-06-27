# Vault-onderhoud & denkgereedschap-laag — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task: write failing test, run it (red), implement, run it (green), commit.

**Spec:** `docs/superpowers/specs/2026-06-21-vault-onderhoud-laag.md` (R1-R8).

**Goal:** Add a vault-maintenance and thinking layer to LLmWiki-KennisBank: a deterministic safe-edit engine with hybrid autonomy and a git safety net (R1, R3), a self-rewriting `/wiki` (R2), contradiction detection + `/reconcile` with an audit trail (R4, R5), and three thinking/context tools — `/uitdaag` (R6), `/brug` (R7), and progressive context budgets L0-L3 (R8). Target release v0.8.0.

**Architecture:** Two clean layers, matching the repo's existing split.
- **Deterministic Python scripts** (`scripts/*.py`) do mechanical, testable work: classify a diff, apply+commit, embed+match, scan for conflicts, select context layers. They take their inputs by dependency injection (embeddings/cache/text passed in) so unit tests never need a live Ollama.
- **Claude command files** (`commands/*.md`) do the LLM-driven judgement: composing the rewritten article (preserving frontmatter), choosing which side of a contradiction wins, phrasing a challenge. They call the scripts.
- All embedding work reuses `scripts/_embeddings.py` (`embed`, `cosine`, `get_cached`, `embed_id`, `load_cache`, `save_cache`, `doc_text`). Nothing re-implements embeddings or adds a cloud provider.
- Frontmatter preservation during a rewrite is the **command's** responsibility (it composes the full new file). The safe-edit engine is content-agnostic: it diffs and applies whole-file content.

**Tech stack:** Python 3.12 stdlib (`difflib`, `subprocess`, `argparse`, `json`, `unittest`), `git`, markdown command files. No new third-party dependency.

## Global Constraints

- **Cross-platform: every script and test must work on macOS, Linux, and Windows (Git Bash).** Use `pathlib`, never hardcode `/`. Tests that shell out to `git` must `git init` a temp repo and set `user.email`/`user.name` locally so they pass in CI with no global git identity.
- **Vault path** resolves via `_vaultpath.vault_root()` (env `KENNISBANK_VAULT`, fallback `~/KennisBank`). Never hardcode `~/KennisBank`.
- **Wiki articles** live in `<vault>/02-wiki/*.md`; raw session logs in `<vault>/01-raw/sessies/raw-sessie-YYYY-MM-DD.md`. Skip `index.md` and `log.md` when scanning wiki (same as `semantic-tiling.py`).
- **Testability by injection:** every script exposes a pure core function (classification, matching, layer selection) that takes data in and returns data out, plus a thin CLI/`main()` that wires the real backend. Unit tests call the pure core with fixture data; no network, no Ollama.
- **Reuse, don't reinvent:** embeddings via `_embeddings.py`; frontmatter via `_frontmatter.py`; slug/time via `_common.py`. Hyphenated scripts are loaded in tests via `tests._loader.load_script("name.py")`; underscore modules import directly after adding `scripts/` to `sys.path`.
- **CI must stay green** (`.github/workflows/ci.yml`):
  - `python3 -m py_compile scripts/*.py`
  - `bash -n setup.sh scripts/doctor.sh`
  - `python3 -m unittest discover -s tests -v`
- **No new providers, no Google.** Retrieval and research stay local (Ollama) or the already-swappable `_embeddings` backends. No Grok/Perplexity/Gemini.
- **Edits go in the repo source** (`commands/*.md`, `scripts/*.py`), never in a deployed `~/.claude` or vault copy.
- **Git discipline:** work on branch `feat/vault-onderhoud-laag` (already created). One commit per task with a conventional message. Do not merge to `main`.

## Locked design decisions (resolving the spec's open questions)

- **R1 change classification (was blocking).** A proposed edit is **klein** when ALL hold: net changed lines `<= KB_EDIT_MAX_LINES` (default 20); no markdown heading (`^#{1,6} `) is removed; net removed non-blank body lines `<= KB_EDIT_MAX_DROP` (default 3); the target file is not being emptied/deleted. Otherwise **groot**. Deterministic, no embeddings.
- **R8 vs cozempic.** `context-budget.py` is standalone and only *emits* layered context; it never calls cozempic and never prunes the live window. `/sessiestart` uses it at default level L1 and offers deeper levels on request. It complements cozempic, does not duplicate it.
- **R7 `/brug`.** Graph-first: use `graphify-out/graph.json` if present to find bridging paths between two clusters; fall back to embedding-space nearest-common articles when no graph exists.

---

### Task 1: Safe-edit engine (`scripts/safe-edit.py`) — R1, R3

**Files:**
- Create: `scripts/safe-edit.py`
- Create: `tests/test_safe_edit.py`

**Interfaces:**
- Pure core (testable, no git, no embeddings):
  - `classify(old: str, new: str, max_lines: int = 20, max_drop: int = 3) -> str` → `"klein"` or `"groot"` per the locked rule.
  - `unified(old: str, new: str, path: str) -> str` → unified diff string (via `difflib.unified_diff`).
- CLI: `python3 safe-edit.py <target> --new <file|-> [--confirm] [--force] [--message MSG] [--json]`
  - Reads proposed content from `--new` file path, or stdin if `--new -`.
  - Git guard: if `<target>`'s repo is not a git repo, or the working tree has unstaged/uncommitted changes to files other than `<target>`, refuse with exit 3 unless `--force`.
  - If `classify == "klein"`: write the file, `git add` + `git commit -m MSG` (default prefix `wiki-rewrite:`), report `{"action":"applied","size":"klein"}`.
  - If `classify == "groot"` and not `--confirm`: print the unified diff, report `{"action":"needs-confirm","size":"groot"}`, exit code 2 (no write).
  - If `classify == "groot"` and `--confirm`: write + commit as above, report `{"action":"applied","size":"groot"}`.
  - New-file case (target does not exist): treated as `klein` only if the new file is short (`<= max_lines`), else `groot`; same apply/commit path.

- [ ] **Step 1: Write the failing test** — `tests/test_safe_edit.py`
  - Import via `from tests._loader import load_script; se = load_script("safe-edit.py")`.
  - `classify` unit tests (no git): identical text → `"klein"`; a 2-line typo fix → `"klein"`; removing a `## heading` → `"groot"`; adding 30 new lines → `"groot"`; dropping 5 body lines → `"groot"`.
  - CLI integration tests using a temp git repo: helper `make_repo()` that `tempfile.mkdtemp()`, `git init`, `git config user.email/name`, writes a seed article, commits. Then:
    - small edit applied + committed without `--confirm` (assert file changed, assert one new commit, assert JSON `action=applied`).
    - large edit without `--confirm` → exit code 2, file unchanged, no new commit.
    - large edit with `--confirm` → applied + committed.
    - dirty-tree guard: create an unrelated unstaged change, run on a different file → exit 3 unless `--force`.
- [ ] **Step 2: Run test, verify red** — `python3 -m unittest tests.test_safe_edit -v`
- [ ] **Step 3: Implement `scripts/safe-edit.py`** per the interface. Use `subprocess.run(["git", "-C", repo, ...])`. Resolve repo root with `git rev-parse --show-toplevel`. Keep `classify`/`unified` import-safe (no side effects at import).
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: `python3 -m py_compile scripts/safe-edit.py`**
- [ ] **Step 6: Commit** — `feat(safe-edit): deterministic hybrid-autonomy edit engine with git safety net`

---

### Task 2: Candidate-match helper (`scripts/find-similar.py`) — R2 support

**Files:**
- Create: `scripts/find-similar.py`
- Create: `tests/test_find_similar.py`

**Interfaces:**
- Pure core: `best_match(target_vec: list, candidates: dict[str, list]) -> tuple[str|None, float]` → highest-cosine `(path, score)` using `_embeddings.cosine`; `(None, 0.0)` if no candidates.
- CLI: `python3 find-similar.py <article-or-text> [--threshold T] [--json]`
  - If arg is an existing `.md` path, embed its `doc_text`; else embed the literal string.
  - Compare against cached embeddings of `02-wiki/*.md` (reuse `load_cache`/`get_cached`, skip `index.md`/`log.md` and the target itself).
  - Threshold env `KB_REWRITE_THRESHOLD` (default `0.62`); CLI `--threshold` overrides.
  - Output best match `{path, score, above_threshold: bool}` or `{path: null}` when below.

- [ ] **Step 1: Write the failing test** — `tests/test_find_similar.py`
  - Unit-test `best_match` with injected vectors: orthogonal vs near-parallel; assert it picks the highest score; empty candidates → `(None, 0.0)`.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Implement `scripts/find-similar.py`.** Keep `best_match` pure; CLI wires `_embeddings`.
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: `py_compile`.**
- [ ] **Step 6: Commit** — `feat(find-similar): embedding candidate-match for self-rewrite`

---

### Task 3: Shared retrieval CLI (`scripts/kb-search.py`) — supports R6, R7, R8

**Files:**
- Create: `scripts/kb-search.py`
- Create: `tests/test_kb_search.py`

**Rationale:** `kb-retrieve.py` is a stdin hook; `/uitdaag`, `/brug`, and context L2 need a **query-string CLI** returning the top matches. Factor that shared logic here (do not change `kb-retrieve.py`'s hook contract).

**Interfaces:**
- Pure core: `rank(query_vec: list, candidates: dict[str, list], top_n: int, threshold: float) -> list[tuple[str, float]]` → sorted desc, filtered by threshold, capped at `top_n`.
- CLI: `python3 kb-search.py "<query>" [--top N] [--threshold T] [--json]` → JSON list of `{path, score, snippet}` (snippet = first ~200 chars of `doc_text`). Reuses `KB_RETRIEVE_THRESHOLD`/`KB_RETRIEVE_TOP_N` defaults (0.60 / 3).

- [ ] **Step 1: Write the failing test** — `tests/test_kb_search.py` unit-tests `rank` with injected vectors: ordering, threshold filter, `top_n` cap.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Implement `scripts/kb-search.py`.**
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: `py_compile`.**
- [ ] **Step 6: Commit** — `feat(kb-search): query-string retrieval CLI shared by thinking tools`

---

### Task 4: Self-rewriting `/wiki` (`commands/wiki.md`) — R2

**Files:**
- Modify: `commands/wiki.md`
- Create: `tests/test_command_structure.py`

**Interfaces:**
- Consumes: `scripts/find-similar.py` (Task 2), `scripts/safe-edit.py` (Task 1).
- Produces: a `wiki.md` whose compile flow, **after the existing Step 3 (Check existing wiki)**, inserts **Step 3.5 — Bestaand artikel herschrijven**: run `find-similar.py` on the candidate topic; if a match is `above_threshold`, compose the improved full article text **preserving the existing frontmatter** (`created`, `tags`, backlinks, status) and route it through `safe-edit.py <match> --new - --message "wiki-rewrite: <topic>"`; if `safe-edit` returns `needs-confirm`, surface the diff to the user and wait. Below threshold → existing create-new path. Update Step 5 reporting to distinguish `herschreven` / `nieuw` / `overgeslagen`.

- [ ] **Step 1: Write the failing test** — `tests/test_command_structure.py` asserts `commands/wiki.md` contains the strings `find-similar`, `safe-edit`, `3.5`, and `wiki-rewrite:` and still contains the original step markers.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Edit `commands/wiki.md`** to add Step 3.5 and the reporting change. Keep instructions concrete and ordered.
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: Commit** — `feat(wiki): self-rewrite existing articles via find-similar + safe-edit`

---

### Task 5: Contradiction detection (`scripts/conflict-scan.py`) — R4

**Files:**
- Create: `scripts/conflict-scan.py`
- Create: `tests/test_conflict_scan.py`

**Interfaces:**
- Pure core:
  - `candidate_pairs(embeddings: dict[str, list], sim_threshold: float) -> list[tuple[str, str, float]]` → unordered article pairs with cosine `>= sim_threshold` (the overlap pre-filter).
  - `contradiction_signal(text_a: str, text_b: str) -> float` → 0..1 heuristic: shared key terms combined with opposing markers (negation tokens `geen/niet/no/not`, mismatched numbers/years on a shared noun). Deliberately recall-biased; false positives allowed (the report is a proposal, not an auto-edit).
- CLI: `python3 conflict-scan.py [--sim T] [--json]` → markdown/JSON report of candidate conflicting pairs over `02-wiki/*.md`, each with both excerpts, `updated` dates from frontmatter, and the signal score. Env `KB_CONFLICT_SIM` (default `0.62`).
- Mirrors `stale-check.py`'s scan/report shape.

- [ ] **Step 1: Write the failing test** — unit-test `candidate_pairs` (injected vectors: only the high-cosine pair returned) and `contradiction_signal` (a "X is geen Y" vs "X is Y" pair scores higher than two agreeing texts).
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Implement `scripts/conflict-scan.py`** (reuse `_frontmatter.parse_frontmatter`, `_embeddings`, `_vaultpath`).
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: `py_compile`.**
- [ ] **Step 6: Commit** — `feat(conflict-scan): detect candidate contradictory article pairs`

---

### Task 6: `/reconcile` command (`commands/reconcile.md`) — R5

**Files:**
- Create: `commands/reconcile.md`
- Modify: `tests/test_command_structure.py` (extend)

**Interfaces:**
- Consumes: `conflict-scan.py` (Task 5), `safe-edit.py` (Task 1).
- Produces: `commands/reconcile.md` driving: run `conflict-scan.py`; present each candidate pair with dates; let the user pick the surviving claim; apply the correction through `safe-edit.py` (prefix `reconcile:`); append an audit line to `<vault>/02-wiki/reconciliation-log.md` in the form `- YYYY-MM-DD [[winner]] over [[loser]] — reden: <...>`. Never auto-delete an article; large changes go through safe-edit's confirm path.

- [ ] **Step 1: Extend test** — assert `commands/reconcile.md` references `conflict-scan`, `safe-edit`, `reconciliation-log.md`, and the `reconcile:` commit prefix.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Write `commands/reconcile.md`.**
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: Commit** — `feat(reconcile): contradiction reconciliation with audit trail`

---

### Task 7: `/uitdaag` command (`commands/uitdaag.md`) — R6

**Files:**
- Create: `commands/uitdaag.md`
- Modify: `tests/test_command_structure.py` (extend)

**Interfaces:**
- Consumes: `kb-search.py` (Task 3); optionally `graphify-out/graph.json`.
- Produces: `commands/uitdaag.md` that takes `$ARGUMENTS` (a stelling/beslissing), runs `kb-search.py "<stelling>" --top 5`, reads the matched articles, and returns counter-arguments, precedents, and blind spots **grounded only in the vault**, each citing its `[[bron-artikel]]`. If no matches clear the threshold, say so plainly rather than inventing.

- [ ] **Step 1: Extend test** — assert `uitdaag.md` references `kb-search` and `[[` citation and `$ARGUMENTS`.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Write `commands/uitdaag.md`.**
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: Commit** — `feat(uitdaag): vault-grounded challenge tool`

---

### Task 8: `/brug` command (`commands/brug.md`) — R7

**Files:**
- Create: `commands/brug.md`
- Modify: `tests/test_command_structure.py` (extend)

**Interfaces:**
- Consumes: `kb-search.py` (Task 3); `graphify-out/graph.json` when present.
- Produces: `commands/brug.md` that takes two topics from `$ARGUMENTS`, pulls each side's articles via `kb-search.py`, and surfaces non-obvious connections. **Graph-first:** if `graphify-out/graph.json` exists, look for short bridging paths between the two clusters and explain the linking nodes; **fallback:** when no graph, report articles that score moderately against *both* queries (embedding-space bridges). Cite `[[articles]]`.

- [ ] **Step 1: Extend test** — assert `brug.md` references `kb-search`, `graph.json`, and the fallback behaviour, plus `$ARGUMENTS`.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Write `commands/brug.md`.**
- [ ] **Step 4: Run test, verify green.**
- [ ] **Step 5: Commit** — `feat(brug): cross-domain bridge tool (graph-first, embedding fallback)`

---

### Task 9: Progressive context budgets (`scripts/context-budget.py` + `commands/sessiestart.md`) — R8

**Files:**
- Create: `scripts/context-budget.py`
- Create: `tests/test_context_budget.py`
- Modify: `commands/sessiestart.md`

**Interfaces:**
- Pure core: `select_layers(level: int, state: dict) -> dict` where `state` carries the raw inputs (identity text, open-loops list, ranked articles, full bodies) and the function returns only the layers `<= level`:
  - L0 identity; L1 + active state (open loops, recent sessions, status counts); L2 + top-N relevant article summaries; L3 + full article bodies. Each higher level is a superset.
- CLI: `python3 context-budget.py --level N [--query "..."]` → assembles the real state (`CLAUDE.md` head, sessiestart-style scans, `kb-search.py` for L2/L3) and prints the selected layers. Default level via `KB_CONTEXT_LEVEL` (default `1`).
- `commands/sessiestart.md`: add a "Context-lagen (L0-L3)" section that calls `context-budget.py --level 1` by default and tells the user how to request deeper levels. Add a one-line note that this complements (does not replace) cozempic context hygiene.

- [ ] **Step 1: Write the failing test** — unit-test `select_layers`: level 0 returns only identity; level 2 includes L0+L1+L2 keys and excludes L3 bodies; level 3 is the full superset; unknown article list is handled gracefully.
- [ ] **Step 2: Run test, verify red.**
- [ ] **Step 3: Implement `scripts/context-budget.py`** (pure `select_layers` + CLI wiring) and edit `commands/sessiestart.md`.
- [ ] **Step 4: Run test, verify green** and assert via `tests/test_command_structure.py` that `sessiestart.md` references `context-budget`.
- [ ] **Step 5: `py_compile`.**
- [ ] **Step 6: Commit** — `feat(context-budget): progressive L0-L3 context layers wired into sessiestart`

---

### Task 10: Deploy, docs, doctor, changelog (v0.8.0)

**Files:**
- Modify: `setup.sh` (verify commands/scripts globs cover the new files; add explicit checks only if needed)
- Modify: `scripts/doctor.sh` (assert the new scripts and commands are present)
- Modify: `CONFIGURATION.md` (document `KB_EDIT_MAX_LINES`, `KB_EDIT_MAX_DROP`, `KB_REWRITE_THRESHOLD`, `KB_CONFLICT_SIM`, `KB_CONTEXT_LEVEL`)
- Modify: `README.md` (component table: new scripts + commands)
- Modify: `CHANGELOG.md` (`## [0.8.0]` section + link refs)
- Modify: `tests/test_setup_deploy.py` (assert new scripts + at least one new command deploy)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: green CI, a documented and deploy-tested v0.8.0 surface.

- [ ] **Step 1: Extend `tests/test_setup_deploy.py`** to assert `<vault>/.claude/scripts/safe-edit.py` and `<home>/.claude/commands/reconcile.md` deploy after `bash setup.sh --yes`. Run, verify red if a glob misses them.
- [ ] **Step 2: Fix `setup.sh`** only if the test is red (the `scripts/*.py` and `commands/*.md` loops should already cover new files; confirm).
- [ ] **Step 3: Update `scripts/doctor.sh`** to check the new scripts/commands exist (`bash -n` must stay clean).
- [ ] **Step 4: Update `CONFIGURATION.md`, `README.md`, `CHANGELOG.md`** (add `## [0.8.0] - 2026-06-21` summarizing R1-R8 and the new env vars; update the `[Unreleased]`/`[0.8.0]` link refs).
- [ ] **Step 5: Run the full gate:**
  ```
  python3 -m py_compile scripts/*.py
  bash -n setup.sh scripts/doctor.sh
  python3 -m unittest discover -s tests -v
  ```
  Expected: all green.
- [ ] **Step 6: Commit** — `docs+setup: deploy, document, and changelog the vault-onderhoud layer (v0.8.0)`

---

## Self-Review

**Spec coverage:**
- R1 safe-edit engine + hybrid autonomy + git net — Task 1. ✓
- R2 self-rewriting `/wiki` — Tasks 2, 4. ✓
- R3 git-net mandatory — Task 1 (dirty-tree/non-repo guard). ✓
- R4 conflict detection — Task 5. ✓
- R5 reconciliation + audit trail — Task 6. ✓
- R6 `/uitdaag` — Tasks 3, 7. ✓
- R7 `/brug` — Tasks 3, 8. ✓
- R8 L0-L3 context budgets — Task 9. ✓
- Deploy/docs/changelog — Task 10. ✓

**Reuse check:** embeddings via `_embeddings.py` (Tasks 2, 3, 5, 9); frontmatter via `_frontmatter.py` (Tasks 5); vault path via `_vaultpath.py` (all scripts); no new provider; `kb-retrieve.py` hook contract untouched (new `kb-search.py` for query-string callers).

**Testability:** every script has a pure core (`classify`, `best_match`, `rank`, `candidate_pairs`/`contradiction_signal`, `select_layers`) unit-tested with injected data — no Ollama in CI. Git behaviour tested in a temp repo with local identity.

**Placeholder scan:** no TBD/TODO; `<vault>`, `<topic>`, `<match>`, `N`, `T`, `MSG` are runtime values inside CLI/command instructions, not plan gaps.

**Naming consistency:** env vars `KB_EDIT_MAX_LINES`, `KB_EDIT_MAX_DROP`, `KB_REWRITE_THRESHOLD`, `KB_CONFLICT_SIM`, `KB_CONTEXT_LEVEL`; commit prefixes `wiki-rewrite:` / `reconcile:`; layer names L0-L3 — used identically across tasks.
