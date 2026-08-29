---
description: Raadpleeg expliciet gevalideerde outcome-bound experiences
---

# /kennisbank:experience-recall

Gebruik deze route alleen voor “wat werkte eerder?”, “wat mislukte?” of een
failure-preventionadvies. Alleen `validated` experiences met source- en
outcome-links worden teruggegeven. Candidates en unknown records zijn
diagnostisch, geen advies. Een failure warning is adviserend en blokkeert geen
actie.

De response labelt de route expliciet:

```json
{
  "status": "ok|no_hit",
  "mode": "explicit|failure",
  "advisory": true,
  "hits": [{
    "experience_id": "...",
    "status": "validated",
    "evidence_kind": "failure_advisory",
    "outcome_state": "failure",
    "source_refs": ["..."],
    "outcome_refs": ["..."],
    "confidence_metadata": {
      "experience": 0.8,
      "cosine": 0.77,
      "lexical_match": true,
      "evidence_bound": true
    }
  }]
}
```

Candidates en `unknown` records worden niet door deze standaardgateway
teruggestuurd; er wordt geen code, configuratie of memory automatisch gewijzigd.

```bash
printf '%s\n' '{"mode":"failure","prompt":"<situatie>","k":5}' |
  python3 "$KENNISBANK_VAULT/.claude/scripts/kb-experience-recall.py"
```

De route is standaard uitgeschakeld. Retrieval-hit-rate zonder downstream
verbetering is geen reden om deze toggle aan te zetten.
