---
description: Registreer en beoordeel de private owner-vault-canary voor bron- en ervaringsrecall
---

# /kennisbank:projection-canary

Gebruik deze command uitsluitend na een echte expliciete `source_recall` of
`experience_recall`. De append-only JSONL blijft onder
`$KENNISBANK_VAULT/06-claude/evaluations/production-canary/`; het rapport bevat
alleen aantallen, percentages, latency en afzonderlijke gate-uitkomsten. Prompt,
passage, pad, SourceRef, lesson, embedding en antwoordtekst worden geweigerd.

Registreer eerst ten minste tien door de eigenaar gecontroleerde exacte
bronreconstructies. Gebruik `owner-reviewed=yes` alleen als de getoonde bytes
daadwerkelijk tegen de bevroren eigenaarbeoordeling zijn gecontroleerd.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-projection-canary.py" \
  record-source --id <opaque-id> --observed-at <iso-8601> \
  --status ok --route exact_ref --shown-count 1 --latency-ms <ms> \
  --owner-reviewed yes --reconstruction-correct yes \
  --provenance-correct yes --candidate-leakage 0 \
  --idempotency-key <unieke-sleutel>
```

Registreer een experience-case alleen als de eigenaar de recall zelf expliciet
vroeg in een natuurlijk ontstane taak. Een evalprompt of achteraf gereplayde
vraag is dus `natural-explicit-use=no` en telt niet mee voor de canarygate.
`useful`, `harmful` en `evidence-correct` zijn onafhankelijke oordelen; een
nuttige hit kan bijvoorbeeld toch schadelijk of verkeerd onderbouwd zijn.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-projection-canary.py" \
  record-experience --id <opaque-id> --observed-at <iso-8601> \
  --status ok --route lexical_fallback --shown-count <n> --latency-ms <ms> \
  --owner-reviewed yes --natural-explicit-use yes --useful yes --harmful no \
  --evidence-correct yes --candidate-leakage 0 \
  --idempotency-key <unieke-sleutel>
```

Toon het contentvrije tussenrapport:

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/kb-projection-canary.py" report
```

De vaste experiencegrens is minimaal twintig geldige beoordelingen, minstens
70% nuttig, hoogstens 5% schadelijk, 100% evidence-correct en nul candidate
leakage. Een individuele safety-fout blijft zichtbaar en wordt niet door een
gemiddelde verborgen. De command activeert of deactiveert zelf geen featureflag.
