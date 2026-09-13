# Freeze source holdout

Use this command only after a human has reviewed the source cases. It reads
the cases inside the local vault boundary and writes a versioned manifest with
queries, expected verdicts, source hashes, and character windows. Raw passages,
answers, and arbitrary document payloads are not copied to the manifest.

```bash
python scripts/build-source-holdout.py \
  --cases /path/inside/vault/reviewed-source-cases.jsonl \
  --output /path/inside/vault/06-evaluations/source-holdout.json \
  --vault "$KENNISBANK_VAULT"
```

Positive cases require an approved source path and at least one valid character
window. Cases without a source must explicitly use `not_found` or `unknown`.
The command does not build the source index and does not alter raw files.
