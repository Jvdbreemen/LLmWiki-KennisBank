# KennisBank - Guiding Principles and Values

**English** · [Nederlands](guiding-principles-and-values.nl.md)

This is the compass for KennisBank: what the project cares about (its **values**)
and the design laws those values produce (its **principles**), worked out
together as one document. Where the concise reference lists live in
[`VALUES.md`](../VALUES.md) and [`PRINCIPLES.md`](../PRINCIPLES.md), this is the
worked-out version - the *why*, the *how*, and the thread that connects them.

The chain is deliberate and one-directional:

> **values → principles → code.**

Values decide what matters. Principles turn that into design laws. Code obeys the
principles. When a decision is unclear, walk back up the chain: a change that
honors the principles but betrays a value is the wrong change.

## The north star: invisible, fast, out of the way

Everything below serves a single image. KennisBank must feel as if it is not
there. Its job is to help you with your real work - writing, coding, thinking -
without ever demanding attention for itself. The best version of KennisBank is
the one you forget is running, right up to the moment it hands you exactly the
context you needed.

## Part 1 - The values (what we care about)

Values are not rules; they are the character behind the code. They cluster into a
few themes.

### Your data, protected: Sovereignty and Privacy

**Sovereignty** - Your knowledge belongs to you. Local by default, no cloud
without your consent, no lock-in, no silent telemetry. Independence is worth the
extra engineering; the alternative is renting access to your own memory.

**Privacy** - What you capture stays yours *and* stays contained. Secrets are
redacted before they touch disk; nothing reaches a cloud provider without an
explicit, up-front warning and your opt-in; there is no telemetry by default. A
memory layer that leaks is worse than no memory layer at all.

### The trust trio: Honesty, Transparency, Traceability

These three are a chain of their own - each depends on the one before it.

**Honesty** - Truth over convenience, even when the truth is inconvenient. The
system never fabricates to look complete; uncertainty is flagged, not smoothed
over. A confident, unsourced answer is a bug, not a feature.

**Transparency** - No hidden behavior. You can always see what KennisBank
captured, injected, or sent - through plain files, structured status, and a
doctor that tells you the truth. The system is a glass box, not a black one; a
tool you cannot inspect is a tool you cannot trust.

**Traceability** - A complete audit trail. Every fact, every recall, every
injection traces back to its origin and its *why* - which session, which source,
which score. Provenance is not an afterthought bolted on; it is how the system
earns belief. Nothing enters the knowledge base that cannot be followed home.

Together: honesty means it will not lie to you, transparency means you can watch
it work, and traceability means you can prove where anything came from.

### The craft: Care and Clarity

**Care** - For the person, the work, and the long haul. Code the next maintainer
can understand and repair. A system that respects your attention, your time, and
your machine's energy. This project is something worth protecting and nurturing -
not a problem to be solved mechanically and abandoned.

**Clarity** - Understandable beats clever. We want to know how things work under
the hood - down to the query, the index, the byte - and we build so the next
person can too. Clever solutions can always be discussed; clarity is the default
we return to.

### The partnership: Respect, Helpfulness, Integrity

**Respect for the human** - You are the editor-in-chief. The tool proposes; you
decide. Your focus is precious, and any interruption has to earn its place.

**Helpfulness** - Being genuinely useful is the entire point - a real partner in
the work, not a passive tool that waits for instructions. Usefulness is measured
by whether your real work got easier.

**Integrity** - We say the true thing when it is inconvenient, surface risks that
were not asked about, and disagree when the evidence supports it. Accuracy over
agreement, always.

### The spirit: Curiosity and joy

**Curiosity and joy** - Built by someone who loves understanding how things work,
from SID chips and copper bars to embeddings and vector search. Elegant hacks are
celebrated, low-level understanding is prized, and the work itself should be a
pleasure. A project made with delight tends to be a project worth using. (Also:
mostly harmless.)

## Part 2 - The principles (how the values become design laws)

Each principle is a value made operational. Read them as "because we value X, we
build this way."

1. **Performance before everything.** Heavy work (embedding, indexing,
   extraction) happens off the hot path - at write time, on idle, scheduled. The
   interactive path (recall, injection) stays sub-second. *A system that adds
   latency to your real work is one you will turn off.*
