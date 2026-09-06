---
description: Raadpleeg expliciet gevalideerde outcome-bound experiences
---

# /kennisbank:experience-recall

Gebruik deze route alleen voor een expliciete vraag zoals “wat werkte eerder?”
of “welke les hebben we hiervan?”. Alleen `validated` experiences met exact
geverifieerde SourceRefs, outcome-evidence en een geaccepteerde menselijke
review worden teruggegeven. Candidates en unknown records zijn diagnostisch,
geen advies. Automatische failure warnings zijn geen publiek productpad.

De response labelt de route expliciet:

```json
{
  "status": "ok|no_hit",
  "mode": "explicit",
  "retrieval_route": "hybrid|lexical_fallback",
  "hits": [{
    "experience_id": "...",
    "lesson": "...",
    "applicability": "...",
    "attempt_state": "failure",
    "resolution_state": "fix_validated",
    "outcome_state": "success",
    "source_ref_ids": ["sr_..."],
    "outcome_refs": ["..."],
    "validation_stamp": {
      "status": "validated",
      "evidence_state": "verified",
      "review_state": "accepted",
      "content_hash": "sha256:..."
    },
    "confidence_metadata": {
      "experience": 0.8,
      "cosine": 0.77,
      "lexical_match": true,
      "evidence_bound": true
    }
  }]
}
```

De gateway geeft maximaal drie ervaringen terug en vermijdt dubbele taken of
dezelfde bron in één resultaat. Bij een ontbrekende embedding-backend of een
modelmismatch blijft FTS beschikbaar als expliciet gelabelde
`lexical_fallback`. De response bevat geen raw passages of volledige SourceRefs;
haal die alleen op via een afzonderlijke expliciete source-recall.

```bash
printf '%s\n' '{"mode":"explicit","prompt":"<situatie>","k":3}' |
  python3 "$KENNISBANK_VAULT/.claude/scripts/kb-experience-recall.py"
```

De route is standaard uitgeschakeld. Een retrieval-hit-rate zonder downstream
verbetering is geen reden om deze capability aan te zetten.
`failure`, `advisory`, `automatic`, `fallback`, `ranking`, `promotion`, `hook`
en `injection` zijn geen publieke modi en retourneren `policy_disabled`.
