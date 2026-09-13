# Source and experience layer evaluation

Build a versioned evidence packet from aggregate observations only. The input
must list all six preregistered arms (`A` through `F`) or give an explicit
omission reason. The evaluator keeps usage telemetry disabled during the run,
and the output is not a production routing decision by itself.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-layer-eval.py" \
  --observations /path/inside/vault/06-evaluations/layer-observations.json \
  --output /path/inside/vault/06-evaluations/layer-evidence.json
```

The packet reports source and experience gates separately, normal/source/
experience latency separately, and applies the fixed `go`, `hold`, or `reject`
policy. Outcome-aware ranking remains research-only and disabled by default.
