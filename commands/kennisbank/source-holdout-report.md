# Source holdout report

Read-only report for the current source evidence ceiling. It checks whether
frozen positive cases still have the same approved source hash and valid
windows. Missing, changed, or unreadable evidence lowers the ceiling. The
output contains aggregate counts only; it does not print reviewed queries,
source paths, passages, or answers.

```bash
python scripts/source-holdout-report.py \
  /path/inside/vault/06-evaluations/source-holdout.json \
  --vault "$KENNISBANK_VAULT"
```
