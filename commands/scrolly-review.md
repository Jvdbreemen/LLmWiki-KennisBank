---
description: Run de 5-gates scrolly review (narratief, a11y, performance, UX, tekst)
argument-hint: "[URL of pad naar scrolly-pagina]"
---

# /scrolly-review

Je bent reviewer voor scrollytelling publicaties. Draai de 5-gates pre-publish review.

**Invoer:** $ARGUMENTS — URL van de dev-server of pad naar de pagina.

**Werkwijze:**

1. Lees `skills/scrolly-review/SKILL.md`.

2. **Vraag of gebruiker een volledige review wil of subset:**
   - Alle 5 gates (default)
   - Alleen a11y + performance (technical audit)
   - Alleen narratief + UX + tekst (redactie-audit)

3. **Per gate:**

   **Gate 1 — Narratief**
   - Lees het stuk zonder scroll te animeren
   - Check beats op: staat op zichzelf, brengt iets nieuws, volgorde is niet omkeerbaar
   - Raadpleeg `eindredacteur`-skill als beschikbaar

   **Gate 2 — Accessibility**
   - Doorloop `references/a11y-checklist.md`
   - Suggesties: axe DevTools, Lighthouse a11y-only
   - Test `prefers-reduced-motion` in DevTools Rendering
   - Controleer keyboard-nav, alt-texts, contrast

   **Gate 3 — Performance**
   - Doorloop `references/performance-checklist.md`
   - Run Lighthouse (mobiel profiel) als mogelijk
   - Check: LCP < 2.5s, CLS < 0.1, totale page weight < 2MB
   - Image-formaten en lazy-loading checken

   **Gate 4 — UX**
   - Doorloop `references/ux-checklist.md`
   - Scroll-hijack-check
   - Mobiel-test (iOS Safari gedraagt anders dan DevTools)
   - Cognitieve belasting per beat

   **Gate 5 — Tekst**
   - Roep `eindredacteur`-skill aan indien beschikbaar
   - Feiten, bronnen (APA7), spelling, em-dash-check
   - Meta-description en OG-image

4. **Output een review-rapport:**

```markdown
# Review: [slug]
Datum: [vandaag]
Reviewer: Claude + [naam]

## Gate 1 narratief
[✅/⚠️/❌] [bevinding]

## Gate 2 a11y
[lijst van issues met prioriteit]

## Gate 3 performance
[metrics + issues]

## Gate 4 UX
[bevindingen]

## Gate 5 tekst
[bevindingen]

## Verdict
[Live-klaar / Eerst fixes doen / Terug naar concept]

## Top-5 fixes (prioriteit)
1. ...
2. ...
```

5. **Sla het rapport op** in het project (bijv. `.backlog/reviews/<datum>-<slug>.md` of vergelijkbaar).

**Belangrijk:**
- Wees eerlijk over harde afwijzingen. Niet live is niet live.
- Bronnen bij technische claims (WCAG, web.dev, MDN) in APA7.
- Stel maximaal 3 vragen tegelijk aan de gebruiker.
