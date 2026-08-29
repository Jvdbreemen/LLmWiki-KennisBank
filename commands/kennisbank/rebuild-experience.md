# /kennisbank:rebuild-experience

Herbouwt de outcome/experience-laag uit de append-only `experience_events` en
`experience_outcomes`. De afgeleide records en de lokale vector/FTS-projectie
worden eerst in staging opgebouwd en pas na succes atomisch vervangen.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/rebuild-experience.py" --progress
```

Gebruik `--incremental` om bestaande derived records te behouden en alleen
nieuwe sessie/taken toe te voegen. Gebruik `--records-only` wanneer alleen de
deterministische recordlaag nodig is en er geen lokale embedding-backend
beschikbaar is. Bij een fout blijft de vorige database staan. De command wijzigt
geen raw source, memory-bestand of skill; retracted/superseded records blijven
zichtbaar als gesloten auditsporen.
