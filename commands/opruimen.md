---
description: Toon idle Claude-sessies en sluit gekozen sessies netjes (sessielog eerst, dan archiveren).
---

Doel: idle Claude-sessies opruimen zonder context te verliezen. Dit is de enige
betrouwbare manier om sessies te sluiten: alleen `list_sessions`/`archive_session`
(in-sessie) kennen de echte draai-status, en `archive_session` vraagt bewust per
sessie bevestiging.

## Wat "stil" betekent

Een sessie is stil als er in de laatste **6 uur geen prompt van de gebruiker** in staat.

Meet dit NIET met `lastActivityAt` en NIET met `isRunning`. Beide gaan door van
achtergrondwerk, hooks en agent-runs, en `isRunning` is alleen waar tijdens een
lopende beurt. Een sessie waarin de gebruiker tien minuten geleden nog een vraag stelde staat
daar gewoon als `isRunning: false`.

Lees in plaats daarvan het transcript
(`~/.claude/projects/<encoded-cwd>/<cliSessionId>.jsonl`) en pak de laatste regel
met `type: "user"` die echte tekst bevat. Sla over: `isMeta`, beurten die alleen
`tool_result` bevatten, en tekst die begint met `<` of `system-reminder` /
`Caveat:` bevat. Dat zijn allemaal machine-injecties, geen mens.

De koppeling sessie naar transcript loopt via
`~/Library/Application Support/Claude/claude-code-sessions/**/local_*.json`,
veld `cliSessionId`. De CCD-id (`local_<uuid>`) is NIET de CLI-id.

## Stappen

1. Roep `list_sessions` aan. Toon sessies gesorteerd op laatste prompt van de gebruiker
   (oudste eerst): nummer, titel, cwd, hoe lang geleden die prompt was, en
   `isRunning`. Markeer de huidige sessie en sla die over.

2. Vraag mij welke ik wil sluiten (losse nummers, of "alle stille").

3. Sessielog capturen per gekozen sessie. De directe route
   (`claude --resume <cliSessionId> --fork-session -p "/sessielog"`) werkt alleen
   als de CLI is ingelogd. Bij 401 (zie [[cli-oauth-revoked]]): gebruik de
   digest-route via CCR/OpenRouter. Comprimeer het transcript lokaal tot
   gebruikersprompts, slotfragmenten, gebruikte tools en aangeraakte bestanden
   (max ~60k tekens), stuur dat in een keer naar
   `http://127.0.0.1:3456/v1/messages` met model `openrouter,z-ai/glm-5.3-flash`
   en het template uit `$VAULT/04-templates/tpl-sessie-log.md`, en schrijf het
   resultaat naar `$VAULT/01-raw/sessies/raw-sessie-<sessiedatum>-<slug>.md`.
   Gebruik de datum van de sessie zelf, niet vandaag. Bij HTTP 500 (`ETIMEDOUT`
   op de upstream): gewoon opnieuw proberen, drie pogingen.

4. Verifieer dat het sessie-log er staat. Lukt dat niet: STOP voor die sessie,
   meld het, en archiveer NIET.

5. **Haal `list_sessions` opnieuw op vlak voor het archiveren.** Loggen kost
   tijd; in dat halfuur werkt de gebruiker door en start die nieuwe sessies. Archiveer
   nooit op een snapshot van voor de log-ronde. Draai ook stap "wat stil
   betekent" opnieuw over de verse lijst.

6. Draait er een sessie in een git-worktree, controleer dan voor het archiveren
   of die worktree schoon is en of de commits in de doelbranch zitten
   (`git merge-base --is-ancestor <commit> <branch>`). Archiveren ruimt de
   worktree op.

7. Pas dan `archive_session` aanroepen met de `sessionId` (ik bevestig per
   sessie).

8. Guards opruimen. Elk cozempic guard-proces draagt zijn sessie in de
   commandline (`--session <cliSessionId>`). Een guard is wees als die id niet
   voorkomt bij een niet-gearchiveerde sessie. Gebruik PPID niet als signaal: de
   guard daemoniseert zichzelf, dus ze staan allemaal op 1. Toon daarna
   `~/Claude/logs/janitor-status.json` als dat bestaat en vraag of ik de rest ook
   wil opruimen.

## Harde regels

- Nooit een sessie archiveren als de sessielog-stap (3/4) faalde.
- Nooit een sessie archiveren met een prompt van de gebruiker binnen 6 uur.
- Er is geen unarchive-tool. Ten onrechte archiveren kost de gebruiker handwerk in de
  sidebar. Twijfel je, laat staan en vraag.
