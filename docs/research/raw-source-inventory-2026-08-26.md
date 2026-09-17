# Raw source inventory

Date: 2026-08-26
Vault: configured local KennisBank vault
Method: `scripts/dev/audit_raw_sources.py --progress`
Mutation: none; the scan read files and emitted aggregate counts only.

| measure | result |
| --- | ---: |
| approved text files | 16,255 |
| unreadable files | 0 |
| redacted-marked files | 0 |
| files missing session/timestamp/source metadata | 15,337 |
| duplicate SHA-256 hash groups | 2,784 |

## Root and type counts

| root | files |
| --- | ---: |
| `01-raw` | 1,408 |
| `05-bronnen` | 14,834 |
| `08-archive` | 13 |

| extension | files |
| --- | ---: |
| `.md` | 15,734 |
| `.jsonl` | 499 |
| `.txt` | 18 |
| `.json` | 4 |

## Interpretation

The corpus is large and mostly weakly labelled. A full embedding build would
therefore be expensive and would create false confidence around source
identity and temporal scope. The first source-recall evaluation must use a
reviewed provenance-rich subset and explicitly measure the oracle ceiling for
the remaining corpus. No full-vault build is approved by this inventory alone.
