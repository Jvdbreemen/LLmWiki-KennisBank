# Atlas: drawer-navigatie (terug/vooruit) + inline memory-fragmenten

Datum: 2026-07-14
Status: goedgekeurd door Robert (sessie 2026-07-14)

## Probleem

Twee irritatiepunten uit dagelijks gebruik van de Atlas inspect-drawer:

1. Wikilink-navigatie in de drawer vervangt het document zonder weg terug —
   er is geen back-button, dus de leescontext is telkens kwijt.
2. Memory-ingangen onder een wiki-artikel vervangen bij een klik het hele
   artikel door het fragment, met hetzelfde geen-weg-terug-probleem. Fragmenten
   zijn kort; ze verdienen geen volledige paginanavigatie.

## Besluit

- **Terug + vooruit** (browser-stijl) in de inspect-drawer voor
  documentnavigatie.
- **Memory-fragmenten klappen inline uit** (accordion) onder hun
  entry-point-regel, in plaats van te navigeren. Overwogen alternatieven:
  float box (afgewezen: overlay/z-index-complexiteit zonder meerwaarde bij een
  accordion) en drawer-navigatie met alleen een back-button (afgewezen:
  leescontext raakt alsnog kwijt).

## Ontwerp

### 1. History in de inspect-drawer (`atlas/frontend/src/inspect.ts`)

- Twee stacks met documentpaden: `backStack`, `fwdStack`.
- Navigatie via wikilink of ander in-drawer pad: push huidig pad op
  `backStack`, leeg `fwdStack`, open het nieuwe pad.
- `←` / `→` knoppen in `insp-head` naast de titel; `disabled` wanneer de
  betreffende stack leeg is. Sneltoetsen Alt+← / Alt+→ zolang de drawer open
  is.
- Reset van beide stacks wanneer (a) de drawer sluit, of (b) een lens een
  nieuw root-document opent (klik vanuit graph/lijst = verse sessie); zo
  bestaat er geen stale history tussen contexten.

### 2. Inline memory-fragmenten (`inspect.ts` + `style.css`)

- Elke entry-point `<li>` wordt een accordion-item met `▸`/`▾`-indicator.
- Eerste klik: fragment lazy laden via bestaand `client.doc("09-memory/<stem>.md")`
  en renderen met de bestaande markdown-pipeline (markdown-it + DOMPurify,
  ongewijzigd sanitisatiepad). Resultaat per stem gecachet; toggelen daarna is
  gratis en zonder netwerk.
- Het artikel blijft staan; er is geen navigatie meer vanuit de memory-lijst.
- Wikilinks bínnen een uitgeklapt fragment gebruiken de gewone
  drawer-navigatie uit §1 (dus mét werkende terug-knop).
- Fail-soft: laadfout toont één foutregel in het accordion-item; het artikel
  blijft onaangetast.

### 3. Testen

- Unit (Vitest, naast bestaande `encoding.test.ts`): history-stackgedrag
  (push/back/forward/reset) als puur module-testje; accordion toggle +
  cachegedrag.
- Handmatig: artikel → wikilink → terug → vooruit; artikel → memory
  uitklappen → wikilink in fragment → terug.

## Scope en grenzen

- Alleen frontend; geen sidecar/backend-wijziging.
- Na implementatie wordt de Tauri-bundle (MSI/NSIS) opnieuw gebouwd zodat de
  standalone app de wijzigingen bevat (bestaande buildflow uit TASK-27.12).
- Out of scope: history persistent over drawer-sessies heen, deep-linking,
  memory-bewerkingen (drawer blijft read-only).
