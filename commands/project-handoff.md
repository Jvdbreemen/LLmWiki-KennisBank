Genereer een complete handoff-map voor een project. Target: $ARGUMENTS (als leeg, gebruik de huidige werkdirectory).

Roep de `project-handoff` skill aan en volg de workflow uit `~/.claude/skills/project-handoff/SKILL.md`.

## Stappen

1. Bepaal het doelproject (argument of cwd)
2. Vraag om een korte 1-regel samenvatting als niet duidelijk uit project-context
3. Draai het inspectiescript:
   ```
   python3 ~/.claude/skills/project-handoff/scripts/handoff_inspect.py <project> --out /tmp/handoff-inventory.json
   ```
4. Controleer `inventory.json` op warnings. Potentiele secrets MOETEN worden uitgesloten, nooit meenemen.
5. Render de handoff:
   ```
   python3 ~/.claude/skills/project-handoff/scripts/render_handoff.py /tmp/handoff-inventory.json ~/.claude/skills/project-handoff/templates/ <output_dir> --summary "<1-regel>"
   ```
6. Default `output_dir` is `<project>/handoff/` tenzij de gebruiker iets anders zegt.
7. Verifieer completeness-checklist uit SKILL.md
8. Rapporteer: pad naar handoff-map, eventuele warnings, en de 6 bestanden die erin staan

## Regels

- Nooit echte secrets meenemen. Bij twijfel: uitsluiten en melden.
- Geen `{{` placeholders mogen achterblijven in de output. Verifieer voor rapporteren.
- Als `output_dir` al bestaat en inhoud heeft: vraag bevestiging voordat je overschrijft.
- Gebruik Nederlands in de 1-regel samenvatting tenzij het project duidelijk Engelstalig is.
