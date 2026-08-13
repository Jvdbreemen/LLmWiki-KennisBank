#!/usr/bin/env python3
"""_llmjson.py - JSON uit een modelantwoord halen dat niet alleen JSON is.

Elke seam deed dit hetzelfde: `raw[raw.find("{"):raw.rfind("}") + 1]`. Dat is
de BREEDST mogelijke snede, en daarmee precies de verkeerde. Een model dat na
zijn JSON nog even doorpraat --

    {"action": "ADD", "reason": "nieuw"}
    Ik heb hiervoor gekozen omdat {…} niet van toepassing was.

-- levert dan een snede die tot de laatste accolade in het NAPRAATJE loopt, en
de parse mislukt. Elke seam is fail-safe, dus dat mislukken is stil: extract
geeft [], reconcile geeft ADD, de judge geeft unverified. Gemeten in de
TASK-142-sweep: qwen3.5:9b deed dit twee keer in twintig aanroepen; de 4b geen
enkele keer in vierenvijftig.

De oplossing is niet breder maar smaller: pak het EERSTE complete object of
array, door de haakjes te tellen met besef van strings en escapes. Wat erna
komt is commentaar van het model, geen data.

Stdlib. Geen side-effects bij import.
"""
from __future__ import annotations

import json

_PAREN = {"{": "}", "[": "]"}


def _span_vanaf(raw: str, open_ch: str, vanaf: int) -> "tuple[int, int] | None":
    """(start, eind) van het eerste complete haakjespaar vanaf positie `vanaf`.

    Telt diepte en slaat alles binnen een string over, want een accolade in
    een reason-tekst ("gebruik {var} niet") hoort niet mee te tellen -- juist
    die maakt de brede snede zo onbetrouwbaar.
    """
    close_ch = _PAREN[open_ch]
    start = raw.find(open_ch, vanaf)
    if start < 0:
        return None
    diepte = 0
    in_string = False
    escaped = False
    for i in range(start, len(raw)):
        c = raw[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == open_ch:
            diepte += 1
        elif c == close_ch:
            diepte -= 1
            if diepte == 0:
                return start, i
    return None


#: Hoeveel openingshaakjes we hooguit proberen. Een model dat na twintig
#: kandidaten nog geen geldige JSON heeft geproduceerd, gaat dat ook niet meer
#: doen; de grens houdt een pathologisch antwoord goedkoop.
_MAX_KANDIDATEN = 20


def _parse(raw, open_ch: str, verwacht):
    tekst = str(raw or "")
    # ELK openingshaakje proberen, niet alleen het eerste. Een model dat zijn
    # antwoord inleidt met "Ik denk {even} na. {"action": "ADD"}" zet een
    # accolade VOOR de JSON; wie alleen de eerste probeert, pakt `{even}`,
    # faalt, en valt terug op de brede snede die ook faalt -- precies de stille
    # parse-fout die deze module moest wegnemen.
    vanaf = 0
    for _ in range(_MAX_KANDIDATEN):
        span = _span_vanaf(tekst, open_ch, vanaf)
        if not span:
            break
        try:
            waarde = json.loads(tekst[span[0]:span[1] + 1])
            if isinstance(waarde, verwacht):
                return waarde
        except Exception:
            pass
        vanaf = span[0] + 1
    # Terugval op de oude, bredere snede. Die is zwakker, maar hij kan een
    # geval oplossen dat de teller mist (bv. een niet-gesloten string ergens
    # achteraan) en nooit een geval breken dat de teller al oploste.
    s, e = tekst.find(open_ch), tekst.rfind(_PAREN[open_ch])
    if s >= 0 and e > s:
        try:
            waarde = json.loads(tekst[s:e + 1])
            if isinstance(waarde, verwacht):
                return waarde
        except Exception:
            pass
    return None


def first_object(raw) -> "dict | None":
    """Het eerste complete JSON-object in de tekst, of None."""
    return _parse(raw, "{", dict)


def first_array(raw) -> "list | None":
    """De eerste complete JSON-array in de tekst, of None."""
    return _parse(raw, "[", list)
