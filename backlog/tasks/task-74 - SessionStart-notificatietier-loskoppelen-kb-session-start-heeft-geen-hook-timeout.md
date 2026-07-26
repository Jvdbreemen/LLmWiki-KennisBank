---
id: TASK-74
title: >-
  SessionStart-notificatietier loskoppelen; kb-session-start heeft geen
  hook-timeout
status: In Progress
assignee: []
created_date: '2026-07-25 20:35'
updated_date: '2026-07-25 22:38'
labels:
  - performance
  - hooks
  - sessiestart
dependencies: []
priority: medium
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Gemeten bij de /doctor-run van 2026-07-25: SessionStart heeft een mediaan van 2,3s maar een piek van 140.826 ms (141 s) over 7 runs in het venster.

Die piek komt NIET van het indexonderhoud. Dat is sinds TASK-63 al losgekoppeld: index-launch.py neemt een lock, spawnt een detached worker die memory-sweep en de drie bouwers sequentieel afwerkt, en keert direct terug; kb-session-start geeft die launcher 15s.

Wat er WEL blokkerend draait, met de caps uit kb-session-start.py en de hook-config:
  caveman-activate.js          5s
  kb-session-end-recover.py   35s
  index-launch.py (launcher)  15s
  memory-notify.py            30s
  distill-notify.py           30s
  git-upstream-check.py       15s
Opgeteld ~130s aan plafonds - wat verdacht goed past op de gemeten 141s.

TWEE OBSERVATIES:

1. De drie NOTIFICATIONS-jobs produceren een MEDEDELING, geen blokkerende voorwaarde. Een sessiestart hoeft niet te wachten op de uitkomst van een upstream-check of een destillatie-signaal; die kunnen net als het indexwerk detached, met hun uitkomst in een bestand dat de volgende sessiestart (of een expliciet commando) leest. Dat is dezelfde vorm die index-launch al gebruikt.

2. kb-session-start.py heeft in de settings GEEN hook-timeout. De som van de interne job-caps is daarmee het enige plafond, en dat plafond groeit stilzwijgend mee met elke job die erbij komt. Een expliciete hook-timeout is de vangnetregel die dat begrenst, los van wat het script intern doet.

Noord-ster 1 (CLAUDE.md): zware verwerking hoort off de interactieve weg. Een sessiestart die twee minuten kan duren is precies wat die regel wil uitsluiten.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 De drie NOTIFICATIONS-jobs (memory-notify, distill-notify, git-upstream-check) blokkeren de sessiestart niet meer
- [ ] #2 Hun uitkomst gaat niet verloren: de melding bereikt de gebruiker alsnog, op de eerstvolgende gelegenheid
- [x] #3 kb-session-start.py heeft een expliciete hook-timeout in de settings, als vangnet los van de interne job-caps
- [x] #4 Gemeten: mediaan en piek van SessionStart voor en na, via dezelfde transcript-analyse
- [x] #5 Volledige suite groen
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CORRECTIE OP DE EIGEN TAAKOMSCHRIJVING: de caps sommeren NIET. kb-session-start draait zijn jobs gelijktijdig via run_parallel (ThreadPoolExecutor), dus de blokkeertijd van een groep is het MAXIMUM, niet de som. De '~130s aan plafonds' in de beschrijving was verkeerd geredeneerd.

HOOFDOORZAAK GEVONDEN, en het is deploy-drift - niet een ontwerpprobleem.

De GEDEPLOYEDE kb-session-start.py in $VAULT/.claude/scripts is de versie van VOOR TASK-63:

  MAINTENANCE = (
      Job('build-embed-index.py'),      # default timeout 180s
      Job('build-kb-index.py'),
      Job('build-activity-index.py'),
      Job('sweep-launch.py', timeout=30),
  )

De repo koppelt dat sinds TASK-63 los via index-launch.py (lock + detached worker, launcher-cap 15s). Maar index-launch.py STAAT NIET IN DE VAULT. De sessiestart draait de drie indexbouwers dus nog altijd blokkerend, met de dataclass-default van 180s per job. Drie parallel met cap 180 verklaart de gemeten piek van 141s exact.

Vier scripts ontbreken in de deploy-kopie:
  index-launch.py       (TASK-63 - de fix zelf)
  _transcript.py
  strip-transcript.py
  build-graph-index.py  (nieuw vandaag, verwacht)

kb-session-start.py verschilt tussen repo en deploy.

METING 2026-07-25 (deploy-kopie, huidige situatie).

