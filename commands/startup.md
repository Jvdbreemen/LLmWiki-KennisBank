Voer een sessie-check uit en geef een compact overzicht om de sessie mee te starten.

## Stap 1 — Systeemcheck (parallel uitvoeren)

1. **CCR status**: `ccr status`
2. **ANTHROPIC_API_KEY beschikbaar**: `echo ${ANTHROPIC_API_KEY:0:10}` — als leeg: hybrid niet actief
3. **Ollama modellen**: `ollama list`
4. **Backlog in progress**: gebruik `mcp__backlog__task_list` met filter `status:in_progress`
5. **Backlog todo**: gebruik `mcp__backlog__task_list` met filter `status:todo` (max 5)

## Stap 2 — Rapport

Geef een compact overzicht:

---

**[datum van vandaag]**

**Modus:**
- Als `ANTHROPIC_API_KEY` beschikbaar: `Hybrid (cloud + lokaal via CCR)` — gebruik `eval "$(ccr activate)"` + `claude`
- Als leeg: `Twee modi — cloud: \`claude\` | lokaal: \`ccr code\``
- Als CCR niet draait: meld dit + geef `ccr start`

**Ollama:** [namen van beschikbare modellen]

**Routing (als CCR actief):**
```
background  → gemma4:e4b   (lokaal)
default     → Sonnet 4.6   (cloud)
think       → Opus 4.7     (cloud)
longContext → gemma4:26b   (lokaal)
```

**In progress:**
- [TASK-id] Taakomschrijving — of: geen

**Todo (max 5):**
- [TASK-id] Taakomschrijving

---

Sluit af met één zin: meest logische volgende stap op basis van de backlog.

## Regels
- Geen uitleg, alleen het rapport
- Taal: Nederlands
- Geen em dashes
