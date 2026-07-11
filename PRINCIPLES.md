# KennisBank - Core Principles

**English** · [Nederlands](PRINCIPLES.nl.md)

These are the principles that govern every design and code decision in
KennisBank. They are the *why* behind the code; when a trade-off is unclear,
these decide it. Operational instructions live in `AGENTS.md`; how the project
should *feel* is written down here.

## North star: invisible, fast, out of the way

KennisBank must feel as if it is not there. Its job is to help you with your real
work - writing, coding, thinking - without ever demanding attention for itself.
The best version of KennisBank is the one you forget is running, right up to the
moment it hands you exactly the context you needed.

Everything below serves that north star.

## The principles

### 1. Performance before everything
Optimize for daily use. Heavy work (embedding, indexing, extraction) happens
**off the hot path** - at write time, on idle, or scheduled. The interactive
path (recall, prompt injection) stays **sub-second**. Pay up front, retrieve
fast. A knowledge system that adds latency to your real work is a knowledge
system you will turn off.

### 2. Retrieval-first
The core job is singular: find the right, current context at the right moment and
hand it over. Everything else - capture, distillation, visualization - is
supporting cast. When two features compete, the one that improves retrieval wins.

### 3. Local, always
Nothing leaves your machine without explicit consent. Local storage (SQLite,
markdown), local embeddings (Ollama), local MCP (stdio). No hosted service, no
mandatory cloud, no telemetry by default. Your knowledge is yours; sovereignty is
not a feature, it is the foundation.

### 4. Automate over discipline
What relies on manual discipline does not happen in practice. Quality is secured
autonomously - capture, indexing, staleness checks, memory hygiene run on their
own. The user is asked only for what only a human can decide.

### 5. Human as editor-in-chief
The system proposes; the human decides. KennisBank never silently deletes, never
force-merges a belief, never rewrites your knowledge behind your back. Unverified
memories wait in quarantine for a human call. The machine does the tedious work;
the human keeps authority over what is true.

### 6. Provenance and auditability
Every piece of knowledge traces back to a source - a raw session, a document, an
event. No summary without evidence links; no claim you cannot follow home. This
is the anti-hallucination guarantee: if it cannot be sourced, it is flagged, not
trusted.

### 7. Never the same mistake twice
The system remembers lessons learned and old bugs, and actively helps prevent
them from returning. "You hit this exact wall two months ago" - surfaced at the
right moment - is worth more than any amount of raw storage.

### 8. Spontaneous, but high-precision, help
Proactively surfacing prior knowledge is allowed - but only above a high
relevance threshold. An unwanted interruption is precisely the cruft KennisBank
exists to avoid. Suppress log noise; give clear summaries and status instead. No
ceremony, no filler.

### 9. Fail-open
A missing Ollama, a stale index, a broken hook, a model that is down - none of
these may block the agent. KennisBank degrades gracefully: it skips its own side
effect, warns quietly, and gets out of the way. The user's work never stops
because the memory layer hiccuped.

### 10. Idempotent-safe
Installers and config mutations are safe to re-run for both fresh and existing
setups. They refresh tooling, **preserve user data**, use marked managed blocks
and key-scoped edits, back up before touching freeform files, and never clobber
what they did not create. Upgrade is just install, run again.

### 11. Multi-agent, one vault
One local vault and one stdio MCP server, shared across every agent - Claude
Code, Codex, OpenCode, GitHub Copilot CLI, and whatever comes next. Your Copilot
session becomes recallable history in your Claude session. The knowledge layer is
agent-agnostic; the vault is the single source of truth.

### 12. Time is a first-class dimension
Memory is **bi-temporal**: *valid time* (when a fact was true) is distinct from
*capture time* (when the system learned it). You can ask "what was true as of date
X" and get an honest answer. Facts supersede, expire, and get retracted - with
the history intact, never overwritten.

### 13. KISS - simple and explainable over clever and opaque
At every fork: prefer the approach a maintainer can understand and repair over
the one that merely works. One clear mechanism beats three clever ones. Make
design choices explicit - explain *why*, not just *what*. Clever can always be
discussed; clarity is the default.

## What KennisBank is not

- Not a hosted platform, not a SaaS, not a required cloud account.
- Not a system that forgets on your behalf or edits your knowledge silently.
- Not a graph database, an Obsidian plugin, or a mandatory external app.
- Not a source of confident, unsourced answers.

## How to use these principles

When you propose a change, weigh it against this list. If it makes KennisBank
slower on the hot path, less local, harder to explain, or louder - the burden of
proof is on the change. If it makes retrieval sharper, the system quieter, or the
human more in control - it is pulling in the right direction.

_See also: `CLAUDE.md` (how KennisBank should feel, for contributors and agents),
`docs/adr/` (the decisions that implement these principles), and `AGENTS.md` (the
operational install/upgrade rules)._
