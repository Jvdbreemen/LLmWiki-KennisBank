---
id: TASK-18
title: >-
  Promoot evidence_basis tot een ordinale trust-as in de ranking (yesmem-les:
  4-tier trust)
status: To Do
assignee: []
created_date: '2026-07-03 21:49'
updated_date: '2026-07-03 21:55'
labels: []
dependencies: []
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
STEEL-IDEE uit de KennisBank-vs-YesMem vergelijking (2026-07-03, research: ~/Claude/research/2026-07-03-kennisbank-vs-yesmem.md). YesMem gebruikt een 4-tier trust-hierarchie: user_stated > agreed_upon > claude_suggested > llm_extracted. User-input wint van geextraheerde feiten. Dat scheidt HERKOMST-autoriteit (wie/hoe is het vastgelegd) van nuttigheid — twee assen die wij nu door elkaar halen.

HUIDIGE STAAT (geverifieerd):
- _memory.py heeft AL een evidence_basis-veld: EVIDENCE_BASES = ('getypt','cc-sessie','audio','import','autoresearch','agent'), DEFAULT_EVIDENCE 'cc-sessie'. Dit is een CATEGORISCH veld (hoe vastgelegd), maar ONGEORDEND en het voedt de ranking NIET.
- Ranking (_rank.py) weegt memory-hits op relevance x recency (halfwaardetijd per memory_type) x importance (judge 1-5) x usage-boost. Trust/herkomst-autoriteit zit daar NIET in.
- Status is binair current/unverified (+ superseded/retracted/expired). Importance (1-5) meet 'hoe nuttig', niet 'hoe betrouwbaar de herkomst'.

HET IDEE: maak van evidence_basis een ORDINALE trust-as en laat die (licht) meewegen in de ranking, analoog aan YesMem's tiers. Een grove mapping van de bestaande categorieen naar een orde:
  getypt (mens typte het letterlijk) > cc-sessie/import/autoresearch (mens-in-de-lus bron) > agent (autonoom geextraheerd).
Dat spiegelt user_stated > agreed_upon > llm_extracted zonder een nieuw veld te hoeven verzinnen — de data staat er al.

WAAROM DIT PAST: het scheidt netjes wat we nu vermengen. importance = nuttigheid (judge), trust = herkomst-autoriteit (wie legde het vast). Een agent-geextraheerd feit en een door de mens getypt feit met dezelfde importance horen NIET identiek te ranken — het mens-getypte is betrouwbaarder. Dit is ook governance-conform: het verhoogt het gewicht van mens-autoriteit, precies onze lijn.

MOGELIJKE INGREPEN:
1. Definieer een TRUST_RANK-mapping over de bestaande EVIDENCE_BASES (getypt hoogst, agent laagst) in _rank.py, en voeg een kleine trust_factor toe (bv. 0.95-1.10, net als importance_factor) aan de memory-weging.
2. Overweeg of nieuwe evidence_basis-waarden nodig zijn (bv. 'agreed_upon' = door de mens bevestigd na agent-voorstel) of dat de bestaande zes volstaan (waarschijnlijk: status current+evidence_basis dekt 'agreed' al deels).
3. Meet met kb-eval memory-only: verbetert het de rang van mens-herkomst zonder de recall te schaden?

BEGRENZING/PRINCIPES: klein/begrensd (anti-runaway), deterministisch (de mapping is een lookup, geen LLM). GEEN nieuwe binaire status; dit is een RANKING-factor, geen filter. Verifieer eerst met een meting dat het loont — de embedding-ruimte is dun (zie TASK-15), dus rang-1 wordt gedomineerd door cosine; een trust-factor van +-10% verschuift alleen bij bijna-gelijke cosine-scores. Mogelijk marginaal effect; meet voor je bouwt.

Raakt: _rank.py (importance_factor is het directe model om te spiegelen), _memory.py (EVIDENCE_BASES), TASK-17 (beide zijn ranking-signaal-verfijningen, plan ze samen).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TRUST_RANK-mapping over de bestaande EVIDENCE_BASES gedefinieerd (getypt hoogst .. agent laagst), gedocumenteerd waarom die orde
- [ ] #2 trust_factor toegevoegd aan de memory-ranking (klein/begrensd, deterministische lookup, geen nieuw veld nodig)
- [ ] #3 kb-eval memory-only voor/na toont of mens-herkomst hoger rankt zonder recall-schade; bij marginaal effect gedocumenteerd als bewust-niet-doen
- [ ] #4 Geen nieuwe status/filter; dit is een ranking-factor. Geen LLM in het pad (de mapping is deterministisch)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CODE-VOORBEELDEN + YESMEM-BRONREFERENTIES (2026-07-03)

