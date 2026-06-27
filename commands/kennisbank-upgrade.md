Upgrade deze KennisBank-vault naar de nieuwste officiële release-tag. Argumenten: $ARGUMENTS

Dit commando is een launcher voor de `kennisbank-upgrade` skill.

1. Gebruik de `kennisbank-upgrade` skill en volg die exact. De skill upgradet de gedeployde vault (`$KENNISBANK_VAULT`, fallback `~/KennisBank`) naar de nieuwste **release-tag** van LLmWiki-KennisBank (nooit bare `main`): controleer de upstream tag, toon de changelog tussen de geïnstalleerde en de nieuwste tag, waarschuw bij lokale tooling-edits (drift-guard, verwijst naar `/kennisbank-contribute`), back-up de huidige deploy, kopieer de nieuwe tooling volgens de deploy-map, stempel de versie-stamp, en verifieer met `doctor.sh`. `CLAUDE.md` wordt nooit overschreven.
2. Geef `$ARGUMENTS` door aan de skill. Gebruik `--dry-run` voor een droogloop die alleen de geplande kopieën en back-ups toont zonder iets te schrijven.
3. Rapporteer de geïnstalleerde tag en de `doctor.sh` PASS-count.
