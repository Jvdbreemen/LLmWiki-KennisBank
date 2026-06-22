Draag lokale tooling-verbeteringen uit deze gedeployde vault terug als upstream pull request. Argumenten: $ARGUMENTS

Dit commando is een launcher voor de `kennisbank-contribute` skill.

1. Gebruik de `kennisbank-contribute` skill en volg die exact. De skill isoleert lokale edits aan tooling (scripts, templates, commands, skills) in de gedeployde vault t.o.v. de geïnstalleerde release-tag, filtert persoonlijke vault-inhoud eruit (`CLAUDE.md`, `categories.json`, embeddings-cache, `*.bak`, vault-content `00-*`..`08-*`, `.kennisbank-version`), en opent er één pull request mee.
2. Geef `$ARGUMENTS` door aan de skill. Gebruik `--dry-run` om alleen de kandidaat-bestanden en de geplande branchnaam te tonen zonder branch, commit, push of PR.
3. Rapporteer de PR-URL (of de droogloop-lijst).
