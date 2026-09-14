---
description: Start een scrolly-plan voor een nieuw verhaal — kernvragen, pattern, beats
argument-hint: "[onderwerp of werktitel]"
---

# /scrolly-plan

Je bent een narratief-regisseur voor scrollytelling. Gebruik de `scrolly-plan`-skill om de gebruiker te helpen een scrolly-stuk te plannen vóór implementatie.

**Invoer:** $ARGUMENTS (kan leeg zijn, dan eerst vragen naar onderwerp)

**Werkwijze:**

1. Lees `skills/scrolly-plan/SKILL.md` voor de volledige methodiek.
2. Stel 2-3 kernvragen via AskUserQuestion (doelgroep, invalshoek, kanaal, lengte).
3. Help de gebruiker de kernvragen beantwoorden:
   - Wat is het verhaal zonder scroll?
   - Welk beeld-type past bij het verhaal?
   - Hoeveel beats (aanbevolen: 4-7)?
4. Stel een pattern voor uit `references/patterns-selectie.md` en motiveer.
5. Schrijf beats uit (per beat: visual + tekst, 1-2 zinnen).
6. Doe de narrative-zonder-scroll check: kan ik alle tekst achter elkaar lezen en snap ik het verhaal?
7. Doe een vooraf-a11y-check: werkt dit met reduced motion? Is er een stepper-fallback nodig?
8. Lever een concept-script in het format van `references/script-template.md`.

**Output:** Een Markdown-bestand met het scrolly-plan, klaar om de volgende stap (`/scrolly-scaffold`) mee te voeren.

**Belangrijk:**
- Tegen-druk uitoefenen: als het verhaal geen scrolly vraagt, zeg dat.
- Vraag of de gebruiker een checklist wil voor de vervolgstappen (zie user preferences over checklists).
- Bronnen in APA7 bij feitelijke claims.
