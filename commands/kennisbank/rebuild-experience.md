# /kennisbank:rebuild-experience

Rebuild the derived experience projection from the separate append-only
`kb-experience-ledger.db`. Canonical events, outcomes and reviews remain in the
ledger; only `kb-experience-index.db` is built in staging and atomically replaced
after a complete successful build.

The selected vault must explicitly enable `experience_projection`. A missing,
false or unreadable setting returns `disabled` without loading an embedding
backend or touching either database. `--vault` selects the authority boundary;
otherwise `KENNISBANK_VAULT` is required. Custom database paths do not bypass
this check. This build capability does not enable either explicit recall route.

```bash
python3 "$KENNISBANK_VAULT/.claude/scripts/rebuild-experience.py" --progress
```

Use `--records-only` for a local lexical-only FTS projection. If Ollama or the
embedding backend is unavailable during an ordinary rebuild, the same complete
lexical fallback is published; there is no hosted fallback. `--incremental` is
accepted only as a deprecated compatibility flag and does not change full-rebuild
semantics. Other failures preserve the previous good projection. This command
does not modify the ledger, raw sources, memory files or skills. Retracted and
superseded records remain in the ledger audit trail and are not published as
recall results.
