# Fase 4b Fix Report — agent-geheugen sweep review

## Findings & Changes

### IMPORTANT 1 — Watermark-burn bij model-outage (memory-sweep.py)
**Risico:** `_extract.extract_candidates` returnt `[]` zonder exception tijdens Ollama-outage → `ss.mark()` wordt toch aangeroepen → transcript permanent verloren.

**Fix:** `scripts/memory-sweep.py`
- Toegevoegd: `_model_reachable() -> bool` helper (regel 40-42): `bool(_llm.generate("ping"))`.
- In `run_sweep` (na de `memory_capture` gate): bouw eerst `pending_list`; als die niet leeg is én `_model_reachable()` faalt → zet `s["model_unreachable"] = True`, schrijf heartbeat, return zonder mark (regels 135-139).
- Nieuwe sleutels in `s`-dict: `embed_failed: 0`, `model_unreachable: False`.

**TDD RED→GREEN:** `test_model_down_marks_nothing` faalt (assert 0 > 0) op ongewijzigde code; slaagt na fix.

### IMPORTANT 2 — Stale-reclaim pad ongetest (test_sweep_launch.py)
**Fix:** `tests/test_sweep_launch.py`
- Toegevoegd: `test_stale_lock_is_reclaimed` — acquires lock, backdates mtime met `os.utime` naar `STALE_SEC+10` seconden terug, assert dat tweede `acquire_lock()` True teruggeeft.
- Toegevoegd: `test_future_mtime_treated_as_stale` — test fix BUG 5a.

### BUG 3 — Expire-pass: lenient match vs. strict mutate (memory-sweep.py)
**Probleem:** `str.replace("status: current", "status: expired", 1)` mist `status: "current"` (quoted); heartbeat telt nep-expiraties; body-match mogelijk.

**Fix:** `scripts/memory-sweep.py`, `_expire_pass()` (regels 58-90):
- Split bestand op `---` (max 2) om frontmatter-blok te isoleren.
- `re.sub(r"^status:.*$", "status: expired", fm_block, count=1, flags=re.MULTILINE)` op frontmatter-blok.
- Telt `n += 1` alleen als `new_txt != txt` (inhoud daadwerkelijk veranderd).
- Toegevoegd `import re`.

**Test:** `test_expire_quoted_status_flips_correctly` in `test_memory_sweep.py`.

### BUG 4 — Dedup uitgeschakeld bij embed-outage (memory-sweep.py)
**Probleem:** `if vec and su.is_duplicate(...)` short-circuit → kandidaat met `vec=None` wordt geschreven zonder dedup-check.

**Fix:** `scripts/memory-sweep.py`, binnen de kandidaat-loop (regels 154-156):
```python
if vec is None:
    s["embed_failed"] += 1
    continue
```
Dedup-check vervolgens zonder `vec`-guard (vec is nu zeker niet None).

**Noot:** Als embed-backend down is maar LLM up, slaagt de model-probe maar worden alle kandidaten overgeslagen via `embed_failed`. De transcript wordt dan wél gemarkeerd (subtiel residueel risico buiten de scope van de taak). BUG 4-fix voorkomt in elk geval het schrijven van un-dedupable herinneringen.

### BUG 5 — Lock TOCTOU + future-mtime deadlock (sweep-launch.py)
**Fix:** `scripts/sweep-launch.py`:
- `is_stale()`: `age = time.time() - mtime; return age > STALE_SEC or age < 0` — negatieve age (clock skew) wordt als stale behandeld.
- `acquire_lock()`: O_EXCL-first strategie — probeer direct `O_CREAT|O_EXCL`; bij `FileExistsError`: check staleness, unlink als stale, retry O_EXCL.

## Testcoverage toegevoegd

| Test | Bestand |
|------|---------|
| `test_model_down_marks_nothing` | test_memory_sweep.py |
| `test_per_transcript_error_increments_errors` | test_memory_sweep.py |
| `test_source_session_in_memory_frontmatter` | test_memory_sweep.py |
| `test_expire_quoted_status_flips_correctly` | test_memory_sweep.py |
| `test_stale_lock_is_reclaimed` | test_sweep_launch.py |
| `test_future_mtime_treated_as_stale` | test_sweep_launch.py |
| `test_block_text_none_content` | test_sweepstate.py |
| `test_block_text_mixed_list_only_text_extracted` | test_sweepstate.py |
| `test_is_duplicate_default_threshold_above` | test_sweeputil.py |
| `test_is_duplicate_default_threshold_below` | test_sweeputil.py |

## Full suite resultaat

```
203 passed in 116.67s
```

Alle tests groen, geen wijzigingen aan `_extract.py`, `_judge.py`, `_llm.py`, `_embeddings.py`, `_kbindex.py`, `kb-retrieve.py`.