Per job, los als subprocess gestart zoals de coordinator het doet:
  memory-notify.py            701 ms
  distill-notify.py           218 ms
  git-upstream-check.py      1187 ms
  kb-session-end-recover.py   180 ms
  index-launch.py             ONTBREEKT
  som serieel  2285 ms | maximum (= parallelle groep) 1187 ms

Coordinator als geheel, koude start (state verwijderd): 35.734 ms.
De tweede meting (357 ms) is GEEN warme start maar een lock-afwijzing: de vorige run had de lock nog. Dat is een meetartefact, geen resultaat - vermeld zodat niemand die 357 ms als 'warm' overneemt.

PROJECTIE na deploy van de repo-versie: de MAINTENANCE-groep valt terug op alleen de launcher (lock nemen, detached spawnen, terugkeren - milliseconden), de NOTIFICATIONS-groep blijft en kost parallel ~1,2 s. Verwachte blokkeertijd onder de 2 s, ruim binnen het doel van 5 s.

CONSEQUENTIE VOOR DEZE TAAK: het loskoppelen van de notificatietier (AC #1) is daarmee GEEN voorwaarde meer om het doel te halen, maar extra marge. De echte fix is deployen wat er al ligt. AC #1 blijft nuttig maar zakt in prioriteit.

RISICO BIJ HET BEWIJZEN, expliciet benoemd: een koude start na de deploy spawnt de detached worker, en die draait memory-sweep. Volgens het onderzoek in TASK-73 is memory-sweep.py:284 (via _memory.unique_memory_path) het ENIGE schrijfpad dat -N-duplicaten maakt, en dat mechanisme is nog actief (jongste -2-paar 2026-07-23).

Het na-meten van de verbetering zou dus nieuwe duplicaten kunnen aanmaken in de geheugenlaag. Daarom niet zelf gedaan: eerst de collisie-check uit TASK-73 erin, dan deployen en meten.

RESULTAAT NA DEPLOY + STATUSREGEL (2026-07-25)

Gemeten met dezelfde methode als de nulmeting: state verwijderd (koude start), kb-session-start.py als subprocess met dezelfde payload, drie runs, mediaan.

                          voor        na
  koude start          35.734 ms   1.872 ms
  piek in transcripts 140.826 ms   n.v.t. (oorzaak weg)

Een tweede meetreeks gaf 2.633 ms mediaan. Dat verschil van 760 ms is NIET de statusregel: die is los gemeten op 33,7 ms, en worker_is_alive op 2,7 ms -- samen 36 ms van een budget van 250. De tweede reeks liep tijdens een volledige her-embedding van de vault (docs-telling liep zichtbaar op van 258 naar 731). Daarmee is het resultaat sterker dan het doel vroeg: ook TIJDENS een volledige herbouw blijft de start onder de 3 s.

DE STATUSREGEL -- drie bugs onderweg, alle drie stil

1. UnicodeEncodeError vrat de HELE uitvoer. _emit schreef met ensure_ascii=False naar een stdout die op Windows cp1252 is. Een bullet (U+00B7) als scheidingsteken gooide een UnicodeEncodeError, die de brede except in main() opslokte: rc=0, stdout 0 bytes, stderr leeg. Niet te onderscheiden van 'er was niets te melden'.
   Reikwijdte groter dan de bullet: kb-session-start geeft de uitvoer van ALLE kindscripts door. Een accent in een bestandsnaam of een typografisch aanhalingsteken uit een notify-melding liet het hele sessierapport verdwijnen. Van alle hooks die naar stdout schrijven waren kb-session-start.py:339 en quiet-hook.py:67 de enige twee met ensure_ascii=False; de rest gebruikt de veilige default. Beide omgezet naar ASCII-escapes -- de leeskant decodeert \uXXXX naar exact hetzelfde teken, dus dit kost niets.

2. Lock-bestaan is geen liveness. worker_running werd afgeleid uit lock.exists(). Gemeten: de lock bevatte PID 31772 terwijl de levende worker 22552 was. Een verweesde lock zou de regel voor altijd 'onderhoud draait al' laten beweren. Nu via index-launch.is_stale() -- het antwoord dat de partij die de lock beheert al gaf, inclusief afgeleide STALE_SEC en eigen bewakende test. Een tweede, PID-gebaseerd antwoord zou op een ander moment verlopen dan de eigenaar.

3. De doctelling was een verkeerd getal met stellige toon. Drie runs lazen 258, 262, 266 uit een tabel die op dat moment gevuld werd; de vault heeft er 1268. Tijdens draaiend onderhoud staat er nu '(bijwerken)' achter.

EXTRA: de regel meldt 'graaf niet geladen' wanneer er wel een graph.json op schijf staat maar de index hem niet kent. Dat maakte binnen een meting de regressie zichtbaar die nu als TASK-75 vastligt: een volledige herbouw van kb-index.db vernietigt de graaftabellen uit TASK-71.

Huidige regel in productie:
  KennisBank: onderhoud draait al | index 731 documenten (bijwerken), graaf niet geladen

Tests: tests/test_session_start_status.py, 20 stuks, groen. Waaronder test_statusregel_is_cp1252_veilig en test_emit_overleeft_niet_ascii_uit_een_kindscript (bug 1), test_verweesde_lock_telt_niet_als_draaiend en test_vervaltijd_komt_uit_index_launch (bug 2), test_telling_krijgt_voorbehoud_tijdens_onderhoud (bug 3).

AC #3 STAAT NOG OPEN, en het is dezelfde deploy-drift als de hoofdoorzaak. _hooks_manifest.TIMEOUTS declareert kb-session-start.py: 240, maar de SessionStart-entry in ~/.claude/settings.json heeft GEEN timeout-sleutel. Het manifest is de bron; hij is alleen nooit geland.

AC #1 (notificatietier loskoppelen) is bewust NIET gedaan. De metingen laten zien dat het doel zonder die wijziging gehaald wordt: de notificatiegroep kost parallel ~1,2 s. Het blijft nuttig als marge, maar het is geen voorwaarde meer. Weghalen of doorschuiven is een keuze voor Robert, niet voor mij.

ITERATIE 2 -- NETWERK VAN DE SESSIESTART-WEG (2026-07-25)

Eigen conclusie uit iteratie 1 bijgesteld. Ik schreef daar dat AC #1 'geen voorwaarde meer' was omdat het doel zonder die wijziging gehaald werd. Dat klopte alleen onder de omstandigheden waarin ik mat.

git-upstream-check.py regel 121 deed een `git fetch` -- een NETWERKAANROEP -- op de blokkerende sessiestart-weg. De 1.872 ms uit iteratie 1 is dus een meting bij een gezond netwerk. Bij een trage verbinding loopt die fetch door tot FETCH_TIMEOUT (8 s), en het jobplafond eromheen is 15 s. Een doel van '<3 s' dat alleen geldt bij goed weer is geen doel maar een gunstige meting.

GEMETEN, zelfde machine, drie runs, mediaan:
  git-upstream-check.py MET fetch      1.384 ms
  kale `git fetch --no-tags origin`      801 ms   (58% van de hook)
  git-upstream-check.py ZONDER fetch     493 ms   (-64%)
  git-fetch-refresh.py (achtergrond)   1.226 ms   buiten de wachttijd van de gebruiker

Koude sessiestart, vijf runs na de wijziging: 1.273 / 1.275 / 1.289 / 1.381 / 1.557 ms -- mediaan 1.289 ms, tegen 1.872 ms in iteratie 1 en 35.734 ms als nulmeting.

WIJZIGING, bewust kleiner dan AC #1 beschrijft:
  - refresh_remote() afgesplitst in git-upstream-check.py; main() doet geen fetch meer
  - nieuw scripts/git-fetch-refresh.py, tien regels, roept refresh_remote() aan
  - toegevoegd aan index-launch.JOBS (losgekoppelde worker, lock-beschermd)

Waarom niet de hele notificatietier verplaatsen: van de drie notify-scripts was de fetch de ENIGE netwerkaanroep. De rest is lokaal en kost milliseconden. Een eigen state-bestand met een staleness-contract oplossen wat twee regels code al oplossen, is de complexe variant van hetzelfde resultaat. AC #1 is daarmee NAAR DE GEEST vervuld (onbegrensde staart van de interactieve weg) maar NIET naar de letter (de drie scripts draaien nog synchroon). Dat verschil hoort Robert te wegen, niet ik.

GEVOLG dat expliciet vermeld moet worden: de drift-tellingen lezen nu de object store die de VORIGE achtergrondrun heeft bijgewerkt. 'main staat N commits achter' kan dus een sessie oud zijn. Voor een drift-waarschuwing is dat acceptabel; het is geen feit dat per seconde verandert.

AC #3 GELAND. `register-hooks.py ~/.claude/settings.json --manifest <vault>` uitgevoerd, met backup op ~/.claude/settings.json.bak-taak74-20260725-233042. Resultaat: kb-session-start.py timeout=240. Niets verwijderd -- geen legacy-scripts geregistreerd, caveman-hook (timeout 5) staat er ongemoeid bij.

Waarom 240 en niet strakker: eerst leek dat ruim tegenover een worst case van 45 s (MAINTENANCE max 15 + NOTIFICATIONS max 30, groepen serieel). Maar TIMEOUTS is EEN bron voor alle drie de installatiewegen, en het copilot-pad voegt kb-copilot-capture (30) en import-copilot (60) toe: worst case ~135 s. 240 is dus verdedigd, niet slordig. Constante ongemoeid gelaten.

HONESTE BEGRENZING VAN HET BEWIJS: gemeten pad is ~1,3 s; het GEDECLAREERDE plafond blijft 240 s. De hook-timeout begrenst een hang, niet de kosten van de code. '<3 s' is bewezen als meting over acht runs in twee condities (rustige machine en tijdens een volledige her-embedding), niet als afgedwongen invariant.

Tests: tests/test_git_upstream_check.py, 10 stuks, met test_main_doet_geen_fetch als kernregel. Plus test_index_launch (9) ongewijzigd groen.

SUITE GROEN -- 885 tests (2026-07-26)

  chunk aa                        256 tests   OK (1 skip)
  chunk ab                        215 tests   OK
  chunk ac                        180 tests   OK (1 skip)
  chunk ad zonder setup_deploy    212 tests   OK
  test_setup_deploy                22 tests   OK (3 batches: 318 s + 342 s + 261 s)
                                  ---------
                                  885 tests

In stukken gedraaid omdat een volledige run ~17 minuten kost en niet in een voorgrondvenster past; zie TASK-77.

DRIE MEETFOUTEN VAN MIJZELF, hier vastgelegd zodat ze niet terugkomen:

1. `python3 -m unittest ... | tail -25` -- in een pipeline is de exitcode die van TAIL, niet van unittest. Ik meldde op basis daarvan 'suite geslaagd, exitcode 0'. Dat was ongefundeerd. Bovendien houdt `| tail` alle uitvoer vast tot EOF, waardoor twee logbestanden leeg bleven terwijl de run wel liep.
2. `python3 -m unittest tests.X` zet tests/ NIET op sys.path; `discover -s tests` wel. Drie modules (test_slugify, test_vaultpath, test_zip_guard) leunen daarop en gaven `ModuleNotFoundError: No module named '_loader'`. Ik had die bijna als kapotte code gerapporteerd. Via discover: alle drie groen. Oplossing bij het draaien in stukken: PYTHONPATH=tests.
3. test_setup_deploy leek te hangen (>560 s). Het is geen hang: setup.sh duurt 42 s en de module roept run_setup() 18 keer aan.

ECHTE VONDST ONDERWEG -- flaky test hersteld:
test_register_hooks.LockStalenessTest.test_a_killed_cycle_recovers_within_one_ceiling viel een keer om onder belasting, en was daarna in isolatie en in twee herhalingen weer groen.

Mechanisme, direct getoetst in plaats van aangenomen: kb-session-start.acquire_lock rekent `age = now - lock.stat().st_mtime` en behandelt een NEGATIEVE age bewust als verlopen (regel 224, klokverzetting). De test gebruikte time.time() als tijdbasis terwijl de code de bestands-mtime gebruikt. Op Windows tikken beide klokken op ~15,6 ms; komt time.time() net VOOR de zojuist geschreven mtime uit, dan geldt een verse lock als verlopen en faalt de assertie 'een verse lock hoort te blokkeren'.

Bewijs: acquire_lock(lock, now=mtime) -> False (correct), acquire_lock(lock, now=mtime-0.001) -> True.

Fix in de TEST, niet in de code -- die age<0-clausule is bewust en gedocumenteerd. De test leest nu de mtime van de lock zelf als tijdbasis. Daarna 10/10 groen.

Deploy-pariteit gecontroleerd na afloop: kb-session-start.py, quiet-hook.py, git-upstream-check.py, git-fetch-refresh.py en index-launch.py zijn byte-gelijk aan de repo. Deploy-drift was de hoofdoorzaak van deze taak; die fout niet zelf herhalen.

STAND VAN DE CRITERIA: #3, #4 en #5 afgevinkt. #1 en #2 staan bewust open. De onbegrensde staart (netwerk) is van de interactieve weg af, wat de reden was dat ze er stonden -- maar de drie notify-scripts draaien nog synchroon, dus naar de LETTER zijn ze niet gehaald. Ze schrappen of alsnog uitvoeren is een keuze voor Robert.
<!-- SECTION:NOTES:END -->
