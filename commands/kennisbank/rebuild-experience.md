# /kennisbank:rebuild-experience

Herbouwt de afgeleide experience-projectie uit het afzonderlijke, append-only
`kb-experience-ledger.db`. De canonical events, outcomes en reviews blijven in
het ledger staan; alleen `kb-experience-index.db` wordt in staging opgebouwd en
na een volledige succesvolle bouw atomisch vervangen.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/rebuild-experience.py" --progress
```

Gebruik `--records-only` om bewust een lokale lexical-only FTS-projectie te
bouwen. Als Ollama of de embedding-backend tijdens een normale rebuild niet
bereikbaar is, wordt dezelfde volledige lexical fallback gepubliceerd; er is
geen hosted fallback. `--incremental` wordt alleen nog geaccepteerd als
deprecated compatibiliteitsvlag en verandert de full-rebuild-semantiek niet.
Bij elke andere fout blijft de vorige goede projectie staan. De command wijzigt
geen ledger, raw source, memory-bestand of skill. Retracted en superseded records
blijven als gesloten auditsporen in het ledger bewaard en worden niet als recall-
resultaat gepubliceerd.
