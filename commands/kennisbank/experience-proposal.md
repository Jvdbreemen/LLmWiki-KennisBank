# Experience procedure proposal

Generate a human-reviewable procedure proposal from derived experience
records. This is offline and proposal-only: it never creates or edits a skill,
memory, configuration, or code. At least two current, validated,
evidence-bound experiences with concrete actions and one consistent outcome
state are required.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-experience-proposal.py" \
  --records /path/inside/vault/06-evaluations/experiences.jsonl \
  --output /path/inside/vault/06-evaluations/procedure-proposals.json \
  --as-of 2026-08-26
```

Rejected/retracted, stale, contradictory, or actionless records are reported
as rejections. Owner approval and the existing controlled skill-evolution path
remain mandatory for any later change.