2. **Retrieval-first.** The core job is singular: find the right, current context
   at the right moment and hand it over. Everything else is supporting cast.
3. **Local, always.** Local storage (SQLite, markdown), local embeddings
   (Ollama), local MCP (stdio). No hosted service, no mandatory cloud, no
   telemetry by default. *(Sovereignty, Privacy.)*
4. **Automate over discipline.** What relies on manual discipline does not happen.
   Quality is secured autonomously; the user is asked only for what only a human
   can decide.
5. **Human as editor-in-chief.** The system proposes; the human decides. It never
   silently deletes, force-merges a belief, or rewrites your knowledge behind your
   back. *(Respect, Integrity.)*
6. **Provenance and auditability.** Every piece of knowledge traces to a source.
   No summary without evidence links; if it cannot be sourced, it is flagged, not
   trusted. *(Honesty, Traceability.)*
7. **Never the same mistake twice.** The system remembers lessons and old bugs and
   actively helps prevent them from returning.
8. **Spontaneous, but high-precision, help.** Proactive surfacing only above a
   high relevance threshold. An unwanted interruption is precisely the cruft
   KennisBank exists to avoid. *(Respect, Helpfulness.)*
9. **Fail-open.** A missing Ollama, a stale index, a broken hook, a model that is
   down - none may block the agent. KennisBank degrades gracefully and gets out of
   the way. *(Care, Helpfulness.)*
10. **Idempotent-safe.** Installers and config mutations are safe to re-run,
    preserve user data, use marked managed blocks and key-scoped edits, back up
    before touching freeform files, and never clobber what they did not create.
    *(Care.)*
11. **Multi-agent, one vault.** One local vault and one stdio MCP server, shared
    across every agent - Claude Code, Codex, OpenCode, GitHub Copilot CLI, and
    whatever comes next.
12. **Time is a first-class dimension.** Memory is bi-temporal: *valid time* (when
    a fact was true) is distinct from *capture time* (when the system learned it).
    Facts supersede, expire, and retract - with history intact, never overwritten.
13. **KISS - simple and explainable over clever and opaque.** Prefer the approach a
    maintainer can understand and repair. One clear mechanism beats three clever
    ones. *(Clarity, Transparency.)*

## Part 3 - How values show up in practice

The chain, made concrete:

| Value | Principle(s) | In the code |
|---|---|---|
| Sovereignty | Local, always | local SQLite/markdown, local Ollama, stdio MCP; cloud opt-in |
| Privacy | Local, always | secret redaction in hooks, a warning gate before any cloud call, no default telemetry |
| Honesty | Provenance & auditability | never fabricate; flag what cannot be verified |
| Transparency | KISS; Fail-open | `doctor.sh` PASS/WARN/FAIL, structured JSON, clear status over log noise |
| Traceability | Provenance & auditability | `source_ref` on every event, provenance wikilinks, the Recall Inspector's *why* |
| Care | Idempotent-safe; Fail-open | safe re-runnable installers, backups before edits, graceful degradation |
| Clarity | KISS | ADRs that explain the *why*, one mechanism over three |
| Respect | Human as editor-in-chief; high threshold | quarantine for unverified memory, no silent deletes |
| Helpfulness | Retrieval-first; Performance | sub-second recall, the right context at the right moment |
| Integrity | Human as editor-in-chief | surfaces risks and disagreements instead of guessing |
| Curiosity/joy | - | the project is allowed to be a bit fun |

## What KennisBank is not

- Not a hosted platform, not a SaaS, not a required cloud account.
- Not a system that forgets on your behalf or edits your knowledge silently.
- Not a graph database, an Obsidian plugin, or a mandatory external app.
- Not a source of confident, unsourced answers.

## How to use this document

When you propose a change, weigh it against the chain. If it makes KennisBank
slower on the hot path, less local, less private, harder to explain, less
traceable, or louder - the burden of proof is on the change. If it makes retrieval
sharper, the system quieter, the human more in control, or the trail clearer - it
is pulling in the right direction.

_See also: [`VALUES.md`](../VALUES.md) and [`PRINCIPLES.md`](../PRINCIPLES.md) (the
concise reference lists), `CLAUDE.md` (how KennisBank should feel), `AGENTS.md`
(operational install/upgrade rules), and `docs/adr/` (the decisions that live all
of this out)._
