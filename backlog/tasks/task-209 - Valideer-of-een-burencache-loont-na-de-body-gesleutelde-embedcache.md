---
id: TASK-209
title: 'Valideer of een burencache loont, na de body-gesleutelde embedcache'
status: To Do
assignee: []
created_date: '2026-08-23 10:41'
labels:
  - performance
  - agent-geheugen
dependencies: []
ordinal: 173700
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
De burenberekening (neighbour_map, drempel 0.75) is de langste pass van de sweep: gemeten 23m52s over 4077 memories, elke run opnieuw. Een cache lijkt aantrekkelijk, maar de invalidatie is verraderlijk: een NIEUWE memory verandert de burenlijst van BESTAANDE memories, dus een cache per pad wordt stil ongeldig. Dat is precies de faalvorm die deze codebase elders juist uitroeit.

Meet daarom eerst of het probleem na PR #158 (embedcache gesleuteld op de body ipv de filebytes) uberhaupt nog bestaat. Voor die fix zag een run 701 gewijzigde bestanden in 6 uur, maar het overgrote deel daarvan waren statuswissels unverified -> current die de vector niet raken. Verwachting, expliciet nog niet gemeten: het aantal memories met een ECHT gewijzigde vector per run valt terug van honderden naar tientallen. Klopt dat, dan is de burenkaart incrementeel bijwerken eenvoudiger en veiliger dan cachen met invalidatie, en is een cache overbodig.

Metingen die de beslissing dragen:
1. Aantal memories per sweep-run waarvan text_hash daadwerkelijk wijzigt (niet file_hash).
2. Tijd van neighbour_map bij die delta, tegen de 23m52s van een volledige herberekening.
3. Of _neighbours_from_index al genoeg schaalt: die pass gebruikt sqlite-vec en is aantoonbaar exact (vec0 sorteert op afstand, dus onder de drempel kan er niets meer boven zitten). De kosten zitten in 4077 opeenvolgende queries met een groeiend venster, niet in brute force.

Besluit expliciet ook de uitkomst 'geen cache bouwen'. Dat is een geldig resultaat en goedkoper dan een cache met een invalidatieregel die niemand kan uitleggen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Gemeten: aantal memories per run met een gewijzigde text_hash, na PR #158, over minimaal 3 sweep-runs
- [ ] #2 Gemeten: looptijd van neighbour_map bij die delta, afgezet tegen 23m52s voor de volle 4077
- [ ] #3 Beslissing vastgelegd met cijfers: incrementeel bijwerken, cachen, of niets doen
- [ ] #4 Als er gecacht wordt: de invalidatieregel is opgeschreven en dekt het geval dat een nieuwe memory de buren van bestaande memories verandert
<!-- AC:END -->
