# KennisBank MCP Tool Contract — `kb-mcp.py`

Source: `scripts/kb-mcp.py` (348 lines), deployed to
`$VAULT/.claude/scripts/kb-mcp.py` by the same `copy_force` loop as every
other script in the Script Layer container. Cross-checked against
[`c4-component-measurement-and-integration.md`](../c4-component-measurement-and-integration.md)
§5.1.

MCP is not REST — this is a tool contract, not an OpenAPI spec. It documents
the [Model Context Protocol](https://modelcontextprotocol.io) surface KennisBank
exposes over **stdio only**: every tool is a one-line delegate to a pure,
independently-testable `<name>_tool()` Python function (`recall_tool`,
`capture_tool`, `review_pending_tool`, `review_decide_tool`,
`what_did_i_do_tool`, `timeline_tool`, `weeklog_tool`, `topic_timeline_tool`),
registered onto an `MCPServer`/`FastMCP` instance inside `build_server()`.

## Sovereignty boundary (hard, documented in-source)

`kb-mcp.py` binds **no network socket**. Transport is stdio only
(`srv.run()`, default transport). A remote/hosted agent cannot reach it —
that gap is deliberate; the manual export bridge `kb-ask.py` (Retrieval
Engine, part of the Script Layer container) exists for exactly that case,
and copying its output is a human action, not an automatic tunnel.

## Process lifecycle

This is the one KennisBank surface with a **long-lived-per-session** process
model, unlike every other script in the Script Layer container (which are
one-shot hook/CLI invocations). Verifiable from source, and only this:

- The **client** (any local MCP client — Claude Code, Codex CLI, GitHub
  Copilot in VS Code, Cline, Windsurf, LM Studio, Claude Desktop) spawns and
  owns the process. `kb-mcp.py` has no self-supervision, no restart policy,
  and no daemon mode of its own — its lifetime is entirely the client's
  concern.
- `build_server()` returns `None` when the optional `mcp` SDK package is not
  installed; `main()` then writes one line to stderr
  (`"kb-mcp: 'pip install mcp' nodig om de MCP-server te draaien."`) and
  returns `0` — a missing dependency is reported, not crashed on.
- The top-level `__main__` guard wraps `main()` in a bare `try/except` and
  calls `sys.exit(0)` on any exception — this component **never** signals
  failure via exit code, mirroring the fail-open convention used by hook
  coordinators elsewhere in KennisBank.
- `os.environ.setdefault("KENNISBANK_VAULT", str(Path(__file__).resolve().parents[2]))`
  (`kb-mcp.py:38`) — self-locates the vault only because it is deployed
  three directories below vault root (`$VAULT/.claude/scripts/kb-mcp.py`);
  an explicit `KENNISBANK_VAULT` environment variable set by the client
  still wins, since `setdefault` only fills an unset variable.
- **Not verifiable from this repository, and not asserted here**: exactly
  when a given MCP client spawns the process (at client startup vs. lazily
  on first tool call) or how it retries a crashed server. That is
  client-side behaviour with no KennisBank-owned evidence.

## Registration — which harnesses actually run this

Per the Agent Integration component (`c4-component-agent-integration.md`
§5.5): **Claude Code registers no MCP server from this layer at all** — it
reaches KennisBank exclusively through hooks (see the Script Layer
container). Codex CLI (`~/.codex/config.toml`,
`[mcp_servers.kennisbank]`), OpenCode (`~/.config/opencode/opencode.json`,
`mcp.kennisbank`), and GitHub Copilot CLI (`~/.copilot/mcp-config.json`,
`mcpServers.kennisbank`) get it written and idempotently validated by
`install-agent-envs.py` / `_copilot.py` (both in the Script Layer container).
A user may register `kennisbank` in their own personal Claude Code MCP
config, but nothing KennisBank ships does that for them — **on a
Claude-only install, this container is deployed to disk but never actually
running unless the user opts in themselves.**

`setup.sh` installs the `mcp==1.28.1` pip package only when `--agents`
includes `codex`, `opencode`, or `copilot` — not for a `claude`-only
install, consistent with the above.

## Tools

All tools return **plain text** (a few return a JSON string as that text,
noted below) — MCP tool results are strings, not typed objects.

### `recall(query: str, k: int = 5) -> str`

Read-only retrieval over the wiki + memory layers (PULL-retrieval — the
pull-nudge counterpart to the hook-driven push retrieval the Script Layer
performs automatically on every prompt).

- Empty/whitespace query → `""`.
- Embeds `query` via `_embeddings.embed`; a `None` vector or a missing
  `kb-recall` import → `"Geen treffers (model onbereikbaar of index
  ontbreekt)."` ("No hits — model unreachable or index missing.")
- On hits, formats each as
  `- [wiki|geheugen] [[stem|Title]] (score): snippet`.
- Any exception anywhere → `"Geen treffers (fout bij ophalen)."` ("No hits —
  error while fetching.")

### `capture(title: str, body: str, memory_type: str = "feit", importance: int = 3) -> str`

Writes a new memory fragment (PULL-write) — for agents with no KennisBank
hooks that still want to contribute durable knowledge.

- Empty `title` or `body` (after `.strip()`) → refuses with
  `"Niets vastgelegd: titel en inhoud zijn beide vereist."` — nothing is
  written.
- Always writes with `status="unverified"`, `evidence_basis="agent"`. There
  is **no write-time reconcile call here** — promotion to `current` (or
  supersede/retraction) happens later, either via the next `memory-sweep.py`
  judge pass (Knowledge Processing) or a human `review_decide`. This tool
  never promotes its own write.
- Any exception → `f"Kon de memory niet vastleggen ({type(e).__name__}).
  Niets geschreven."` — fail-soft, never a crash, never a silent partial
  write.

### `review_pending(k: int = 10) -> str`

Renders the unverified-memory review queue, oldest first — pure read, calls
`_memory.pending_reviews(limit=k)`.

- Empty queue → `"Review-queue leeg: geen unverified memories."`
- Unreadable queue (any exception) → `"Review-queue niet leesbaar (fout bij
  scannen)."`
- Otherwise one line per item:
  `- [[stem]] [memory_type/importance] (age_daysd, evidence_basis) title: snippet[:120]`.

### `review_decide(stem: str, decision: str) -> str`

Executes **one** human review decision. Decision values: `approve`,
`reject`, `skip` — note this is a **superset** of the Atlas sidecar's
`POST /memory/decide` HTTP route, which accepts only `approve`/`reject`.

- Delegates to the same shared `_memory.decide(stem, decision, via="mcp")`
  helper the CLI and Atlas both call — one audit log
  (`.claude/memory-review-log.jsonl`), one set of guards, three surfaces.
- Crash-safe by contract: on any exception the item stays `unverified` in
  the queue and the tool reports the error text (plus a `(code N)` suffix
  when the exception carries a `.code`) — it never silently marks something
  "handled" that wasn't.
- `skip` → `"Overgeslagen: [[stem]] blijft unverified in de queue."`
- A real decision → `"Beslist: [[stem]] -> new_status."`

**Behavioural contract carried in the tool's own docstring, not merely
convention**: this tool must be called *only* after the human has explicitly
decided, per item, in the conversation — the agent must never decide on the
user's behalf. The same rule is restated in the `kennisbank://instructions`
resource text (below).

### `what_did_i_do(date_or_period: str, topic: str = "", project: str = "", max_events: int = 25) -> str`

Temporal activity recall for a date or period, returned as a **JSON string**
(`json.dumps(..., indent=2, ensure_ascii=False)`), not prose. Delegates to
`_activity.what_did_i_do()` (Index Store component). If the `_activity`
module failed to import, or the call raises, returns a JSON envelope
`{"ok": false, "warnings": [...], "events": []}` rather than an error string
— callers should always expect valid JSON from this tool, success or not.

### `timeline(period: str, topic: str = "", project: str = "", max_events: int = 50) -> str`

Chronological activity timeline for a period/topic, JSON string. Same
`_activity` dependency and same `{"ok": false, ...}` degradation shape as
`what_did_i_do`.

### `weeklog(period: str = "vorige week", topic: str = "", project: str = "", max_events: int = 100) -> str`

Weekly rollup with source references, JSON string. Default period is
`"vorige week"` (Dutch: "last week") — the tool is bilingual in practice
(`_activity`'s period parser handles nl/en/de/fr/es/it) but the *default
argument value* is Dutch. Same degradation shape.

### `topic_timeline(topic: str, period: str = "afgelopen 90 dagen", project: str = "", max_events: int = 80) -> str`

Follows one topic/entity through time via activity events, JSON string.
Default period `"afgelopen 90 dagen"` ("past 90 days"). Same degradation
shape.

## Resource

### `kennisbank://instructions`

Best-effort registered (wrapped in its own `try/except` because not every
MCP SDK version exposes `.resource()`) — a static pull-nudge text telling
the client: call `recall` before external search or assumptions; call
`capture` for reusable facts/preferences/procedures/decisions; call the four
temporal tools for date/period/topic questions; call `review_pending` /
`review_decide` only after an explicit per-item human decision, never on the
user's own behalf; and that the vault never leaves the machine.

**GitHub Copilot CLI does not support MCP resources at all** — only tools.
For that harness the equivalent nudge lives in `.github/copilot-instructions.md`
/ `~/.copilot/copilot-instructions.md` instead (written by `_copilot.py`,
Script Layer container), not in this resource.

## Error and degradation summary

| Situation | Behaviour |
|---|---|
| `mcp` package not installed | `build_server()` returns `None`; `main()` logs to stderr, exits 0 |
| Embedding backend / index unreachable (`recall`) | Returns a Dutch "no hits" sentence, never an exception |
| Empty title/body (`capture`) | Refuses with a message; nothing written |
| Any exception in a tool body | Caught locally; returns an error string (text tools) or `{"ok": false, ...}` (JSON tools) — the MCP call itself always succeeds |
| Any uncaught exception reaching `main()` | `sys.exit(0)` — never a non-zero process exit |

## What this is not

- Not a network service — no HTTP, no socket, nothing reachable off the
  local machine.
- Not the same process family as the hook coordinators in the Script Layer
  container, even though the file ships via the identical deploy step — the
  distinguishing fact is *process lifecycle* (long-lived stdio server owned
  by an external MCP client vs. one-shot subprocess spawned per event/CLI
  call), not deployment path.
- Not guaranteed running on every install — see "Registration" above.
