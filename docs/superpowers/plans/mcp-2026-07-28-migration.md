# MCP 2026-07-28 — migration plan for `scripts/kb-mcp.py`

**Status:** design document for TASK-100. Supersedes the version of this file dated
2026-07-30 00:33, which recommended an immediate pin bump to `mcp>=2.0.0,<3` as step 3.
That recommendation is **withdrawn** — not because it was wrong in direction, but
because three adversarial reviews plus measurement on this machine established that the
bump buys nothing observable today and that the highest-value work is version-neutral.
Everything still correct in the old version is carried forward, and each reversal is
named in §10.

**Scope:** `scripts/kb-mcp.py` (local stdio MCP server), its dependency pin, and the
tool surface it exposes.

> **Concurrent change, reconciled 2026-07-30.** While this plan was being written another
> session landed the *old* plan's step 1 (TASK-101, "fail loudly on an incompatible SDK"):
> `scripts/kb-mcp.py` is now **377 lines**, not 348. The change is good and is **retained**
> — it splits "package absent" (stderr note, exit 0) from "package present but the server
> API is unusable" (named exception, exit 1) via new `SDK_ABSENT`/`SDK_ERROR` module
> globals at `47-49`, and it replaces the blanket `except Exception: sys.exit(0)` with
> `except (KeyboardInterrupt, BrokenPipeError)`. That removes the silent-success failure
> mode this plan's §3 describes as the worst diagnosis path. Every line citation below is
> against the **post-TASK-101** file. Two consequences carried into the steps: the blind
> guard `tests/test_kb_mcp.py:69` **still exists** and step 1 still has to replace it; and
> the new remediation strings in `main()` hardcode `mcp>=2.0.0,<3`, which contradicts D4 —
> step 8 aligns them to `>=2.0.1,<3`.

**Hard constraints carried through every step:** stdio only, no network bind, the vault
never leaves the machine; the eight `*_tool()` functions stay importable and callable
with no `mcp` package present; KISS; no existing client breaks at any step.

### How to read the evidence in this document

Two classes of claim, marked differently, because they are not equally durable:

- **Normative** — protocol requirements. Carries the primary-source URL. These were
  fetched 2026-07-29 by the upstream research task feeding this plan, not re-fetched
  while writing it; the URL is the check.
- **Measured** — the state of this machine, this repo, or a shipped client binary.
  Carries `measured 2026-07-30` and *whose* measurement. Client-binary string counts are
  a reviewer's, on one machine, two days after the spec published. They are a dated
  snapshot, not a property of MCP. Facts my recommendation actually rests on
  (encoding behaviour, interpreter drift, SDK signatures) I re-verified myself and
  labelled `verified here`.

Where a source is a blog post or SDK release note it is labelled as such — those
describe an *implementation*, never the protocol. Genuine unknowns are in §9 as
unknowns, not smoothed into facts.

---

## 1. Verdict

**Urgency: none. Nothing is broken, and nothing breaks by waiting.** The spec's own
stdio backward-compatibility rule means a 2026-07-28 client that reaches our
2025-era server falls back to the `initialize` handshake
(<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio>).
Measured in the other direction as well: a *modern-only* server dies against the
clients we actually run — `McpError: Method not found: initialize`, because the
client's first frame is `initialize` and it never probes `server/discover`
(measured 2026-07-30, client-reality reviewer, against `mcp` 1.28.1). Migrating early
can only lose; waiting cannot.

**Recommended route: SDK v2, staged, and currently parked one step before the pin
bump.** The official SDK owns protocol conformance; we write zero wire code. But the
pin bump is the *last* step and it is gated on a measurement rather than scheduled,
because no client we can inspect reads a single one of the new fields yet.

**Do not hand-roll the transport.** The stdlib route was designed in full and refuted
on three independent grounds — see §4.

**The first shippable step is not protocol work at all: tool annotations, ~35 lines,
on the pin we already have.** Claude Code computes both `isReadOnly()` and
`isConcurrencySafe()` directly from `annotations.readOnlyHint` and defaults each to
false when annotations are absent (measured 2026-07-30, client-reality reviewer,
Claude Code 2.1.220 binary: `isConcurrencySafe(){return D.annotations?.readOnlyHint??!1}`).
So today our six read-only retrieval tools present to Claude Code as
possibly-destructive and non-parallelisable — needless confirmation prompts and
serialisation on the hot path, which is a live cost against north stars 1 and 6. That
is the only measured present-day defect on the surface, and it ships today.

### "Minimal dependency versus minimal code" — a straight answer

You asked for minimal dependency *where it goes* ("als het gaat"). Here it does not go,
and the reason is arithmetic rather than taste.

- Staying on `mcp` 1.x **saves nothing**. v1.28.1 already declares starlette, uvicorn,
  sse-starlette, python-multipart and cryptography — every one unreachable from a stdio
  server that never binds a socket. Moving 1.28.1 → 2.0.0 measured **+1.1 MB and one
  package fewer** (61.4 MB/32 pkgs → 62.5 MB/31 pkgs, clean venvs, Python 3.12.9;
  measured 2026-07-30, SDK-v2 design task).
- Only the **stdlib route** actually reduces the footprint, by roughly 62 MB. Its price
  is permanent ownership of a wire protocol — and §4 shows we would have got the era
  model wrong on the first try.
- Its headline benefit is also **overstated**: "works on a bare CPython install" is not
  true in the way that matters. `scripts/kb-recall.py:47` imports `sqlite_vec` inside
  `_open_ro`, which returns `None` on failure, after which `recall_hits` returns `[]`.
  A no-pip vault yields a server that lists eight tools where the flagship one cannot
  reach the index.

So: **minimal code wins over minimal dependency at this boundary.** The thing being
economised on in the stdlib route is protocol correctness, and this project already has
a rule against that trade — one understandable mechanism over three clever ones. The
dependency we keep is the one already installed on both interpreters here.

### The gate on the pin bump

Bump the pin when the need is demonstrated **and** the preconditions hold — both, not
either:

- **Necessity (the trigger):** a client on this machine sends
  `_meta["io.modelcontextprotocol/protocolVersion"]`. Cheap to detect — log the inbound
  value to stderr (§9, Q1).
- **Safety (the precondition):** `mcp` 2.0.1 or later exists on PyPI, **and** steps 1-7
  are green.

Deliberately an AND. The preconditions alone are not a reason to bump: that would ship a
wire-behaviour change with no demonstrated need, which is exactly what §6 and D7 refuse
to do for new tools, and the same discipline applies to the protocol.

