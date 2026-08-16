# /kennisbank:autoreview — client-LLM escalation for quarantined memories

Trap 2/3 of the autonomous memory review (TASK-195). Trap 1 (`kb-verify.py`)
already promoted everything a memory's own passage supports; what remains in
quarantine needs a reading of the WHOLE transcript, which is your job in this
command. You adjudicate; `kb-autoreview.py apply` disposes — the promotion and
retraction rules live in that script, not in you.

## Vault root (REQUIRED — resolve first)

`VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"` — resolve once, use
everywhere. The fallback is the documented default deploy location; the
env var always wins (ADR-0002).

## Procedure

1. **Bundle.** Run:

   ```bash
   python3 "$VAULT/.claude/scripts/kb-autoreview.py" bundle
   ```

   It refuses when `auto_review_llm` is off — respect that refusal; the
   toggle is the owner's cloud consent, not a technicality. The output names
   a batch directory with `case-NNN/` subdirectories (claim.md +
   transcript.txt) and a `manifest.json`.

2. **Adjudicate every case**, in parallel subagents (10–15 cases per agent).
   Per case the question is narrow: does the transcript, ANYWHERE in it,
   state this claim? Instructions that are load-bearing, learned from
   measured failures:
   - The memory is usually DUTCH, the transcript largely ENGLISH. Search
     both languages; translate the key concepts. This is the most common
     cause of a false "absent".
   - Search identifiers, filenames, version numbers, error strings — they
     survive translation and paraphrase.
   - `supported` needs a VERBATIM quote from transcript.txt as evidence.
     Stating is enough; the transcript need not argue for the claim.
   - `partial` = the transcript carries part, the claim adds specifics it
     lacks. `absent` = the subject appears nowhere after searching several
     ways. `unclear` = you cannot decide; that is a legitimate answer.

3. **Refute every `absent`** with an independent second subagent instructed
   to overturn the verdict (default to overturning when unsure). Record
   `refuted: true` when it found the claim after all (and lift the verdict to
   what it found), `refuted: false` when the absence survived.

4. **Write `results.json`** in the batch directory: a JSON list of
   `{"stem", "verdict", "evidence", "refuted"}` — `refuted` is null for
   non-absent verdicts.

5. **Apply.** Run:

   ```bash
   python3 "$VAULT/.claude/scripts/kb-autoreview.py" apply "<batch>/results.json"
   ```

   The script promotes `supported` (evidence quote into the promote log),
   retracts ONLY `absent` + `refuted: false` (capped, logged, reversible),
   and leaves everything else. Do not bypass it: applying verdicts by editing
   files directly would skip the caps and the audit trail.

6. **Reindex and report.** Run
   `python3 "$VAULT/.claude/scripts/build-kb-index.py"` and give the user the
   apply summary plus the batch path for the audit trail.

## What this command does NOT do

It never touches `current`, `superseded` or `retracted` memories; it never
deletes; every action is a status change with a log line, and
`_memory.reopen()` undoes any of them.
