# Explicit recall policy evidence — 2026-09-06

## Capability split

The settings schema now has four independent, default-off grants:

| Capability | Default | Authority granted |
| --- | --- | --- |
| `experience_capture` | off | append typed events and outcomes |
| `experience_projection` | off | build the reviewed derived index |
| `experience_explicit_recall` | off | answer an explicit experience query |
| `source_explicit_recall` | off | search sources or hydrate an exact SourceRef |

The broad legacy keys `source_recall` and `experience_recall` are no longer
defaults and are not consulted by either gateway. During settings migration an
old true value is preserved as unknown historical data, the replacement flags
are added as false, and stderr names the exact replacement choices. Unknown
keys remain intact; corrupt non-empty JSON is still left byte-for-byte
untouched.

Example migration:

```text
before: source_recall=true, experience_recall=true, future_setting=preserved
after:  all four new flags=false, legacy and future keys preserved
notice: legacy values activate nothing; choose replacement capabilities explicitly
```

## Public policy

The MCP server continues to expose its ten tools: `recall`, `source_recall`,
`experience_recall`, `capture`, `review_pending`, `review_decide`,
`what_did_i_do`, `timeline`, `weeklog`, and `topic_timeline`. The two deeper
recall tools retain read-only, closed-world annotations.

- Source MCP input is capped to 4,000 query characters, 20 hits and a 16 KiB
  structured SourceRef.
- Experience MCP input is capped to 4,000 query characters and three hits.
- Source permits `explicit`, `verify`, and `reconstruct` behavior.
- Experience permits `explicit` behavior only.
- Advisory, automatic fallback, ranking, promotion, hook and injection modes
  return `policy_disabled` before an optional backend is called.
- CLI gateways and MCP adapters use the same `policy_disabled`, `not_routed`,
  `disabled`, `unavailable`, `invalid`, `no_hit`, and `ok` vocabulary.

## Automated evidence

The settings, policy, MCP unit/wire, CLI, source, experience and projection
contracts completed with 96 passed tests. The targeted temporary-vault setup
test also passed, proving a fresh installation writes the new defaults. The
full setup module was not used as a gate because it redundantly rebuilds many
temporary installations; the scoped installation assertion covers the changed
artifact.

Negative-route tests compare the real CLI gateway status with the MCP adapter
status and assert `policy_disabled` for every forbidden mode. Separate tests
prove a legacy true-only settings file leaves both new gateways `disabled`.
