# KennisBank - Core Values

**English** · [Nederlands](VALUES.nl.md)

Values are not rules. They are what this project *cares about* - the character
behind the code. Where `PRINCIPLES.md` says *how* KennisBank works, this says
*why we bother*. When the principles are silent or in tension, the values break
the tie.

The chain is simple: **values → principles → code.** A design decision that
honors the principles but betrays a value is the wrong decision.

## The values

### Sovereignty
Your knowledge belongs to you. Local by default, no cloud without your consent,
no lock-in, no silent telemetry. Independence is worth the extra engineering -
the alternative is renting access to your own memory.

### Privacy
What you capture stays yours and stays contained. Secrets are redacted before
they touch disk; nothing reaches a cloud provider without an explicit, up-front
warning and your opt-in; there is no telemetry by default. A memory layer that
leaks is worse than no memory layer at all.

### Honesty
Truth over convenience, even when the truth is inconvenient. Every claim traces
to a source; uncertainty is flagged, not smoothed over; the system never
fabricates to look complete. A confident, unsourced answer is a bug, not a
feature.

### Transparency
No hidden behavior. You can always see what KennisBank captured, injected, or
sent - through plain files, structured status, and a doctor that tells you the
truth. The system is a glass box, not a black one; a tool you cannot inspect is a
tool you cannot trust.

### Traceability
A complete audit trail. Every fact, every recall, every injection traces back to
its origin and its *why* - which session, which source, which score. Provenance
is not an afterthought bolted on; it is how the system earns belief. Nothing
enters the knowledge base that cannot be followed home.

### Care
For the person, for the work, and for the long haul. Code the next maintainer can
understand and repair. A system that respects your attention, your time, and your
machine's energy. This project is something worth protecting and nurturing - not
a problem to be solved mechanically and abandoned.

### Clarity
Understandable beats clever. We want to know how things work under the hood - down
to the query, the index, the byte - and we build so the next person can too.
Clever solutions can always be discussed; clarity is the default we return to.

### Respect for the human
You are the editor-in-chief. The tool proposes; you decide. Your focus is
precious, and any interruption has to earn its place. KennisBank does the tedious
work so a human can keep authority over what is true.

### Helpfulness
Being genuinely useful is the entire point - a real partner in the work, not a
passive tool that waits for instructions. Usefulness is measured by whether your
real work got easier, not by how much the system did.

### Integrity
We say the true thing when it is inconvenient, surface risks that were not asked
about, and disagree when the evidence supports it. Accuracy over agreement,
always. Trust is built by being right and honest, not by being agreeable.

### Curiosity and joy
Built by someone who loves understanding how things work - from SID chips and
copper bars to embeddings and vector search. Elegant hacks are celebrated, low-level
understanding is prized, and the work itself should be a pleasure. A project made
with delight tends to be a project worth using. (Also: mostly harmless.)

## How values show up in practice

- **Sovereignty** → local SQLite/markdown, local Ollama, stdio MCP; cloud is opt-in.
- **Privacy** → secret redaction in hooks, an explicit warning gate before any cloud call, no default telemetry.
- **Honesty** → provenance links, `kb-lint`, quarantine for unverified memory.
- **Transparency** → `doctor.sh` PASS/WARN/FAIL, structured JSON output, clear status over log noise.
- **Traceability** → `source_ref` on every event, provenance wikilinks, the Recall Inspector that shows *why* something surfaced.
- **Care** → idempotent-safe installers, fail-open hooks, backups before edits.
- **Clarity** → KISS, ADRs that explain the *why*, one mechanism over three.
- **Respect** → high relevance threshold for surfacing, no silent deletes.
- **Helpfulness** → sub-second recall, the right context at the right moment.
- **Integrity** → the system flags what it cannot verify instead of guessing.
- **Curiosity/joy** → the project is allowed to be a bit fun.

_See also: `PRINCIPLES.md` (the design laws these values produce), `CLAUDE.md`
(how KennisBank should feel), and `docs/adr/` (the decisions that live them out)._
