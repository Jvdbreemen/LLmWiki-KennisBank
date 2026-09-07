# Source-grounded experience capture

Experience capture is an opt-in, private write path for naturally occurring
lessons. Set `experience_capture=true` only during shadow capture. The command
writes one typed event to `.claude/kb-experience-ledger.db`; it does not build
or modify the disposable `.claude/kb-experience-index.db` projection and does
not enable recall.

Pass the private event as JSON on stdin so its content does not appear in the
process command line. `source_ranges` are vault-relative exact character
ranges under an approved raw-source root. The command reads those ranges and
creates complete content-addressed SourceRefs itself.

```powershell
$event = @{
  idempotency_key = 'session-id:lesson-1'
  session_id = 'session-id'
  task_id = 'session'
  event_type = 'fix'
  observed_at = '2026-09-07T12:00:00+00:00'
  payload = @{
    situation = 'what happened'
    goal = 'intended result'
    approach = 'what was tried'
    action = 'the concrete change'
    observed_result = 'what was directly observed'
    lesson = 'the reusable lesson'
    applicability = 'when the lesson applies'
    attempt_state = 'failure'
    resolution_state = 'fix_validated'
    attribution_limits = 'what this observation does not prove'
  }
  source_ranges = @(@{
    source_path = '01-raw/transcripts/session.md'
    start = 0
    end = 120
    chunk_id = 'lesson-1'
  })
} | ConvertTo-Json -Depth 6

$event | python "$env:KENNISBANK_VAULT/.claude/scripts/kb-experience-capture.py"
```

The result contains only the event id, candidate experience id, SourceRef
count, and mutation status. Repeating the same idempotency key with identical
content is a no-op; changed reuse is rejected. Invalid, external, missing, or
redacted source ranges fail before a ledger event is written.

Capture is proposal-only. A session outcome must exist for the same
`session_id` and `task_id`; then follow [Experience candidate review](experience-review.md).
Only exact evidence plus a content-hash-bound owner acceptance can enter a later
projection rebuild.
