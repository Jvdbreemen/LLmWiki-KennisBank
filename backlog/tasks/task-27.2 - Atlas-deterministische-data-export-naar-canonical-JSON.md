---
id: TASK-27.2
title: Atlas - deterministische data-export naar canonical JSON
status: To Do
assignee: []
created_date: '2026-07-11 16:43'
updated_date: '2026-07-11 16:43'
labels:
  - visualization
  - atlas
  - export
  - schema
dependencies:
  - TASK-27.1
parent_task_id: TASK-27
priority: high
ordinal: 31200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bouw `scripts/atlas-export.py`: een deterministische, read-only export die alle
vijf de KennisBank-stores inleest en samenvoegt tot één canonical JSON-model dat
de renderer (26.3) consumeert.

Bronnen en velden (read-only, nooit muteren):
- Memory (`09-memory/*.md` via `_memory.py`/`_frontmatter.py`): `title`,
  `memory_type`, `importance`, `status`, `evidence_basis`, `created`, `updated`,
  `valid_from`, `valid_until`, `superseded_by`, `tags`, afgeleide
  `provenance_tag`.
- Wiki (`02-wiki/*.md`): `title`, `status`, `tags`, `created`/`updated`,
  sessie-herkomst/provenance-links.
- Index (`.claude/kb-index.db` via `_kbindex.py`): `docs(path, layer, status,
  title, created)`. Geen embeddings in de output dumpen (privacy/omvang).
- Usage (`.claude/kb-usage.db` via `_usage.py`): `injected`, `used`,
  `last_injected`, `last_used` per stem (warmth).
- Activity (`.claude/kb-activity.db` via `_activity.py`): events met
  `event_time`/`captured_at`, `activity_kind`, afgeleide `state`, `entities`,
  `topic_tags`, `artifacts`, `confidence`, `source_kind`, `unknown_time`.
- Graph (`graphify-out/graph.json`): `nodes{id, source_file}`,
  `links{source, target, relation, confidence_score}`, optionele `hyperedges`;
  plus wikilinks uit de artikelen als fallback-edges.

Eisen:
- Join op bestandspad (`docs.path` = `activity_events.source_path` = graphify
  `source_file` = usage `stem`), zodat één node alle assen draagt.
- Deterministisch: dezelfde vault-staat levert byte-identieke JSON (stabiele
  sortering, geen tijd/rng in de payload behalve een expliciet meegegeven
  `generated_at`).
- Fail-open: ontbrekende store levert een warning en een lege sectie, geen
  traceback.
- Stdlib-first, read-only DB-access (WAL readers), geen clouddependency.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `atlas-export.py` leest memory, wiki, index, usage, activity en graph en emit één JSON met nodes (per bestandspad) en edges. Bewijs: run tegen een fixture-vault; JSON bevat nodes met velden uit elke store en edges uit wikilinks/graph.
- [ ] #2 De export is deterministisch: twee runs op dezelfde vault-staat geven identieke JSON (op `generated_at` na). Bewijs: golden-test die twee runs diff't en gelijkheid aantoont; `generated_at` wordt geinjecteerd, niet intern geklokt.
- [ ] #3 De pad-join werkt: een node die in meerdere stores voorkomt draagt memory-, activity- en usage-velden tegelijk. Bewijs: fixture met een artikel dat in kb-index, kb-usage en kb-activity voorkomt; test verifieert samengevoegde node.
- [ ] #4 Fail-open: ontbrekende `graph.json` of lege `kb-activity.db` levert warning + lege sectie, exit 0. Bewijs: test verwijdert/leegt een bron en verifieert nette output zonder crash.
- [ ] #5 Geen embeddings of ruwe transcript-inhoud in de JSON; alleen metadata/snippets. Bewijs: schema-assert in test dat verboden velden afwezig zijn.
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Unit tests met fixture-bronnen dekken elke store-extractor plus ontbrekende-bron cases. Bewijs: `python3 -m pytest tests/ -k atlas_export` groen.
- [ ] #2 Golden JSON-fixture is vastgelegd en een test bewaakt regressie tegen dat golden bestand.
- [ ] #3 JSON valideert tegen het schema uit TASK-27.1 (veld/type-check in test).
- [ ] #4 Script is read-only bewezen: test draait tegen een kopie en verifieert dat brondbestanden/DB's ongewijzigd zijn (mtime/hash).
<!-- DOD:END -->
