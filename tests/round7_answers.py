"""Round-7 fixtures — one answer holding a genuine funnel, scatter and waterfall, and the same answer
with each shape *absent*, replaced by something that merely resembles it.

Kept apart from the earlier fixture modules so those answers stay exactly as they were.
"""

#: One real instance of each of the three new kinds: a narrowing run of signup stages, a run of numeric
#: x=y points, and a signed run that steps both up and down.
GENUINE_ANSWER = """## Acquisition

Visited: 1200
Signed up: 340
Activated: 180
Paid: 64

## Response times

1=2.4
2=3.1
3=2.9
4=4.1

## Cash flow

Start: +120
Refunds: -30
Costs: -45
Net: +45
"""

#: The same answer with the three shapes gone.  Each stand-in *resembles* one — a plain descending
#: list of unrelated counts (not a funnel), a `label=value` run and a two-column table (not a scatter),
#: and an unsigned count run (not a waterfall) — and must emit nothing.
ABSENT_ANSWER = """## Acquisition

Build: 42
Test: 18
Package: 7

## Response times

Firmware=42
DSP=28
Web=18

## Board

| Board | Runs |
| --- | --- |
| Alpha | 42 |
| Beta | 28 |

## Cash flow

Start: 120
Refunds: 30
Costs: 45
Net: 45
"""

#: A plain descending list — narrows exactly like a funnel but names no stage, so it stays `bars`.
PLAIN_DESCENDING = """Build: 42
Test: 18
Package: 7
"""

#: A `label=value` run — the left side is a word, so it is `bars`, never a scatter.
LABEL_VALUE_RUN = """Firmware=42
DSP=28
Web=18
"""

#: A two-column table is `array`; no `=` pair sits on a table row, so a scatter cannot fire.
TWO_COLUMN_TABLE = """| Board | Runs |
| --- | --- |
| Alpha | 42 |
| Beta | 28 |
"""

#: An unsigned count run is `bars`; the sign is what a waterfall is made of.
UNSIGNED_RUN = """Start: 120
Refunds: 30
Costs: 45
Net: 45
"""

#: Every amount is signed, but the run only ever rises — a waterfall steps *both* ways, so this is bars.
ALL_POSITIVE_SIGNED = """Start: +120
Raise: +30
Net: +150
"""
