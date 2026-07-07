---
id: TASK-21
title: 'Testsuite-hardening: hermeticiteit, coverage-meting en luide mock-asserties'
status: Done
assignee: []
created_date: '2026-07-03 23:27'
updated_date: '2026-07-06 20:56'
labels: []
dependencies: []
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
AANLEIDING (2026-07-04): de CI faalde op 2 stale tests in test_kb_retrieve_wiki (mock met oude wiki_hits-signatuur zonder expand -> TypeError door de fail-soft except opgeslokt -> test observeerde stil het fallback-pad i.p.v. het hybride pad). Bij het reproduceren bleek een tweede, dieper probleem: de volledige suite HANGT lokaal (>3 min, exit 143) op test_kb_retrieve_memory.KbRetrieveMemoryTest.test_memory_recall_on_without_index_still_no_crash. Die test raakt de ECHTE embed-endpoint (lokale Ollama, cold-load qwen3-embedding:8b). Op CI slaagt hij alleen omdat Ollama daar afwezig is -> connection-refused -> fail-soft. De test slaagt dus om de VERKEERDE reden (geen model i.p.v. geen index), en de suite is niet lokaal draaibaar waar Ollama up is.

Deze twee symptomen delen een wortel: te veel vertrouwen op fail-soft except-blokken die setup-fouten (verkeerde mock-signatuur, echte netwerk-call) STIL absorberen i.p.v. luid te falen. Dat verlaagt de effectieve dekking: een test kan groen zijn zonder de code-under-test te raken.

ONTWERP (gefaseerd, elk stukje klein/verifieerbaar):

1. HERMETICITEIT (grootste winst): dwing ALLE tests Ollama-blind af. Een gedeelde test-base/conftest die in setUp KB_EMBED_ENDPOINT + KB_LLM_ENDPOINT naar een dood adres pint (of emb.embed/generate mockt). Dan zijn CI en lokaal identiek en snel, en test je bewust de model-onbereikbaar-tak apart van de model-bereikbaar-tak. Verwijdert de hang.

2. LUIDE MOCK-ASSERTIES: waar een mock een fail-soft except kan raken (kb_recall.wiki_hits/has_fts_match/memory_hits, emb.embed), assert dat de mock DAADWERKELIJK is aangeroepen (unittest.mock.Mock + assert_called / call-count). Dan faalt een signatuur-drift (zoals expand) LUID op de plek van de fout i.p.v. stil door te vallen naar fallback. Dit had de CI-faal van vandaag bij de bron gevangen.

3. COVERAGE-METING in CI: draai 'coverage run -m unittest discover' + 'coverage report'. Meet de huidige lijn/branch-dekking, zet --fail-under net onder de baseline zodat regressies zichtbaar worden. Publiceer het getal (job-summary).

4. JOB-TIMEOUT: geef de CI-testjob een timeout-minutes zodat een toekomstige hang snel faalt i.p.v. de runner-limiet vol te draaien. Klein vangnet naast punt 1.

5. OPTIONEEL - INTEGRATIE-TIER: een kleine, apart-gemarkeerde integratietest (gated op KB_INTEGRATION=1, standaard geskipt op CI) die de ECHTE pijplijn draait (embed -> index -> retrieval) tegen een mini-fixture-vault. Zo dekt iets een keer het end-to-end pad dat nu alleen /kb-eval handmatig raakt, zonder de unit-CI te vertragen of te laten hangen.

BEGRENZING/PRINCIPES: fail-open in productie blijft (dat is bewust); dit gaat over de TESTS die fail-soft misbruiken om groen te zijn. Geen nieuwe test-dependency zonder noodzaak (coverage is stdlib-adjacent via 'coverage'; pytest-timeout alleen als punt 4 het echt vergt). Meet baseline voor je --fail-under zet.

Raakt: tests/ (base/conftest, mock-asserties), .github/workflows/ci.yml (coverage + timeout), scripts/_embeddings.py + _llm.py (endpoint-env-vars die de hermeticiteit mogelijk maken - bestaan al: KB_EMBED_ENDPOINT/KB_LLM_ENDPOINT).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Gedeelde test-base/conftest pint embed+LLM-endpoint dood (of mockt embed) zodat de volledige suite hermetisch is: draait lokaal EN op CI identiek, geen hang, geen echte netwerk-call
- [x] #2 Fail-soft-gevoelige mocks asserteren dat ze zijn aangeroepen (call-count), zodat signatuur-drift luid faalt op de bron i.p.v. stil naar fallback te vallen
- [x] #3 CI meet coverage (coverage run + report) met een --fail-under net onder de gemeten baseline; getal zichtbaar in de job-summary
- [x] #4 CI-testjob heeft timeout-minutes als hang-vangnet
- [x] #5 Optionele integratie-tier gated op KB_INTEGRATION=1 (default geskipt) draait de echte embed->index->retrieval-pijplijn tegen een mini-fixture; documenteer wel/niet-doen
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Testsuite-hardening is in de repo geland: `tests/__init__.py` pinnt de suite naar een hermetische, Ollama-blinde default; de retrieval-tests gebruiken luide mock-asserties; `.github/workflows/ci.yml` draait coverage met een fail-under en timeout. De opt-in integratietier blijft gated op `KB_INTEGRATION=1`, zodat de unit-CI snel en reproduceerbaar blijft.
<!-- SECTION:FINAL_SUMMARY:END -->