One correction to the framing this plan was given: **"mcp 2.0.0 has zero field time" is
false.** PyPI shows a seven-week public pre-release train — 2.0.0a1 2026-06-11, a2
06-16, a3 06-26, b1 06-30, b2 07-14, rc1 07-27, GA 2026-07-28T13:45:28Z
(<https://pypi.org/pypi/mcp/json>; measured 2026-07-30, maintenance reviewer). The
honest residual risk is narrower and different: **zero post-GA patch releases**, so the
post-release bug harvest has not happened. That argues for waiting one patch cycle. It
does not argue for writing our own protocol.

---

## 2. What the 2026-07-28 revision changes for a local stdio server

Read only the changelog and you would conclude this revision is a rewrite. For a stdio
tools-plus-resources server it is not. Three clean buckets.

### 2a. Does not touch us — HTTP-only

All of the loud breakage is Streamable-HTTP surface we never had:

| Removed / changed | Why it cannot reach us |
| --- | --- |
| Protocol-level sessions and the `Mcp-Session-Id` header | No header layer on stdio |
| SSE resumability, `Last-Event-ID` | No SSE |
| Required `Mcp-Method` and `Mcp-Name` headers | No header layer |
| The `x-mcp-header` mechanism | No header layer |
| Every authorization change, incl. OAuth DCR deprecation | We bind no socket and have no auth surface |

The normative basis is one sentence on the stdio page: "All request metadata for the
stdio transport is carried inline in the JSON-RPC message body… There is no header
layer."
<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio>

Stdio framing itself is **unchanged**: newline-delimited JSON-RPC on stdin/stdout, no
embedded newlines, the server MUST NOT write non-MCP output to stdout, MAY write UTF-8
logging to stderr, and the client SHOULD NOT treat stderr as errors (same page).

### 2b. Does touch us

| Change | Requirement | Source |
| --- | --- | --- |
| `initialize` / `notifications/initialized` handshake **removed**; MCP is stateless | Every request carries `_meta["io.modelcontextprotocol/protocolVersion"]` (REQUIRED) and `_meta["io.modelcontextprotocol/clientCapabilities"]` (REQUIRED). Clients SHOULD send `clientInfo`; servers SHOULD send `serverInfo` in each result's `_meta`. Version mismatch → `UnsupportedProtocolVersionError` | [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [schema.ts](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts) |
| `server/discover` | Servers **MUST** implement it. `DiscoverResult extends CacheableResult` with `supportedVersions: string[]`, `capabilities: ServerCapabilities`, optional `instructions` | [server/discover](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) |
| `resultType` | **REQUIRED on every result.** `"complete"` for ordinary results, `"input_required"` for MRTR interim results. Clients MUST treat a missing `resultType` from an earlier-protocol server as `"complete"` | schema.ts |
| `ttlMs` + `cacheScope` | **Both REQUIRED** (not optional) on `CacheableResult`. Six results extend it: `server/discover`, `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`, `resources/read`. `CallToolResult extends Result` only — so it needs `resultType` but **not** the cache fields | schema.ts, [caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching) |
| New error codes | `HEADER_MISMATCH` -32020, `MISSING_REQUIRED_CLIENT_CAPABILITY` -32021, `UNSUPPORTED_PROTOCOL_VERSION` -32022. Resource-not-found moves -32002 → **-32602**. -32000..-32019 stays implementation-defined; -32020..-32099 reserved for the spec | schema.ts |
| Server-initiated requests | Replaced by Multi Round-Trip Requests: the server returns `InputRequiredResult` (`resultType: "input_required"`) with `inputRequests`; the client retries with `inputResponses`. Server MUST NOT write JSON-RPC *requests* to stdout | schema.ts, stdio page |
| Cancellation, shutdown | Client MUST send `notifications/cancelled`; server SHOULD stop promptly and MUST NOT send further messages for that request. Servers SHOULD exit promptly on stdin EOF | stdio page |
| `tools/list` ordering | SHOULD return tools in a deterministic order (helps client-side and prompt caching) | changelog |
| Schema looseness | `inputSchema`/`outputSchema` accept any JSON Schema 2020-12 keywords; `structuredContent` may be any JSON value | schema.ts |

**Era is a property of how the client opens the connection, not of a date.** This is the
single most important sentence in the revision for anyone implementing it, and it is
normative: "A request carrying modern per-request `_meta` is served statelessly
according to this revision. An `initialize` request selects legacy semantics… The era
determination is a property of the server, not of an individual request."
<https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning>

**Backward compatibility is normative and it protects us.** A client supporting both
eras SHOULD probe with `server/discover` first. Three outcomes: (a) a `DiscoverResult`
→ modern server, pick a mutually supported version; (b) a recognised modern error such
as `UnsupportedProtocolVersionError` → modern server, unsupported version, pick from its
list and do **not** fall back to `initialize`; (c) any other error, or no response
within a reasonable timeout → legacy server, fall back to `initialize`. The fallback
MUST NOT be keyed to one specific error code, because legacy servers answer unknown
pre-`initialize` requests with implementation-defined errors (commonly -32601 or -32602)
or not at all.
<https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio>

That rule is why a non-migrated server keeps working. Note its status honestly: the
probe is a client **SHOULD**, and a modern-*only* client need not probe at all. So this
is protection, not a guarantee — see §9 R1.

### 2c. Merely deprecated — minimum twelve-month window

Deprecated is not removed. The lifecycle policy defines Active / Deprecated / Removed
with a floor of at least twelve months from the revision that first marks a feature
Deprecated (<https://modelcontextprotocol.io/community/feature-lifecycle>,
<https://modelcontextprotocol.io/specification/2026-07-28/deprecated>). Note the
lifecycle page is a governance document binding SEP authors, not RFC-2119 text binding
our server.

Deprecated in this revision: **Roots, Sampling, Logging; HTTP+SSE transport; OAuth
Dynamic Client Registration.** The recommended replacement for Logging on stdio is
literally "log to stderr". Also deprecated on arrival: the per-request
`_meta["io.modelcontextprotocol/logLevel"]` field, marked `@deprecated` as of
2026-07-28 (SEP-2577) while remaining for at least twelve months.

We use **none** of these. Full audit in §7. Net action from the entire deprecation
list: zero code changes.

---

## 3. Baseline — what `kb-mcp.py` implements today

377 lines (post-TASK-101). The entire SDK surface is still four call sites; everything the
new revision demands lives underneath them.

| What | Where | Detail |
| --- | --- | --- |
| Vault root | `kb-mcp.py:38` | `os.environ.setdefault("KENNISBANK_VAULT", …parents[2])` |
| **Speculative v2 import**, now with split failure state | `kb-mcp.py:41-63` | `MCPServer`/`SDK_ABSENT`/`SDK_ERROR` at `47-49`. Tries `mcp.server.mcpserver`, falls back to `mcp.server.fastmcp`, and records *which* failed rather than collapsing both to `None` |
| Eight pure tool functions | `83`, `109`, `140`, `157`, `189`, `206`, `223`, `240` | `recall_tool`, `capture_tool`, `review_pending_tool`, `review_decide_tool`, `what_did_i_do_tool`, `timeline_tool`, `weeklog_tool`, `topic_timeline_tool`. All take and return `str`. No SDK import on any of these paths |
| JSON-as-text seam | `177-178` | `_activity_json()` = `json.dumps(payload, indent=2, ensure_ascii=False)`, applied at three sites per temporal tool |
| Pull-nudge constant | `260-274` | `INSTRUCTIONS_TEXT`, reachable **only** as a resource today |
| Server constructor | `281` | `MCPServer("kennisbank-geheugen")` — no `instructions=`, no `version=`, no annotations anywhere |
| Eight `@srv.tool()` registrations | `283`, `289`, `296`, `302`, `309`, `317`, `324`, `331` | All **bare `@srv.tool()`**, nothing positional (verified here) — which is what makes adding `annotations=` safe on both SDK generations despite their differing signatures. Descriptions are Dutch docstrings, distinct from the `*_tool` docstrings |
| One resource | `340-345` | `@srv.resource("kennisbank://instructions")`, wrapped in `try/except Exception: pass` |
| `main()` | `350-367` | **Fixed by TASK-101.** Absent package → stderr note, `return 0`. Package present but API unusable → names the exception, `return 1` |
| `__main__` guard | `370-377` | **Fixed by TASK-101.** `except (KeyboardInterrupt, BrokenPipeError): sys.exit(0)`; everything else propagates |

**Without the `mcp` package the MCP surface still does not exist at all** —
`build_server()` returns `None` (`279-280`) and `main()` returns 0. What TASK-101 changed is
that this is now *distinguishable* from a broken install, which was the worst diagnosis path
and is the one genuine improvement already banked. Only the pure `*_tool()` functions remain
importable and testable, which is the standing contract recorded in the module docstring at
`27-30`.

One item TASK-101 introduced that this plan must correct: the new remediation strings in
`main()` hardcode `mcp>=2.0.0,<3` twice. Per D4 the intended pin is `>=2.0.1,<3` (never
2.0.0 — no post-GA patch cycle), and per §1 the bump is gated. Advising an ungated `>=2.0.0`
in an error message is a small contradiction, and step 8 aligns it.

### Measured state of this machine (verified here, 2026-07-30)

Three-way version drift, and the v2 import branch has never resolved here:

```
python  → 3.12.9  → mcp 1.9.4   → find_spec("mcp.server.mcpserver") = False
py -3   → 3.14.2  → mcp 1.28.1  → find_spec("mcp.server.mcpserver") = False
requirements.txt:2 pins mcp==1.28.1
```

`py -3` is the interpreter `setup.sh:270-274` selects for MCP on Windows, so the
authoritative interpreter has 1.28.1 and the ambient `python` has 1.9.4. That gap
matters, because the two SDKs differ where it counts (verified here):

- `FastMCP.tool` on **1.9.4** takes `(name, description, annotations)` only.
- `FastMCP.tool` on **1.28.1** takes `(name, title, description, annotations, icons,
  meta, structured_output)` — byte-identical to v2's `MCPServer.tool`.
- `ToolAnnotations.model_fields` is identical on both: `destructiveHint`,
  `idempotentHint`, `openWorldHint`, `readOnlyHint`, `title`.
- `__init__` accepts `instructions` on **both**; accepts `version` and `cache_hints` on
  **neither**.

That is why §5 step 1 uses `annotations.title` rather than the `title=` kwarg, and why
any `version=`/`cache_hints=` use must be signature-gated. It is not defensiveness; it
is the measured floor.

### Three false statements currently in the repo

Found while verifying the baseline. All three are load-bearing for decisions in this
plan, so they get fixed in §5 step 2 rather than noted and forgotten.

1. **"GitHub Copilot supports no MCP resources"** — `kb-mcp.py:18-20` (docstring),
   `kb-mcp.py:259` (comment), `README.md:632`. **False on both Copilot surfaces**
   (measured 2026-07-30, client-reality reviewer): VS Code 1.130.0 contains
   `resources/list` ×2, `resources/read` ×5, `resources/templates/list` ×1; Copilot CLI
   1.0.70 contains `resources/list` ×5, `resources/read` ×2, templates ×2, plus
   `listMcpResourceTemplates` and the error string `"MCP resources/list failed for ${e}"`.
   The nuance that survives: VS Code exposes resources as *user-attached context*, not
   as something the model fetches autonomously — so a resource is still a weaker nudge
   carrier than server instructions.
2. **`README.md:534` says "seven primitives: six tools … plus an `instructions`
   resource".** The code has eight tools. `docs/agent-integrations.md` enumerates six.
3. **`tests/test_kb_mcp.py:69` proves nothing** (verified here, and it **survived**
   TASK-101). `test_build_server_none_without_mcp` branches on `MCPServer is None` and
   asserts the matching outcome, so it passes whether or not the SDK is installed and
   whether or not the server works. This is exactly the PR #54 pattern CLAUDE.md has a
   standing rule against — a guard that has never been able to fail. TASK-101 *added* four
   genuinely falsifiable tests around it (`:94` absent-package exits 0, `:103` incompatible
   SDK exits non-zero, `:114` the two paths differ, `:123` import state is consistent, plus
   `:139` module imports without writing to stdout), which is the right pattern — but it
   left the blind one in place, so step 1 still replaces it.

### The two SDK-presence gates that will fail under v2

Both hardcode the v1 module path (verified here):

- `scripts/install-agent-envs.py:790` —
  `dep_check = "import mcp; import mcp.client.stdio; import mcp.server.fastmcp"`
- `scripts/doctor.sh:297` — the identical import, with remediation at `:302` advising
  `pip install mcp==1.28.1`

Under `mcp` 2.0.0 there is no `mcp/server/fastmcp` directory at all, so both raise
`ModuleNotFoundError` and then **advise a downgrade**. Latent today (nothing here has
2.0.0), live the moment anyone installs it.

Also relevant: `setup.sh:280` decides with
`importlib.util.find_spec('$import_name')` — that is *presence*, not version — and
`setup.sh:291` installs the SDK only when `--agents` includes codex, opencode or
copilot. So the pin is partly decorative: a `--agents claude` install never gets it, and
an existing install is never upgraded.

---

## 4. Route comparison

Numbers are measured where stated; everything else is labelled an estimate.

| | **A. SDK v2 bump** | **B. Stdlib transport** | **C. Hybrid (recommended)** | **D. Do nothing** |
| --- | --- | --- | --- | --- |
| **Dependency footprint** | `mcp` 2.x: 62.5 MB / 31 pkgs (measured) | Zero for MCP; still needs `sqlite-vec` for recall | Unchanged now (`mcp` 1.28.1, 61.4 MB / 32 pkgs), 2.x later | Unchanged |
| **Lines of code we own** | ~10 (pin) + ~70 (era probe) + ~45 (wire test) | **~500-600**, of which ~250 is a protocol module (estimate, from the Route A design) | ~250 total across 8 steps, none of it protocol (estimate) | 0 |
| **Conformance risk** | Low — SDK stamps `resultType` (runner.py:387-393), `ttlMs`/`cacheScope` (runner.py:362 + model defaults `_types.py:207,211`), serves both eras (`serve_dual_era_loop`, lowlevel/server.py:711). Verified from v2.0.0 source by two reviewers | **High — refuted, see below** | Low now (era untouched), Low later (inherits A) | We stay pre-2026-07-28 permanently by upstream design |
| **Maintenance burden** | Future revisions = pin bump | Every future revision needs a code change *before we can even talk to* a new client: an unknown version hits our `SUPPORTED` tuple and gets -32022 by design | A's, plus a two-era import and probe carried until every vault reports modern | Zero, until it is not |
| **What breaks if it goes wrong** | Repo says 2.0.0 while every deployed vault still serves 1.x — invisible to CI, visible only in `doctor.sh` | Silently dead stdio server, or silent vault corruption (measured below) | Same as A, but discovered by the wire test before the bump | The day a client ships modern-only *and* declines to probe, the server stops working |
| **Reversibility** | High: re-pin + `pip install`, no code revert (the dual import at `41-49` is the rollback path — and `fastmcp` being absent from the 2.0.0 wheel is what makes it genuine rather than redundant) | Low: it is our code now | High at every step; each step is one commit | n/a |

### Route B is refuted, and it is worth recording why

The stdlib route was designed in full, with care — its error-code table is right, its
`-32602`-for-unknown-tool versus `isError`-for-tool-failure split matches the schema,
it correctly omits the cache fields from `CallToolResult`, and its `-32022` payload uses
the exact field names `data.supported` / `data.requested` where a plausible guess would
have been wrong. It is not rejected for lack of care. It is rejected because it got the
one genuinely hard thing wrong, three times over:

1. **Era modelled as a lexicographic date compare.** The design gated `resultType`,
   `ttlMs` and `cacheScope` on `ver >= "2026-07-28"`. The spec makes era a property of
   how the client *opens* the connection
   (<https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning>). The
   consequence is not cosmetic: the design also advertised
   `supportedVersions: ["2026-07-28", "2025-11-25", "2025-06-18"]`, and the schema tells
   the client to choose from that list — so a modern client that obeys and sends
   `2025-11-25` gets every `server/discover` and `tools/list` back **missing all three
   required fields**, on a connection that never did a handshake. `server/discover` has
   no legacy form at all, so there is no version for which stripping its required fields
   is correct. The v2 SDK keeps `MODERN_PROTOCOL_VERSIONS` and
   `HANDSHAKE_PROTOCOL_VERSIONS` as separate constants (mcp-types version.py:41,53,56)
   for exactly this reason, and builds discovery payloads from the modern set only.
2. **The `initialize` handler jumped an unknown-version client forward.**
   `ctx.legacy_version = want if want in SUPPORTED else LATEST` answers a client
   requesting 2025-03-26 with `2026-07-28`. Measured against real SDK clients: both
   `mcp` 1.9.4 and 1.28.1 raise `RuntimeError: Unsupported protocol version from the
   server: 2026-07-28` (measured 2026-07-30, client-reality reviewer). LM Studio 0.4.6+1
   carries 2024-11-05 / 2025-03-26 / 2025-06-18 and no 2025-11-25, so this is a live
   configuration, not a hypothetical.
3. **Inbound bytes were left in the platform encoding — verified here, both failure
   modes.** The design reconfigured *stdout* to UTF-8 and never touched stdin. Under
   `py -3` on this machine `sys.stdin.encoding` is `cp1252` with `errors=surrogateescape`
   and `utf8_mode=0`. Feeding real UTF-8 through the design's own loop:

   ```
   in : {"params": {"text": "em—dash café"}}      (UTF-8 bytes on the wire)
   out: "emâ€”dash cafÃ©"                          rc=0, no exception
   in : byte 0x81 (undefined in cp1252)
   out: UnicodeEncodeError: 'utf-8' codec can't encode character '\udc81'
        rc=1, empty stdout, server dead mid-session with no JSON-RPC error frame
   ```

   The first case is the dangerous one: silent, rc=0, and `capture_tool` would write
   that mojibake straight into a vault memory file. It is also invisible to the obvious
   test, because `json.dumps` defaults to `ensure_ascii=True` and puts pure-ASCII
   escapes on the wire — the failure only appears when a client emits raw UTF-8, which
   is what Node's `JSON.stringify` (Claude Code, VS Code Copilot) and pydantic's
   `model_dump_json` do. Two lines fix it
   (`io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")`), which is exactly the point:
   the SDK already does this and we would have shipped without it.

Two smaller findings, recorded for completeness: the cancellation set was dead code that
could only misfire (single-threaded dispatch means a `notifications/cancelled` can only
be read *after* the response it targets was written and flushed) and it grew without
bound; and `-32600` errors returned `id: null` even when the request carried a usable id,
which is JSON-RPC-legal but costs a client a full timeout instead of an immediate error.

**Route D is not a resting place either.** `mcp` 1.29.0 was published
2026-07-28T13:41:40Z, four minutes *before* 2.0.0, so the 1.x line is actively
maintained — but grepping the 1.29.0 wheel for `server/discover`, `resultType`, `ttlMs`,
`cacheScope` and the literal `2026-07-28` returns **zero hits in any `.py` file**, and
`mcp/types.py` still reads `LATEST_PROTOCOL_VERSION = "2025-11-25"` (measured
2026-07-30, maintenance reviewer). Upstream chose a hard generational split. So "stay on
1.x" means permanently pre-2026-07-28 by upstream design. Route D is the correct
*present* posture and the wrong *permanent* one, which is precisely why Route C stages
it instead of choosing.

---

## 5. Recommended plan

Eight steps. Each is independently shippable, testable and revertible. Ordered so no
existing client breaks at any point, and so the two steps with the highest present-day
value come first.

**Invariant that survives every step:** the eight `*_tool()` functions stay at module
scope, importable and callable with no `mcp` package installed. No step may move logic
into a decorated closure inside `build_server()`. `tests/test_kb_mcp.py` and
`tests/test_mcp_capture.py` exercise them with no SDK involved; that must remain true
after every step.

Gate for every step: `python -m pytest tests -q`. Not `unittest discover` — it misses
the function-style tests in this suite.

---

### Step 1 — Tool annotations on all eight tools, and kill the blind guard

**Changes.** `scripts/kb-mcp.py`: beside the SDK import at `41-49`, add
`try: from mcp.types import ToolAnnotations / except Exception: ToolAnnotations = None`
plus a two-line `_ann(**kw)` helper returning `ToolAnnotations(**kw)` or `None`, so the
module stays importable without the package. Pass `annotations=_ann(...)` on all eight
`@srv.tool()` calls (`283-331`). Replace `tests/test_kb_mcp.py:69`.

Field names verified against schema.ts for this revision and against both installed SDKs
(verified here): `title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`,
`openWorldHint` — nothing else exists.

| Tool | Annotations | Earned how |
| --- | --- | --- |
| `recall`, `review_pending`, `what_did_i_do`, `timeline`, `weeklog`, `topic_timeline` | `readOnlyHint=True, openWorldHint=False` | No writes on any path. `openWorldHint=False` is not a judgement call — schema.ts uses "a memory tool" as its own example of a closed world |
| `capture` | `readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False` | Only ever creates a *new* unverified file; `_memory.write` never overwrites, and there is deliberately no write-time reconcile, so two identical calls make two memories |
| `review_decide` | `readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False` | `_memory.decide` flips an existing memory's status and `_memory.py:402` then refuses anything no longer `unverified` with a 409 — irreversible through this tool. `idempotentHint=False` is earned too: `skip` writes no file change but appends a row to `memory-review-log.jsonl` on every call |

Put the human-readable label in `annotations.title`, **not** the `title=` kwarg:
`tool()` on the ambient `python`'s mcp 1.9.4 takes `(name, description, annotations)`
only (verified here), so `title=` would raise `TypeError` there, while schema.ts makes
display precedence `title`, `annotations.title`, `name` — so `annotations.title` is
honoured everywhere and cannot fail.

**Why first.** This is the only measured present-day defect on the surface, and it is
read by every client that could be inspected: `readOnlyHint` appears 24× in Claude Code,
26× in Copilot CLI, 2× in VS Code, 1× in LM Studio (measured 2026-07-30, client-reality
reviewer). Claude Code defaults both `isReadOnly()` and `isConcurrencySafe()` to false
when annotations are absent, so six read-only tools are prompting and serialising today.
Honest limit: annotations are hints, and clients are explicitly told not to make tool-use
decisions based on annotations from untrusted servers
(<https://modelcontextprotocol.io/specification/2026-07-28/server/tools>). This improves
confirmation UX and parallelism; it enforces nothing.

**Risk.** Low. The kwarg is accepted on both installed SDKs and on v2. Residual risk is
semantic drift — an annotation that stops being true is worse than none — which is what
the assertion below is for.

**Verify.** `python -m pytest tests/test_kb_mcp.py -q`. New test builds the server with
a stub SDK and asserts the exact annotation dict per tool name. Replace
`test_build_server_none_without_mcp` with one that asserts the eight tools register and
carry their annotations, so it can actually fail.

**~35 lines** + ~25 in tests.

---

### Step 2 — Truth-fix pass: the Copilot resources claim and the tool count

**Changes.** `scripts/kb-mcp.py:18-20` and `:244` — remove "GitHub Copilot ondersteunt
GEEN MCP-resources". `README.md:632` — same claim in English; replace with the accurate
nuance (both Copilot surfaces call `resources/list`, `resources/read` and
`resources/templates/list`; VS Code surfaces resources as user-attached context rather
than model-callable, so keep the `.github/copilot-instructions.md` block).
`README.md:534` and `docs/agent-integrations.md` — "seven primitives: six tools" → eight
tools plus one resource.

**Why.** Docs-only, but not cosmetic: that false claim is the stated justification for
the `instructions=` work in step 4. Fixing it first forces step 4 to be justified on its
real merits, and stops the next person building on a premise that does not hold. Per repo
language policy these stay English.

**Risk.** Low. `tests/test_docs_consistency.py:89-96` counts `def {name}_tool(` and
forbids the phrase "three primitives" / "drie primitieven" (verified here) — it does
**not** assert the mcp pin, so most of the drift in §3 is ungated and must be re-grepped
rather than trusted to CI.

**Verify.** `python -m pytest tests/test_docs_consistency.py tests/test_integration_documentation.py -q`.
Then `grep -rn -i "not MCP resources\|geen MCP-resources\|seven primitives" . | grep -v __pycache__`
returns nothing.

**~15 lines** across four files.

---

### Step 3 — Four temporal tools return dicts, so `structuredContent` comes free

**Changes.** `scripts/kb-mcp.py`: change `what_did_i_do_tool`, `timeline_tool`,
`weeklog_tool`, `topic_timeline_tool` and `_activity_unavailable` from `-> str` to
`-> dict[str, Any]`; return `activity.*()` directly; delete `_activity_json` (`177-178`)
and its call sites. Mirror the annotation on the four `@srv.tool()` wrappers. Do **not**
pass `structured_output=` — the kwarg does not exist on mcp 1.9.4 (verified here) and
would raise `TypeError` there; rely on return-annotation auto-detection.

`dict[str, Any]` specifically: `func_metadata._try_create_model_and_schema` routes a
`dict` with `str` keys through `_create_dict_model` (a RootModel) with
`wrap_output=False`. Any other generic return type gets silently wrapped in
`{"result": …}`, adding a level to every payload.

**Why it is free.** The four functions already build dicts and JSON-encode them at the
MCP seam. The SDK's `_convert_to_content` produces a **byte-identical** string —
measured with Dutch non-ASCII content: identical, same length, no `\uXXXX` escaping
(measured 2026-07-30, tool-surface design task, re-confirmed by the maintenance
reviewer). So `content` does not change by one byte, no client regresses, no token cost
is added — and 1.28.1 and 2.0.0 additionally emit `structuredContent` plus a derived
`outputSchema`. On 1.9.4 there is no structured output and the dict serialises to the
same text. Graceful degradation with no version probe and no branching. `structuredContent`
is read by all four inspectable clients (49× Claude Code, 24× Copilot CLI, 12× VS Code,
2× LM Studio; `outputSchema` 88× in Claude Code — measured 2026-07-30, client-reality
reviewer).

**Risk.** Medium, concentrated in one known place: `tests/test_kb_mcp.py:178-184`
(`test_temporal_tool_wrappers_return_json`) calls `json.loads()` on all four return
values (verified here) and will raise `TypeError` on a dict. That is the migration cost,
it is two lines per assertion, and it is a *good* break — the test name encodes the old
contract.

**Verify.** Rewrite that test to assert on the dicts and rename it
`test_temporal_tool_wrappers_return_dicts`. Add one assertion pinning the byte-identity
claim: `content` equals `json.dumps(payload, indent=2, ensure_ascii=False)`. Then
`python -m pytest tests -q`.

**~30 lines** changed, ~10 in tests.

---

### Step 4 — `instructions=` on the constructor, keeping both other carriers

**Change.** `MCPServer("kennisbank-geheugen", instructions=INSTRUCTIONS_TEXT)` at
`kb-mcp.py:281`. Add nothing else, remove nothing: the `kennisbank://instructions`
resource at `340-345` stays, and the managed block in `.github/copilot-instructions.md`
stays.

`instructions` is accepted by `__init__` on mcp 1.9.4, 1.28.1 and 2.0.0 (verified here on
the first two). Same kwarg, different envelope per era: `InitializeResult.instructions`
on 1.x, `DiscoverResult.instructions` on 2.x
(<https://modelcontextprotocol.io/specification/2026-07-28/server/discover>).

**Why, honestly.** This is a one-line improvement with a real but *bounded* payoff, and
the bound must be stated because step 2 just removed the reason it was originally
proposed:

- **VS Code 1.130.0** captures `InitializeResult.instructions` into `serverInstructions`
  and builds `{type:"mcp", serverLabel, instructions}` for chat, with no allowlist
  observed. Capture and plumbing verified; whether it reaches the final prompt text is
  **not established** (measured 2026-07-30, client-reality reviewer).
- **Copilot CLI 1.0.70** *discards* third-party server instructions by default. It gates
  them behind an allowlist that resolves to GitHub's own servers
  (`github-mcp-server`, `bluebird`, `computer-use`); non-allowlisted servers land in
  `deferredServerInstructions`. Opt-in flag: `--allow-all-mcp-server-instructions`
  (measured 2026-07-30, client-reality reviewer).
- **`DiscoverResult.instructions` is unreachable today.** The string `server/discover`
  appears **zero** times in all five inspected clients, so that envelope is never
  requested.

**So the duplication into `.github/copilot-instructions.md` cannot be retired.** That is
the honest answer to the question §6 asks, and it is a reversal of the earlier version of
this plan.

**Risk.** Low, purely additive. Document the `--allow-all-mcp-server-instructions` flag
in `docs/agent-integrations.md` as the Copilot CLI opt-in.

**Verify.** `python -m pytest tests/test_kb_mcp.py -q` asserts the constructor receives
the instructions text and the resource is still registered.

**~5 lines** + ~8 lines of docs.

---

### Step 5 — Make `recall` and `review_pending` output followable

**Changes.** In `recall_tool` (`kb-mcp.py:83-106`), add
`from _vaultpath import vault_root` (ADR-0002; the module currently only sets the env
var) and put the vault-relative path into each hit line, with the vault root stated once
in the header:

```
KennisBank hits (vault: <root>):
- [memory] [[stem|title]] (0.90) 09-memory/2026-07-12-foo.md: snippet…
```

Keep the `[[stem|title]]` wikilink — additive, and Obsidian readers use it. In
`review_pending_tool` (`125-139`), render the identifier as `stem=<x>` instead of a bare
`[[stem]]`, because that string is the exact argument `review_decide` requires. Leave
`capture_tool` alone; it already names the file.

**Why.** This is the one real defect in the output. `recall` is the core tool of a
retrieval-first system and it returns an Obsidian wikilink that an agent in Codex,
Copilot, LM Studio or Cline cannot resolve to anything it can open — the most important
tool dead-ends. Path derivation must be fail-soft: a hit outside the vault or an
unreadable path falls back to the raw value rather than raising.

**Explicitly rejected: giving `recall` a dict return / `structuredContent`.** The SDK
derives `content` and `structuredContent` from the *same* return value, so returning a
dict would replace the compact curated block with pretty-printed JSON in `content` —
roughly doubling tokens on the hot path (north star 1) to buy machine-readability that
nothing on the MCP path consumes. Atlas reads the vault directly; the only consumer here
is an LLM, and an LLM reads a text line more cheaply than a JSON object. Same reasoning
for `review_pending`: the failure mode is the model passing a title where a stem is
required, and the cure is to label the field, not restructure the envelope. This is why
step 3 is scoped to the four tools that *already* build dicts.

**Risk.** Medium. `tests/test_kb_mcp.py::test_recall_tool_formats_hits` asserts on the
rendered string and must be extended. The separate hook-path renderer in `kb-retrieve.py`
has its own format and must **not** be touched.

**Verify.** `python -m pytest tests -q` with the format assertion extended to require the
relative-path substring. Then one manual `recall` through a real client, confirming the
returned path opens with that client's own file-read tool — that is the property being
bought.

**~20 lines.**

---

### Step 6 — Era-agnostic SDK probe, reporting interpreter + version + era

**Changes.** New `scripts/_mcp_probe.py` exposing `probe() -> (era, version) | None`
that accepts either generation. Replace the hardcoded `dep_check` at
`install-agent-envs.py:790` and the identical import at `doctor.sh:297` with a call to
it, and update the remediation strings at `install-agent-envs.py:808` and
`doctor.sh:302`. Update `tests/test_agent_envs_install.py:273`, which asserts the literal
`"pip install mcp==1.28.1"`.

Report **the resolved interpreter path, the mcp version and the era together** — not era
alone. The interpreter is the thing that actually diverged here (§3: 3.12.9/1.9.4 versus
3.14.2/1.28.1), and an era-only line would not have surfaced it.

```python
# scripts/_mcp_probe.py — one place that knows which SDK generation is installed.
"""Report the installed MCP SDK generation, or exit 1 when there is none.

v2 renamed mcp.server.fastmcp -> mcp.server.mcpserver. A gate that imports one
fixed path fails on the other generation and then advises the wrong pin, so we
accept EITHER and name what we found.
"""
import importlib.util as u
import sys


def _has(mod: str) -> bool:
    try:
        return u.find_spec(mod) is not None
    except Exception:
        return False


def probe():
    """('modern'|'legacy', version) for the installed SDK, else None."""
    if not _has("mcp") or not _has("mcp.client.stdio"):
        return None
    if _has("mcp.server.mcpserver"):
        era = "modern"          # v2.x: serves 2026-07-28 and the legacy era
    elif _has("mcp.server.fastmcp"):
        era = "legacy"          # v1.x: LATEST_PROTOCOL_VERSION == 2025-11-25
    else:
        return None
    try:
        from importlib.metadata import version
        return era, version("mcp")
    except Exception:
        return era, "unknown"


if __name__ == "__main__":
    got = probe()
    if got is None:
        sys.stderr.write("no usable MCP SDK for this interpreter\n")
        sys.exit(1)
    print(f"{got[0]} mcp=={got[1]} interpreter={sys.executable}")
```

**Deliberately *not* in this step:** making `setup.sh:280` version-aware, and widening
`setup.sh:291` to install the SDK for every agent selection. Both belong to step 8,
because both change install behaviour and only matter once the pin moves. Keeping them
out is what lets step 6 claim, truthfully, that it changes no behaviour at all.

**Why.** This is the prerequisite that makes step 8 safe, and it is the only signal that
will ever reflect the *deployed* reality rather than the repo's. State it accurately in
the ADR: a prerequisite, not a bug fix — nothing fails today, because both interpreters
here have 1.x. Writing it as a *swap* to `mcp.server.mcpserver` instead of an
either-check would just mirror the bug onto every vault still on 1.28.1, which is the
per-bullet-update pattern CLAUDE.md flags from PR #54.

**Risk.** Medium — the mirror-image regression above. The test must assert **both**
directions (modern-only present, legacy-only present, neither). Note
`find_spec("mcp.server.mcpserver")` imports the parent `mcp.server`, costing a full SDK
import (~2.7 s, measured 2026-07-30, SDK-v2 design task) — but the old `dep_check`
already fully imported `mcp.server.fastmcp`, so this is not a regression.

**Verify.** `python -m pytest tests/test_agent_envs_install.py tests/test_copilot_doctor.py -q`.
Then run the probe under both interpreters and confirm each names itself correctly:
`python scripts/_mcp_probe.py` → `legacy mcp==1.9.4 interpreter=…`, and
`py -3 scripts/_mcp_probe.py` → `legacy mcp==1.28.1 interpreter=…`. Then
`bash scripts/doctor.sh` shows the three-part line.

**~70 lines** (new file ~35, two call sites ~18, tests ~25).

---

### Step 7 — Wire-level conformance harness on the current pin

**Changes.** New `tests/test_mcp_wire.py`. Spawn `scripts/kb-mcp.py` as a subprocess,
speak raw newline-delimited JSON-RPC over stdin/stdout, and assert the **legacy** era on
the pin we already have: `initialize` → `tools/list` returns exactly the eight expected
names in registration order → `tools/call` on `review_pending` returns text. Skip
cleanly when `mcp` is not importable.

Three assertions that no in-process test can make:

1. **Stdout purity.** Every non-empty stdout line parses as JSON-RPC; no line contains
   `\r`; the whole stream decodes as UTF-8. This catches a stray `print()` introduced in
   *any* transitively imported module years from now, including at import time. Negative
   control: temporarily add `print("boom")` to `scripts/_rank.py` and confirm the test
   fails — a guard that has never failed is a guard you have not tested (the ADR-0002
   column-0 regex lesson).
2. **UTF-8 round-trip.** Feed a `capture` call whose body contains real UTF-8 non-ASCII
   (`ensure_ascii=False`) plus one 0x81 byte; assert the written memory's codepoints
   round-trip and the process survives. This is the exact failure verified in §4, and it
   is the assertion that would have caught it.
3. **No Ollama dependency.** Use `review_pending` for the `tools/call` shape assertion,
   never `recall` — `recall_tool` calls `emb.embed()` first and would block on the
   embedding path. Give the subprocess a hard timeout so a hung server fails the suite
   instead of hanging CI (cold boot measured 3.1-5.5 s under v2).

**Why before the pin bump.** This is the instrument that will *prove* step 8 rather than
assume it, and building it against the version we already run means a failure in step 8 is
unambiguously caused by step 8. It also replaces an assertion about the SDK with an
assertion about our server. One cautionary note carried from review: the SDK-v2 design's
own wire test was never executed in the form presented — it contained an undefined name
inside the untaken branch of an `... if False else ...` expression, which Python does not
evaluate. Run this one before citing it.

**Risk.** Low-medium. Needs a hermetic tmp vault via `KENNISBANK_VAULT`.

**Verify.** `python -m pytest tests/test_mcp_wire.py -q` under `py -3` (1.28.1) and under
`python` (1.9.4); then the full gate.

**~60 lines.**

---

### Step 8 — [GATED] Pin bump, modern-era assertions, ADR

**Do not start this step until the gate in §1 is met.**

**Changes.** `requirements.txt:2` `mcp==1.28.1` → `mcp>=2.0.1,<3`, and `setup.sh:291`
likewise. Two install-behaviour changes carried here from step 6, because without them the
pin move is cosmetic: make `setup.sh:280` compare the *installed version* against the spec
rather than merely checking `find_spec` presence, and widen `setup.sh:291` to install the
SDK whenever `kb-mcp.py` is registered for any agent rather than only for
codex/opencode/copilot (today a `--agents claude` install never gets it, so `kb-mcp.py`
cannot run at all on that machine). Also align the two remediation strings TASK-101 added in
`main()` (`kb-mcp.py:355,360`), which currently advise `mcp>=2.0.0,<3`, to the D4 pin
`>=2.0.1,<3` — an error message that advises an ungated 2.0.0 contradicts §1's gate. Then
extend step 7's harness with the modern era on the same executable:
`server/discover` returns `supportedVersions == ["2026-07-28"]`, `resultType ==
"complete"`, and `ttlMs`/`cacheScope` present; `tools/list` and `resources/read` carry
the cache fields; `tools/call` does **not** (`CallToolResult extends Result` only);
`tools/list` order equals registration order; and the **legacy** assertions from step 7
still pass against the same binary — that pair is the dual-era proof. Skip the modern half
via `find_spec("mcp.server.mcpserver")` so the suite stays green on 1.x and with no SDK.

**The pinning decision, and why it is a floor-and-ceiling rather than `==`.** The repo
style is exact pins, and exactness has a real argument here: there is no lockfile, so a
floating pin gives different vaults different SDKs, and upstream already freezes the wire
types with `mcp-types==2.0.0`. Against that: the 1.x line receives security fixes only
while every fresh `pip install mcp` lands on 2.x anyway, and we specifically want the
first patch release. `>=2.0.1,<3` encodes both facts — never 2.0.0 (no post-GA patch
cycle), never 3.x (unknown breakage) — and it is the one form that states *why* in its
own syntax. Record that in the ADR so the next person does not tidy it back to `==`.

**Keep the dual import at `kb-mcp.py:41-63`.** It is the rollback path, and `fastmcp`
being absent from the 2.0.0 wheel is what makes it genuine rather than redundant
redundancy. Also keep the `_server_kwargs()` discipline if `version=`/`cache_hints=` are
ever adopted: introspect `inspect.signature(MCPServer.__init__)` rather than guessing the
era, because both are accepted on **neither** installed SDK (verified here).

**Explicitly out of scope: auto-upgrading the user's Python environment.** `setup.sh`'s
`install_python_dep` skips any package that already imports, so this step changes git and
not a single deployed vault. The fix — running `pip install` against the resolved
interpreter — mutates the user's environment and belongs behind the same
`kennisbank-settings.json` opt-in as the other background automation, not inside
`setup.sh`. Until that exists, treat "requirements.txt says 2.x" as **necessary and not
sufficient**, and let `doctor.sh`'s three-part line from step 6 be the authority on what a
machine actually serves.

**ADR.** Short record under `docs/adr/` (next free number after ADR-007) capturing four
durable choices: the SDK owns protocol conformance and we write no wire code; the two-era
import is retained deliberately until every vault reports modern, with an explicit
retirement condition; the pin form and why; and the rejection of the stdlib route with the
three refutations from §4 so nobody re-litigates it from scratch.

**Risk.** Medium — this is the one step that changes wire behaviour. Rollback rehearsal
belongs *in* the step: re-pin to 1.28.1, `pip install`, re-run steps 6 and 7, and confirm
both go green with `era=legacy` and no code revert. Cost measured: spawn → `tools/list`
went 1616 ms → 3075 ms (min of 5; medians 2217 → 3172 ms), i.e. **~+0.95 s once per
client session**; a warm process answers successive `tools/list` calls in 4.2-6.2 ms
(measured 2026-07-30, SDK-v2 design task). The recall hot path is unaffected; what
regresses is client startup.

**Verify.** Full gate, then both halves of the harness against the v2 interpreter, then
the installer's embedded client validator (`install-agent-envs.py:822-850`, which uses
`ClientSession` / `StdioServerParameters` / `stdio_client` / `session.initialize()` — all
still exported at v2.0.0) must still report the handshake OK. Then the manual smoke pass
in §8. Then the release order: suite green → push → PR → process the Copilot review →
merge → `git fetch` and confirm `origin/main` contains the commits → tag that SHA.

**~15 lines** of pin/config + ~45 in tests + ~60 lines of ADR prose.

---

## 6. Tool surface

Latency classes: **instant** = deterministic SQL/file read, no model call; **seconds** =
one local embedding call; **minutes** = LLM work per item.

### The eight current tools — all keep, five refine, none drop

| Tool | Backing | Read-only | Latency | Verdict |
| --- | --- | --- | --- | --- |
| `recall` | `kb-mcp.py:83` → `kb-recall.py:recall_hits` | yes | seconds | **Refine** (step 5: vault-relative path). Core capability. Verified pure — no INSERT/UPDATE/commit in `kb-recall.py`, and `_embeddings.embed()` writes nothing |
| `capture` | `kb-mcp.py:109` → `_memory.write` | no | instant | **Keep.** The only agent write path; lands `unverified`/`agent` so a human or the sweep promotes it |
| `review_pending` | `kb-mcp.py:140` → `_memory.pending_reviews` | yes | instant | **Refine** (step 5: `stem=` label). Frontmatter scan; presents the human's decision queue |
| `review_decide` | `kb-mcp.py:157` → `_memory.decide` | no | instant | **Keep.** Executes one human decision. Stays because the human is in the conversation, not because the agent may decide |
| `what_did_i_do` | `kb-mcp.py:189` → `_activity.what_did_i_do` | yes¹ | instant | **Refine** (step 3: dict return) |
| `timeline` | `kb-mcp.py:206` → `_activity.timeline` | yes¹ | instant | **Refine** (step 3) |
| `weeklog` | `kb-mcp.py:223` → `_activity.weeklog` | yes¹ | instant | **Refine** (step 3) |
| `topic_timeline` | `kb-mcp.py:240` → `_activity.topic_timeline` | yes¹ | instant | **Refine** (step 3) |
| `kennisbank://instructions` (resource) | `kb-mcp.py:340` | yes | instant | **Keep.** Step 4 adds `instructions=` *alongside* it, never instead of it |

¹ Read-only under default settings, not unconditionally: with `activity_llm_fallback`
enabled (default off) an unparseable period falls through to a local-Ollama call that
writes a `temporal_llm_cache` row and an audit line. Caches and audit, never vault
knowledge — but the `readOnlyHint` in step 1 should carry a comment saying so.

**Consolidating the four temporal tools into one `activity_recall` is explicitly
rejected.** They share parameters and index and compete during selection, so on KISS
grounds one tool would be better design. But merging would break shipped client
configurations for a cosmetic win, and backward compatibility outranks tidiness. Recorded
so a future clean-slate surface does not repeat the pattern.

### Add now: nothing

**Zero new tools.** This is a deliberate finding, not an omission, and it reverses the
earlier version of this plan (which proposed `read_note` and `orientation`).

The whole near-term value here is **metadata and output quality, not surface area**:
annotations that six read-only tools do not currently carry, `structuredContent` that
comes free from a type annotation, and a `recall` line an agent can actually follow. All
three make the existing eight tools better for every client. A ninth tool makes tool
selection harder for every client.

### Defer, each with the trigger that would promote it

| Candidate | Why deferred, and what would change my mind |
| --- | --- |
| `read_note` (whole-document read over the `docs` table) | The argument is real: `recall` returns a wikilink plus a ~280-char snippet, and a client without filesystem access cannot open it. But **step 5 discharges most of that argument** — a vault-relative path is followable by every client that can read a file, which is Claude Code, Codex, Copilot CLI and VS Code. What remains is clients that speak MCP but cannot read the filesystem, and **which clients those are is not established** (Cline, Windsurf and Claude Desktop are not installed here). *This is a considered departure from the reviewers' steer, which was that `read_note` survives if its argument is stated — I think step 5 weakens the argument enough to defer.* **Trigger:** establish that a client actually in use lacks filesystem read. Then build it, with mandatory input validation (resolve only via the `docs` table or a `vault_root()`-anchored path, reject anything escaping the vault, cap the body with an explicit truncation notice — the spec requires "Servers MUST: Validate all tool inputs", <https://modelcontextprotocol.io/specification/2026-07-28/server/tools>) |
| `capture(source_session=…, tags=…)` | Cheap and strictly additive — `_memory.render()` already accepts both and emits `source_session:` into frontmatter — and it closes a real gap: agent captures arrive `unverified` **and** unsourced, so the one class a human must adjudicate is the one class with no traceable origin. **Trigger:** verify that a client can supply a stable session identifier at capture time. Unverified today, and a parameter the model fills with a guess is worse than no parameter |
| `orientation` | Wraps `kb-orientation.py` to give hookless clients the SessionStart summary. Weakest of the three: it duplicates a coordinator that Claude Code, Codex and Copilot CLI already have, for clients whose revisions are not established. **Trigger:** a client in regular use that starts blind and where the missing orientation is observed to cost something |
| `structuredContent`/`outputSchema` for `recall` | **Rejected**, not deferred — see step 5. Doubles hot-path tokens for a consumer that does not exist |
| `mark_noise` | Strictly downstream of a telemetry gap. `_usage.log_injected` fires only in the Claude-only prompt hook (`kb-retrieve.py:405-411`); on the MCP path nothing is recorded as injected, so a noise mark would count against zero injections and the ratio is meaningless. Sequence after MCP recalls are logged |
| `log_session` / `checkpoint_*` | Genuine holes but not wrappers — they need design decisions first (where agent-authored logs land, whether `kb-lint` provenance may cite them, interaction with the `.swept`/`.distilled` watermarks). A quick MCP write here would manufacture unsourced "raw" material, which is exactly what `kb-lint` exists to prevent |

### Skip — do not build

- `search` / `find_similar` / `presearch` — same query, same index, marginally different
  filter. Each near-synonym degrades tool selection for every client.
- `vault_health` as a tool — the one agent-relevant fact (index freshness, pending count)
  belongs as a line inside a future `orientation`, not a second mechanism.
- `rebuild_index` / `build_embed_index` / `build_activity_index` — already detached off
  the hot path by `index-launch.py` precisely because inline runs cost minutes. A callable
  tool that blocks for minutes is the anti-pattern north star 1 forbids.

### The human-only boundary, and why it sits there

Slash commands and skills keep everything with one of three properties:

1. **Minutes of LLM work, or it rewrites human-owned articles.** `/wiki`, `/destilleer`,
   `/kennisbank:rebuild-memory`, `/stale`, `/reconcile`. The human is editor-in-chief; the
   agent's legitimate route is `capture` → `unverified` → human or judge promotion.
2. **The invocation is itself a decision only the human can make.** `/import`, `/intake`
   (which export, whether to OCR — privacy and scope), `/kennisbank:settings` (an agent
   silently flipping `memory_capture` off would stop the automation invisibly for weeks,
   this repo's known failure mode), install/upgrade/release, and `kb-ask.py` — whose
   entire purpose is that the *human* is the gate to a cloud agent, so exposing it over
   MCP would blur the sovereignty boundary the server exists to hold.
3. **It is operator plumbing, not knowledge.** Index and graph builders, evals,
   calibration. These already reach the agent implicitly — the graph arrives as a recall
   neighbour entry — so exposing the builders would expose plumbing, not capability.

Everything on the MCP surface is the complement: instant-or-seconds, read-mostly, and
answers a question the agent is holding right now.

One honesty note on `review_decide`: its "only after the user explicitly decided" contract
is enforced by prose alone. Annotations are hints and clients are told to treat them as
untrusted, so no server-side metadata can enforce human consent. The real guard is the
client's human-in-the-loop confirmation. Stated so it is not mistaken for an oversight.

### `DiscoverResult.instructions` — the honest answer

It is the protocol-level home for the pull-nudge, it costs one line (step 4), and **it is
unreachable today**: `server/discover` appears zero times in all five inspected clients.
On the legacy envelope the picture is mixed — VS Code captures it (whether it reaches the
prompt is **not established**), Copilot CLI discards it for third-party servers unless
launched with `--allow-all-mcp-server-instructions`. Conclusion: adopt `instructions=`
because it is one line and additive, **keep both other carriers**, and do not claim the
protocol field replaces the duplication.

**Surface delta: 8 tools + 1 resource → 8 tools + 1 resource.** Five tools refined, all
eight annotated, four gaining `structuredContent`, one nudge carrier added. Nothing added,
nothing removed, nothing renamed.

---

## 7. Deprecated features and extensions

### Deprecated — did we ever use it?

| Feature | Used? | Evidence | Action |
| --- | --- | --- | --- |
| **Roots** | No | No `roots/list`, no `notifications/roots/list_changed` anywhere in `scripts/`. The vault path arrives via `KENNISBANK_VAULT` (`kb-mcp.py:38`) and per-client `env` blocks — which *is* the spec's suggested migration | None. Do not adopt |
| **Sampling** | No | No `sampling/createMessage`. LLM calls go direct to local Ollama via `_llm`/`_embeddings` — also the suggested migration | None. Do not adopt |
| **Logging (MCP utility)** | No | No `logging/setLevel`, no `notifications/message`. We write to stderr (`kb-mcp.py:355,360`) | None — and the sanctioned migration for stdio is literally "log to stderr", which is already what we do |
| **HTTP+SSE transport** | No | `srv.run()` at `kb-mcp.py:366` takes no `transport=`; default is stdio; no `mcp.server.sse` import; no socket/bind/listen/host/port in the file | None. Sovereignty forbids it anyway |
| **OAuth Dynamic Client Registration** | No | No authorization code at all | None |
| **`ping`** | n/a — **removed**, not deprecated | We never call it; the SDK answers it | None under the SDK route. Noted because if we ever owned the transport, answering `ping` anyway is two lines of legacy keepalive insurance: some older clients tear a connection down when a keepalive gets -32601 |
| **`logging/setLevel`** | No | Removed in this revision. Never used | None |
| **`notifications/roots/list_changed`** | No | Removed. Never used | None |
| **`resources/subscribe` / `unsubscribe`** | No | Replaced by `subscriptions/listen` (opt-in stream). Our single resource is a module-level constant that cannot change while the process lives, so there is nothing to subscribe to | None. Do not declare `resources.subscribe` |
| **Per-request `io.modelcontextprotocol/logLevel`** | No | `@deprecated` on arrival (SEP-2577). We neither read it nor emit `notifications/message`, which satisfies "servers MUST NOT emit `notifications/message` for requests that did not include that field" vacuously | None |

**Total action from the entire deprecation list: zero code changes.** The only thing worth
writing down is the negative rule: none of these may be adopted later without revisiting
this section, because "new implementations SHOULD NOT adopt" a Deprecated feature
(<https://modelcontextprotocol.io/specification/2026-07-28/deprecated>).

One reported inconsistency, not resolved: schema.ts marks
`io.modelcontextprotocol/logLevel` `@deprecated … (SEP-2577)` while the `_meta`
reserved-keys table on `/specification/2026-07-28/basic` lists it with no deprecation
marker. Irrelevant to us; the two pages do literally disagree.

### Extensions — adopt / defer / skip

Ground rule: "Extensions are always disabled by default and require explicit opt-in from
the developer" (<https://modelcontextprotocol.io/extensions/overview>). Declining all of
them is fully conformant. The `extensions` field is new on both `ClientCapabilities` and
`ServerCapabilities`; we leave it absent.

| Extension | Decision | Reason |
| --- | --- | --- |
| **Tasks** (`io.modelcontextprotocol/tasks`) | **Skip** | Moved out of core into an official extension in this revision (polling via `tasks/get`, client-to-server input via `tasks/update`, `tasks/list` **removed**, servers may return task handles unsolicited). But it solves a problem we do not have: every tool on our surface is instant or sub-second by design, and the minutes-long operations are deliberately human-driven or already detached off the hot path (§6). Adopting Tasks to make them callable would invert north star 1. Two supporting facts: the Python SDK does not ship it, and Codex 0.145.0 still implements the *removed* `tasks/list` (measured 2026-07-30, client-reality reviewer) — the extension is in flux client-side |
| **MCP Apps** (`io.modelcontextprotocol/ui`) | **Skip** | Inline interactive HTML in the conversation. **We already have a viewer**: Atlas is a Tauri desktop app with seven lenses over the same vault (ADR-0004). Building a second, weaker viewer inside two chat clients — HTML we would design, host inline, and keep in sync with Atlas — is textbook surface without demonstrated need. If vault visualisation is the goal, invest in Atlas |
| **Skills over MCP** | **Skip — nothing to adopt yet** | No specification exists. It is a *Working Group charter* (<https://modelcontextprotocol.io/community/working-groups/skills-over-mcp>), absent from the official extension list and the client matrix, with no extension identifier to declare. Separately, this repo's `skills/kennisbank-*` are Anthropic Agent-Skill `SKILL.md` files on the filesystem, not an MCP feature, and they stay that way (§6, human-only boundary). Revisit when the working group produces an Extensions-Track SEP with a reference SDK implementation, which is a documented prerequisite for official status |
| **OAuth Client Credentials / Enterprise-Managed Authorization** | **Skip** | Machine-to-machine and enterprise IdP auth for networked servers. A local stdio server has no auth surface, and adding one would be a sovereignty regression, not a feature |
| **MRTR / `InputRequiredResult`** (core, not an extension) | **Skip** | No tool needs mid-call input. For `review_decide` this is a design invariant rather than a shortcut: TASK-89 requires the human to have decided *before* the call, so implementing MRTR would create exactly the path the design forbids — an agent soliciting a review decision from inside a tool call |

**Net: adopt nothing.** The honest summary is that the extension ecosystem currently offers
this project one thing it might want — a richer viewer — and we already built a better
version of it outside MCP.

---

## 8. Verification

### Principle

CI checks behaviour; it does not check whether a guard covers what it claims. This repo's
own PR #54 lesson applies directly, because we already have such a guard:
`tests/test_kb_mcp.py:69` passes whether or not the SDK is installed and whether or not
the server works (verified here). Every conformance claim in this plan must be proved on
the wire instead.

### Tests to add, by step

| Step | Test | Proves |
| --- | --- | --- |
| 1 | Exact annotation dict per tool name, built against a stub SDK | The six read-only tools actually carry `readOnlyHint`; the hints stay true when behaviour changes |
| 1 | Replacement for `test_build_server_none_without_mcp`: eight tools register and carry annotations | The blind guard is gone |
| 1, all | The eight `*_tool()` functions remain importable and callable with `mcp` absent | The standing constraint from `kb-mcp.py:27-30` |
| 2 | `grep` for the false Copilot-resources claim and the stale primitive count returns nothing | Docs drift closed; note `test_docs_consistency.py` does **not** gate the pin, so re-grep rather than trust CI |
| 3 | `test_temporal_tool_wrappers_return_dicts` — the four return dicts; `content` equals `json.dumps(payload, indent=2, ensure_ascii=False)` | `structuredContent` is free *and* byte-identical, so no client regresses |
| 4 | Constructor receives `instructions=`; the resource is still registered | Additive, not a replacement |
| 5 | `recall` output contains the vault-relative path; `review_pending` renders `stem=`; a hit outside the vault falls back rather than raising | The core tool stops dead-ending; fail-soft holds |
| 6 | Probe under all three states: modern-only present, legacy-only present, neither | No mirror-image regression onto vaults still on 1.x |
| 7 | **Stdout purity** — every stdout line parses as JSON-RPC, no `\r`, valid UTF-8. Negative control: inject `print("boom")` into `scripts/_rank.py` and confirm the test fails | The import-time window is ours; catches a stray print in any transitively imported module, forever |
| 7 | **UTF-8 round-trip** — `capture` with real UTF-8 non-ASCII plus one 0x81 byte; codepoints round-trip, process survives | The exact §4 failure; the only assertion that would have caught it |
| 7 | Legacy era on the current pin: `initialize` → eight named tools in registration order → `tools/call review_pending` | The wire actually works, on the SDK we run |
| 8 | Modern era on the same executable: `supportedVersions == ["2026-07-28"]`, `resultType == "complete"`, cache fields on the six cacheable results and **absent** on `tools/call` | Conformance with the MUSTs that apply to us |
| 8 | Dual era: the step-7 legacy assertions still pass against the v2 binary | The whole backward-compatibility constraint (R1) |
| 8 | Concurrency: N parallel `tools/call` on `capture` + `recall`, assert no `database is locked` | v2 runs sync handlers on a worker thread; no module-scope SQLite connections exist, but two write paths become concurrently reachable |
| 8 | The installer's embedded client validator (`install-agent-envs.py:822-850`) still reports the handshake OK | The Codex/OpenCode/Copilot install path survives the bump |

### `doctor.sh` visibility check

`doctor.sh` must report **interpreter path + mcp version + era** on one line (step 6).
This is the only signal that reflects what a machine actually serves, as opposed to what
`requirements.txt` claims. If it is ever dropped, a vault can serve legacy forever while
everything reports green. Add `_mcp_probe.py` to the explicit deployed-file list in
`install-agent-envs.py::validate_files` (currently ten entries at `:619-630`) so a stale
vault gets named instead of ImportError-ing at startup — `setup.sh:186` copies
`scripts/*.py` by glob, so the file itself deploys automatically.

### What can only be smoke-tested by hand

No unit test proves a real client accepts our bytes; the harness proves we match our
*reading* of the spec, which is a different claim. After step 1 and again after step 8,
per client: start a session, confirm the server appears with eight tools, call `recall`
with a query that has known hits, and confirm the returned path opens with that client's
own file-read tool.

Priority order, cheapest and most informative first:

1. **Claude Code** — the reference client, and the one whose `isReadOnly()` /
   `isConcurrencySafe()` behaviour step 1 targets. Confirm the read-only tools stop
   prompting.
2. **Codex CLI** and **GitHub Copilot CLI** — both registered by `install-agent-envs.py`
   with explicit `env` blocks; they exercise the `py -3` interpreter argv path.
3. **VS Code GitHub Copilot** — confirm step 4's `instructions=` text actually surfaces
   (this is Q3 in §9, currently not established).
4. **LM Studio** — the client measured to top out at 2025-06-18, so the most likely place
   a version-handling mistake shows up.

Record the client version alongside the result. When a client later goes modern-only, that
record is what tells us whether it was ever proven against a dual-era server.

---

## 9. Risks, open questions and how to close them cheaply

**Q1 — Which protocol version do our clients actually send?** *The single
highest-value measurement in this plan, and the gate on step 8.* Every inspectable client
is pre-2026-07-28: Claude Code 2.1.220 `LATEST_PROTOCOL_VERSION = "2025-11-25"`, VS Code
1.130.0 `"2025-11-25"`, Copilot CLI 1.0.70 `"2025-11-25"`, Codex 0.145.0 requests
`"2025-06-18"` on the live wire (`clientInfo: {"name":"codex-mcp-client","version":"0.145.0"}`)
despite carrying `"2026-07-28"` in its version enum, LM Studio 0.4.6+1 tops out at
`"2025-06-18"` (measured 2026-07-30, client-reality reviewer; a dated snapshot of one
machine).
*Cheapest experiment:* log the inbound `_meta` protocol version to stderr for a week. Ten
lines, zero risk, and it converts the whole step-8 decision from a judgement into a
reading.

**Q2 — Do Cline, Windsurf and Claude Desktop speak a modern revision?** **Not
established.** None is installed here; Cline's repo root declares no MCP SDK dependency
(monorepo) and Claude Desktop is closed source. The only defensible bound is indirect:
`@modelcontextprotocol/sdk` latest is 1.30.0, still on the 2025-11-25 line, while the
2026-07-28 TypeScript implementation ships under **new package names**
(`@modelcontextprotocol/server` 2.0.0, published 2026-07-27) — so TS clients face a
package migration, not a version bump, which is a structural reason to expect slow
adoption. Do **not** record these three as legacy; record them as unknown.
*Cheapest experiment:* the same 20-line stdio shim from Q1, run once per client.

**Q3 — Does VS Code Copilot actually surface `instructions` to the model?** Capture and
plumbing verified; the final prompt text is not. Matters because it determines whether the
`.github/copilot-instructions.md` duplication can ever be retired.
*Cheapest experiment:* set `instructions=` to a distinctive falsifiable directive (e.g.
"always prefix answers with KB:"), remove the managed block in a scratch checkout, and see
whether behaviour changes.

**Q4 — Will `mcp` 2.0.1 land, and should the release wait for it?** A major with zero
post-GA patch releases will get one, and it is likely to touch exactly the code paths this
route depends on (`runner.py` resultType stamping, `serve_dual_era_loop`, `caching.py`).
*Cheapest check, at release time:*
`curl -s https://pypi.org/pypi/mcp/json | python -c "import sys,json;print(sorted(v for v in json.load(sys.stdin)['releases'] if v.startswith('2.')))"`

**Q5 — Is the deployed copy of `kb-mcp.py` in the live vault current?** If a deploy copy
has drifted, everything in this plan applies to the repo and not to the running server —
the ADR-0002 failure mode.
*Cheapest check, before starting:* diff `$VAULT/.claude/scripts/kb-mcp.py` against the
repo copy.

**R1 — The backward-compatibility fallback is a client SHOULD, not a guarantee, and
`initialize` was removed rather than deprecated.** So it gets no twelve-month window, and
`mcp` 1.29.0 proves upstream will not backport 2026-07-28 into the 1.x line. The clock
ends the day a client ships modern-only *and* declines to probe. Nothing to do now; this
is what Q1 is monitoring for.

**R2 — Conformance is a per-machine property, not a per-release one.** `install_python_dep`
skips any already-importable package, so step 8 changes git and no deployed vault. Only the
step-6 doctor line can see this. Mitigation is in step 8's scope note: do not auto-mutate
the user's Python environment without the settings opt-in.

**R3 — Concurrency, introduced by the SDK not the spec.** v2 runs sync handlers on a worker
thread. There are no module-scope SQLite connections in `_activity.py`, `_memory.py`,
`kb-recall.py`, `_usage.py` or `_kbindex.py` — every `sqlite3.connect(...)` is inside a
function — so the obvious bug is absent. Remaining exposure: two concurrent `capture`
calls, `_usage.py:73` (`timeout=5.0`), and the `_activity` temporal-LLM cache write. Test
is in step 8.

**R4 — Statelessness audit.** An open stdio process "is not a conversation or session"
(<https://modelcontextprotocol.io/specification/2026-07-28/basic>). Our tools look clean —
every one takes all its inputs as arguments. The pair to check deliberately is
`review_pending`/`review_decide`: reading `kb-mcp.py:157-174`, `review_decide` takes a
`stem` and does not assume a prior `review_pending` in the same process.
*Cheapest experiment:* call `review_decide` as the very first request of a fresh process and
assert identical behaviour.

**R5 — A pre-existing false negative in the core tool, worth its own task.**
`kb-mcp.py:98` returns "Geen treffers in de KennisBank." when `sqlite_vec` is missing but
Ollama is reachable — a confident "no hits" where the truth is "the index is unreachable".
Not introduced by anything here; ~5 lines to distinguish. File as a separate Backlog task
under whichever route wins.

**R6 — Genuinely unclear from primary sources, reported not resolved.** (a) The changelog
lists five methods requiring `ttlMs`/`cacheScope`; the caching page lists six, including
`server/discover`. Six is right — `DiscoverResult extends CacheableResult` in schema.ts —
but the pages disagree and I found no erratum. (b) `ServerCapabilities` still carries
`resources.subscribe?: boolean` even though `resources/subscribe` is replaced by
`subscriptions/listen`; no page states the mapping. (c) Whether `ResultType` is a closed
union or open (`"complete" | "input_required" | string`) came from a summarising fetch of
schema.ts, not a verbatim read. None affects us: we emit no notifications, declare no
subscribe, and only ever produce `"complete"`.

### Closed by measurement — no longer open

- **Is it safe to emit `resultType`/`ttlMs`/`cacheScope` to a legacy client?** **Yes.** A
  dual-era server stamping all three on `initialize` and `tools/list` was accepted by both
  `mcp` 1.28.1 and 1.9.4, with the extras surviving into `model_extra`
  (`{'resultType': 'complete', 'ttlMs': 3600000, 'cacheScope': 'private'}`); TS clients use
  zod, which strips unknown keys rather than rejecting them (measured 2026-07-30,
  client-reality reviewer). The stdlib route's "residual uncertainty" here is resolved. It
  is moot under the recommended route, where the SDK decides.
- **Does mcp 2.0.0 emit the required fields on our behalf?** **Yes**, verified from the
  v2.0.0 source by two independent reviewers: `resultType` stamped at `runner.py:387-393`;
  `ttlMs`/`cacheScope` at `runner.py:362` with model defaults at `_types.py:207,211` so
  even un-hinted cacheable methods stay conformant; `serve_dual_era_loop` at
  `lowlevel/server.py:711` picks the era from the client's first frame; discovery payloads
  built from `MODERN_PROTOCOL_VERSIONS` only. One caveat worth carrying: `resources/read`
  carries the cache fields because of those *model defaults*, not because a hint was
  configured — a design that claims otherwise is right about the fact and wrong about the
  mechanism.
- **Does mcp 2.0.0 have zero field time?** **No** — seven weeks of public pre-releases
  (§1). The real gap is zero *post-GA patch* releases.

---

## 10. Decision log

| # | Decision | What would have to change to revisit |
| --- | --- | --- |
| D1 | **SDK owns protocol conformance; we write no wire code.** | The SDK stops serving the legacy era, or an SDK bug blocks us with no workaround. Then the stdlib route returns — with the §4 refutations as its acceptance criteria, not as a punch list |
| D2 | **The stdlib route is rejected**, on era-as-date-compare, the forward-jumping `initialize`, and cp1252 stdin — the last verified here in both failure modes | A future revision that the SDK declines to implement. The ~250-line protocol module is not the cost; owning version negotiation is |
| D3 | **The pin bump is the last step and is gated on demonstrated need AND preconditions**, not scheduled | Both must hold: Q1 shows a client sending 2026-07-28 (necessity), *and* 2.0.1 ships with steps 1-7 green (safety). Preconditions alone do not flip the gate |
| D4 | **Pin form `>=2.0.1,<3`**, not `==` and not `>=2.0.0` | A lockfile arrives (then `==` becomes cheap), or 2.x proves unstable enough that an exact pin beats a floor |
| D5 | **Minimal code beats minimal dependency here** | Only if the MCP surface's dependency became genuinely removable — which needs `sqlite-vec` gone from the recall path too. Not foreseeable |
| D6 | **Annotations ship first, on the current pin** | Nothing. This is the one step with a measured present-day payoff and no protocol coupling |
| D7 | **Zero new tools.** `read_note`, `orientation` and the `capture` provenance params all deferred with named triggers — a departure from the reviewers' steer on `read_note`, on the grounds that step 5 discharges most of its argument | Any of the three triggers in §6 firing. `read_note` is closest: establish one client in use that lacks filesystem read |
| D8 | **`recall` keeps a text return; only the four already-dict tools get `structuredContent`** | A consumer of structured recall output appears that is not an LLM. Atlas reads the vault directly, so not Atlas |
| D9 | **The `.github/copilot-instructions.md` duplication stays**, and `instructions=` is additive rather than a replacement | Q3 shows VS Code surfacing `instructions` to the model, *and* Copilot CLI's allowlist stops gating third-party servers |
| D10 | **Adopt no extensions.** Tasks, MCP Apps, Skills-over-MCP, OAuth variants, MRTR all skipped | Tasks: a tool that genuinely needs minutes *and* belongs on the agent path. MCP Apps: only if Atlas is abandoned. Skills: an Extensions-Track SEP with a reference SDK implementation |
| D11 | **The four temporal tools are not consolidated** into one `activity_recall`, despite that being better design | A clean-slate surface with no shipped client configurations to break |
| D12 | **No auto-upgrade of the user's Python environment** during `setup.sh` | The `kennisbank-settings.json` opt-in gains a toggle for it. Sovereignty over convenience: KennisBank does not mutate a Python environment behind the user's back |
| D13 | **`doctor.sh` reports interpreter + version + era together**, not era alone | Nothing. The three-way drift measured in §3 is the argument |
| D14 | **TASK-101's "fail loudly" work is retained as landed**, not re-litigated. It removed the silent-success failure mode and added four falsifiable tests | Nothing — it is strictly better than what it replaced. Two follow-ups only: the blind guard at `tests/test_kb_mcp.py:69` still needs replacing (step 1), and its `>=2.0.0,<3` advice needs aligning to D4 (step 8) |

---

*Every step above is one Backlog task. Per CLAUDE.md: create the task before executing,
set it In Progress on start, and close it only after the gate
(`python -m pytest tests -q`) is green and any PR's Copilot review has been processed.*
