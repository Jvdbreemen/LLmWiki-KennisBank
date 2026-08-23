---
id: TASK-210
title: Verwijder de md5-herkenning uit _embeddings zodra de cache gemigreerd is
status: To Do
assignee: []
created_date: '2026-08-23 19:11'
labels:
  - hygiene
  - agent-geheugen
dependencies: []
ordinal: 174700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De sha256-overstap liet een enkele md5-aanroep staan: _legacy_bytes_hash. Die produceert nooit een nieuwe identiteit; hij VERIFIEERT alleen bestaande cache-entries zodat get_cached ze kan upgraden zonder opnieuw te embedden. Zonder dat pad kost de overstap ruim drie uur lokale GPU-tijd voor vectoren die bit-identiek zijn aan wat er al ligt.

Zodra geen enkele entry nog een text_hash van 8 tekens draagt, is het pad dood gewicht en kan het weg: _legacy_bytes_hash, _legacy_file_hash, en de twee migratietakken in get_cached.

Controleren zonder te raden:

  python3 -c "import json,collections,pathlib,os; c=json.loads(pathlib.Path(os.environ['KENNISBANK_VAULT'],'.claude/embeddings-cache.json').read_text('utf-8')); print(collections.Counter(len(e.get('text_hash','')) for e in c.values()))"

Staat daar alleen nog 16, dan is de migratie rond. Let op: entries migreren pas wanneer een aanroeper de cache wegschrijft, en dat doen alleen build-embed-index en build-kb-index. De hot loops in _maintenance en memory-sweep lezen wel maar schrijven nooit, dus reken op een paar dagen normale runs voordat de teller op nul staat.

Robert wil geen md5 in zijn codebases; deze aanroep is de laatste, en staat er alleen als overgangsmaatregel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Geverifieerd met de teller dat geen enkele cache-entry nog een text_hash van 8 tekens heeft
- [ ] #2 _legacy_bytes_hash, _legacy_file_hash en beide migratietakken uit get_cached verwijderd
- [ ] #3 Geen enkele hashlib.md5-aanroep meer in scripts/
- [ ] #4 Testsuite groen; de tests die legacy-entries construeren zijn mee verwijderd of omgezet
<!-- AC:END -->
