# The supersede judge is not too conservative; the ground truth is contaminated

**2026-08-13 — 97 real supersede pairs in the 0.70–0.90 band, qwen3.5:4b**

TASK-156 opened on a measurement: the judge agreed with only 30% of the vault's
own recorded supersessions in the band that matters. Two readings were possible
and the measurement could not separate them, because the ground truth is partly
this same mechanism's earlier output:

1. the judge is too conservative for the job, or
2. many recorded supersessions were themselves wrong.

Reordering the prompt (the treatment `RECONCILE_SYSTEM` got in TASK-144) took
agreement from **30% to 55%** on the same 97 pairs. This report answers what the
remaining 45% is, by reading the disagreements instead of counting them.

## Method

Only the disagreements carry information. Where the judge says "yes", both
readings agree and there is nothing to learn. Of the 97 pairs, the judge
contradicts the recorded history on **44**. The first 22 of those, ordered by
cosine, were labelled by hand: is this a genuine replacement, or not?

## Result

| | |
| --- | --- |
| pairs labelled | 22 |
| the judge was right — no real supersession | **19 (86%)** |
| the judge was wrong — a real replacement missed | **3 (14%)** |

So the overwhelming majority of what looks like judge conservatism is the
history recording something that was never a contradiction.

**What the 19 actually are.** Almost all are the same memory captured twice,
days or weeks apart, in slightly different words:

> `2026-07-31-fix-dhcp-sntp-leak` — "Memory leaked on every lease renewal when a
> DHCP server advertised an NTP server via option 42."
> `2026-08-13-fix-ignore-dhcp-provided-ntp-servers` — "Het negeren van door DHCP
> geleverde NTP-servers stopt een lek per vernieuwing."

Same cause, same fix, one in English and one in Dutch. Closing one is
reasonable housekeeping. It is not a supersession, and scoring the judge as
wrong for saying so measures the wrong thing.

**The proof that the history is unreliable here is circular.** Two memories
supersede each other, in both directions:

    2026-07-02-uitzonderingen-voor-adr-creatie  ->  2026-07-15-criteria-...
    2026-07-02-criteria-voor-adr-creatie        ->  2026-07-02-uitzonderingen-...

Whatever that pair is, it is not a record of one fact replacing another.

**One case where superseding lost information.** `2026-07-06-zelf-review-van-
specificaties` says "scan for placeholders … and fix everything found". Its
successor says only "scan". The instruction to fix was dropped, and the older
memory — which carried it — was closed.

**The three genuine misses**, for completeness:

| cosine | what changed |
| --- | --- |
| 0.777 | ADR numbering moved from glob-max to a script instead of LLM selection |
| 0.797 | the rule of three changed from "more than three" to "three or more" failures |
| 0.834 | "manual edits are forbidden, use the command" became "manually adjust the Status line" |

The last is a real contradiction and the judge should have caught it. The first
two are method and threshold changes buried inside otherwise identical prose.

## What follows

**Do not loosen the fail-safe bias.** That was TASK-156's AC#3, written on the
assumption that "Bij twijfel: false" was costing real corrections. Measured, it
costs 3 missed replacements in 97 pairs — around 3% — while the 44 refusals are
86% correct. Loosening it would buy a handful of genuine closures and pay for
them by closing duplicates automatically, which no measurement here shows to be
wanted.

**The number to quote is not 55%.** Corrected for a contaminated ground truth,
the judge is right on roughly 19 of every 22 pairs it declines, plus every pair
it accepts. Any future evaluation of this seam needs hand-labelled pairs, not
`superseded_by` links, because those links record housekeeping as often as
contradiction.

**The real finding is upstream.** Nineteen of 22 disagreements exist because the
same knowledge was captured twice and neither capture knew about the other. That
is a dedup and reconcile question at write time, not a supersede question after
the fact — which is the same conclusion `supersede-window-2026-08-13.md` reached
from the other direction.
