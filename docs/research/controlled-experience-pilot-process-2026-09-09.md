# Controlled experience pilot: operator and owner process

Status: preparation, not activation or release approval. Tracking: TASK-236;
release authority and rollback: TASK-237.

## Entry conditions

1. Bind the complete regression report to the runtime commit being installed.
   Later documentation-only edits must be identified separately.
2. Complete supported setup/client checks. Investigate the six existing wiki
   provenance failures without manufacturing citations or waiving the gate.
3. Preserve settings and canonical ledger through a scoped backup. Confirm the
   deployed runtime, configured vault and approved experience projection.
4. Exercise disabling the read flags and verify ordinary recall still works
   without deleting ledger records or raw evidence. Restore the pre-drill state.
5. Enable only explicit source and experience reads for the local pilot. Verify
   each selected client sees the current tools; installed files alone do not
   prove a long-running MCP process has reloaded them.

Capture and projection activity are not evidence that read routes are enabled.
An accepted lesson is corpus preparation, not an observed successful recall.

## Normal owner workflow

The owner works on an actual task and explicitly asks whether prior experience
can help. No quota-driven invented questions and no replay of old eval prompts.
The assistant retrieves eligible experiences, presents applicability and limits,
and resolves exact source evidence explicitly when needed for verification.

After use, ask the owner for three independent judgments: was it useful, was
anything harmful or misleading, and was the evidence correct? Do not infer all
three from a single generic approval. A useful suggestion can still be wrongly
grounded. Record no-hit and unavailable-evidence outcomes too, not only wins.

Metric interpretation follows the existing implementation: usefulness and harm
use all eligible owner-reviewed natural requests as their denominator. Evidence
precision is weighted by shown hits, not by requests. A no-hit request does not
create a correctly grounded hit; if no hits are shown across the whole pilot,
the evidence gate cannot pass. Do not interpret zero-case report fields as
measured safety or effectiveness.

The assistant records an opaque case id, actual route, measured latency, shown
count, natural-use status and owner judgments through the existing
`projection-canary` command. Use one writer at a time for the private log.
Prompts, answers, lessons, source paths and passages do not belong in that log
or in repository reports. Detailed investigation stays inside the private vault.

## Stop and review

On incorrect evidence, candidate leakage, unexpected automatic routing or
materially harmful advice, stop that exposure path and investigate. Preserve
the observation; never delete a failed case to improve the aggregate. Turning
off read flags must retain canonical history and source evidence.

Twenty reviewed natural uses is a minimum, not a deadline or assurance of
success. Apply the existing gates: at least 70% useful, at most 5% harmful,
100% evidence-correct and zero candidate leakage. With exactly twenty cases,
that means at least fourteen useful and at most one harmful observation, while
any evidence or leakage failure still prevents acceptance. A gate passing does
not establish broad generalizability or measured time savings.

## Exit decision

Publish content-safe aggregates with failures and limitations. Keep previous
blinded action results separate from prospective pilot evidence. The owner
chooses accept, amend or reject; only then can TASK-237 complete the ADR
lifecycle, PR review, release checklist and post-release verification.

Until entry conditions pass, both explicit read flags remain disabled. No
automatic warnings, source fallback, cross-layer ranking or skill promotion
are added by this pilot.