GEVERIFIEERD: evidence_basis wordt momenteel door NIETS gelezen voor ranking of stale.
grep evidence_basis scripts/stale-check.py -> geen treffer; _rank.py gebruikt het niet.
Het is nu een puur categorisch metadata-veld. De data staat er dus al maar is dood-gewicht -> precies de premisse van deze task.

YESMEM-MODEL (internal/storage/trust.go, Go, Apache-2.0):

  type TrustLevel int
  const ( TrustLow TrustLevel = iota; TrustMedium; TrustHigh )
  // ClassifyTrust(score): >=3.0 High, 1.0-2.99 Medium, <1.0 Low
  // TrustScore() combineert DRIE factoren:
  //   recall     = base 0.5 + log(1+hits), recency-scaled
  //   source-mult: user_stated 2.0 > agreed_upon 1.8 > claude_suggested 1.0 > llm_extracted 0.8
  //   importance = importance/3.0
  // TrustLevel stuurt supersede-gedrag:
  //   Low  -> supersede immediately
  //   Med  -> supersede with warning
  //   High -> only-as-proposal (pending_confirmation)

Let op: yesmem's TrustScore = recall x source x importance is bijna exact onze
relevance x recency x importance ranking, MAAR met de source-multiplier die wij missen.

HUIDIG (scripts/_memory.py):
  EVIDENCE_BASES = ("getypt", "cc-sessie", "audio", "import", "autoresearch", "agent")
  # ongeordend, voedt de ranking NIET.

HUIDIG model om te spiegelen (scripts/_rank.py, importance_factor):
  def importance_factor(importance) -> float:
      # 1-5 -> 0.9..1.1 (neutraal 3 = 1.0)
      imp = min(5, max(1, int(importance)))
      return 1.0 + 0.05 * (imp - 3)

VOORGESTELD (trust_factor, spiegelt importance_factor + yesmem's source-multiplier):
  # _rank.py: ordinale mapping over de BESTAANDE evidence_basis-waarden.
  # Orde spiegelt yesmem user_stated>agreed>llm_extracted:
  #   getypt (mens typte letterlijk)                    ~ user_stated
  #   cc-sessie / import / autoresearch (mens-in-lus)   ~ agreed_upon
  #   audio (transcriptie, mens-bron maar ruisig)       ~ tussen
  #   agent (autonoom geextraheerd)                     ~ llm_extracted
  TRUST_RANK = {"getypt": 2, "cc-sessie": 1, "import": 1, "autoresearch": 1,
                "audio": 1, "agent": 0}   # 2=hoog, 1=mens-in-lus, 0=autonoom
  def trust_factor(evidence_basis) -> float:
      t = TRUST_RANK.get(evidence_basis, 1)          # onbekend -> neutraal
      return 1.0 + 0.05 * (t - 1)                    # 0.95 .. 1.05, klein/begrensd

  # in rerank(): memory-hit score *= trust_factor(fm.get("evidence_basis"))
  # naast de bestaande recency/importance/usage-factoren.

BELANGRIJKE KANTTEKENING (uit TASK-15 meting): de embedding-ruimte is dun
(p99 pairwise cosine 0.577, mediaan 0.358). Rang-1 wordt gedomineerd door cosine;
een trust-factor van +-5% verschuift alleen bij bijna-gelijke cosine-scores.
Effect is mogelijk MARGINAAL. Meet met kb-eval memory-only voor je het houdt;
documenteer als bewust-niet-doen bij nul effect.

Bronbestanden yesmem:
- internal/storage/trust.go — TrustLevel, ClassifyTrust, TrustScore, source-multipliers.
- SYSTEM.md / configs/SYSTEM.md — de user_stated>agreed_upon>claude_suggested>llm_extracted tekst.
<!-- SECTION:NOTES:END -->
