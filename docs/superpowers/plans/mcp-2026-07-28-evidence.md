# Evidence: the MCP surface measured on the wire

Captured 2026-07-30 by driving `scripts/kb-mcp.py` as a subprocess over
newline-delimited JSON-RPC, exactly as an MCP client does. This records what the
server actually puts on the wire, not what the source intends.

Reproduce with `python -m pytest tests/test_kb_mcp_wire.py -q`: every claim below is
asserted there and fails when it stops holding.

## Environment

| Item | Value |
| --- | --- |
| `mcp` SDK | `1.28.1` (the pin currently in `requirements.txt`) |
| Python | 3.14.2 |
| Transport | stdio, subprocess, no network |
| Negotiated protocol version | `2025-06-18` |

Note the era: this is the **2025-era** handshake, deliberately. The pin bump to
`mcp>=2` is the last step of the migration plan and is gated on a measurement,
because a modern-only server fails against the clients actually in use
(`McpError: Method not found: initialize`). See `mcp-2026-07-28-migration.md`
section 1.

## What `initialize` returns

Result keys: `capabilities`, `instructions`, `protocolVersion`, `serverInfo` - including `instructions`, which is the point of the
constructor change.

- `serverInfo`: `{"name": "kennisbank-geheugen", "version": "1.28.1"}`
- `instructions` present: **true**
- first line: `Je hebt een lokale KennisBank (persoonlijk geheugen + gecureerde wiki) via de MCP-tools `recall` en `capture`.`

The pull-nudge now travels on three carriers at once: this protocol field, the
`kennisbank://instructions` resource, and the managed block in
`.github/copilot-instructions.md`. None of the three reaches every client on its
own, which is why all three stay.

## Tool annotations as delivered

| Tool | Annotations on the wire | Label |
| --- | --- | --- |
| `recall` | `readOnlyHint=true`, `openWorldHint=false` | Recall knowledge |
| `capture` | `readOnlyHint=false`, `destructiveHint=false`, `idempotentHint=false`, `openWorldHint=false` | Capture a memory |
| `review_pending` | `readOnlyHint=true`, `openWorldHint=false` | List memories awaiting review |
| `review_decide` | `readOnlyHint=false`, `destructiveHint=true`, `idempotentHint=false`, `openWorldHint=false` | Decide one review item |
| `what_did_i_do` | `readOnlyHint=true`, `openWorldHint=false` | What happened on a date |
| `timeline` | `readOnlyHint=true`, `openWorldHint=false` | Activity timeline |
| `weeklog` | `readOnlyHint=true`, `openWorldHint=false` | Week overview |
| `topic_timeline` | `readOnlyHint=true`, `openWorldHint=false` | Topic through time |

Why this matters concretely: Claude Code derives both `isReadOnly()` and
`isConcurrencySafe()` from `annotations.readOnlyHint`, defaulting each to false when
annotations are absent. Before this change the six read-only retrieval tools
presented as possibly-destructive and non-parallelisable, costing needless
confirmation prompts and serialisation on the hot path. Annotations are hints, not
enforcement: clients are explicitly told not to base trust decisions on annotations
from an untrusted server.

## Honest limits of this evidence

- Measured against SDK `1.28.1`, not `2.0.0`. The modern-era requirements
  (`server/discover`, `resultType`, `ttlMs`/`cacheScope`) are **not** proven here and
  stay open until the gated step runs in a throwaway virtualenv.
- `destructiveHint=true` on `review_decide` is a claim about our own code: the
  decision flips a memory status that the write path then refuses to change again.
  Should that ever become reversible, the annotation becomes a lie and
  `tests/test_kb_mcp.py` must change in the same commit.
- No client was driven end to end here. That is manual smoke work and cannot be
  automated in this suite.
