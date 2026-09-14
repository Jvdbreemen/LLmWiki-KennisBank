---
description: Scaffold een scrolly-implementatie (Hugo, React of Pageflow) op basis van een plan
argument-hint: "[hugo|react|pageflow] [slug of pad naar script]"
---

# /scrolly-scaffold

Je bent een implementatie-engineer voor scrollytelling. Gebruik de juiste skill om templates te scaffolden in de juiste stack.

**Invoer:** $ARGUMENTS — eerste arg is stack (`hugo`, `react`, of `pageflow`), tweede arg is slug of pad naar scrolly-plan.

**Werkwijze:**

1. **Als geen stack meegegeven:** vraag via AskUserQuestion welke stack (hugo / react / pageflow).

2. **Als geen plan meegegeven of gevonden:** vraag of er een plan is, of suggereer `/scrolly-plan` eerst te draaien.

3. **Per stack:**

   **Hugo:**
   - Lees `skills/scrolly-hugo/SKILL.md` en `references/dev-workflow.md`
   - Maak een feature-branch, backlog-taak (als backlog.md aanwezig)
   - Kopieer templates uit `templates/hugo/` naar:
     - `themes/<jouw-theme>/layouts/partials/scrolly-section.html`
     - `themes/<jouw-theme>/layouts/shortcodes/scrolly.html`
     - `themes/<jouw-theme>/assets/js/scrolly.js`
   - Voeg CSS toe uit `templates/hugo/scrolly.css` aan `themes/<jouw-theme>/assets/css/main.css`
   - Maak content-bundle in `content/tekst/<slug>/index.md` met front matter + scrolly-shortcodes
   - Draai `hugo` en controleer build

   **React:**
   - Lees `skills/scrolly-react/SKILL.md`
   - Vraag: BSMNT library of eigen primitives? (zie `references/bsmnt-vs-custom.md`)
   - Kopieer `templates/react/` naar het project
   - Instrueer npm install (gsap + optioneel @bsmnt/scrollytelling)
   - Genereer story-page met pattern uit plan

   **Pageflow:**
   - Lees `skills/scrolly-pageflow/SKILL.md`
   - Vraag welk render-target (Hugo of React)
   - Maak `data/stories/<slug>.yaml` of `stories/<slug>.json` gebaseerd op `references/voorbeeld-story.yaml`
   - Scaffold de chapter/scene-dispatcher (Hugo partials of React components)
   - Valideer schema met `ajv` (zie `references/schema.md`)

4. **Finish:**
   - Vat samen wat er is gemaakt en wat de vervolgstappen zijn (content invullen, images plaatsen, testen).
   - Suggereer `/scrolly-review` zodra het werkt.

**Belangrijk:**
- Nooit hardcoded styles -- alles via design tokens uit het actieve theme.
- Altijd reduced-motion fallback implementeren.
- Werk iteratief: scaffold eerst minimale versie, test, dan uitbouwen.
