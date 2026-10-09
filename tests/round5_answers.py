"""Round-5 fixtures — an answer that genuinely nests, one that does not, and the five stated shapes.

Kept apart from the earlier fixture modules so those answers stay exactly as they were.
"""

#: A `##` section holding two `###` sub-headings, each with its own data, plus a state run and a
#: schedule.  Level 2 must fire on the `###` headings, and the two shapes must reach a Mermaid fence.
NESTED_ANSWER = """## Build report

The flash ran on three boards and every one came up.

### Timing

- Build: 42
- Test: 18
- Package: 7

### Failures

- Alpha: 1
- Beta: 0
- Gamma: 2

## Firmware states

Idle -> Running
Running -> Halted
Halted -> Idle

## Schedule

Build: 2026-01-04 .. 2026-01-09
Test: 2026-01-09 .. 2026-01-12
"""

#: The same kind of answer with nothing nested: one `##` heading, no `###` under it, no caption above
#: the list.  Level 1 only — a level 2 here would be invented.
FLAT_ANSWER = """## Build report

The flash ran on three boards and every one came up.

- Build: 42
- Test: 18
- Package: 7
"""

#: A bare caption above a table, under an open `##` — the caption is a division *within* the section.
CAPTION_UNDER_H2 = """## Flash report

Board runs

| Board | Runs |
| --- | --- |
| Alpha | 42 |
| Beta | 28 |
| Gamma | 17 |
"""

#: A run of named states with transitions — a Mermaid state diagram the text already states.
STATES_ANSWER = """### States

Idle -> Running
Running -> Halted
Halted -> Idle
"""

#: An exchange of messages — a Mermaid sequence diagram the text already states.
MESSAGES_ANSWER = """### Exchange

Client -> Server: GET /build
Server -> Client: 200 OK
"""

#: A schedule with dates — a Mermaid gantt the text already states.
SCHEDULE_ANSWER = """### Schedule

Build: 2026-01-04 .. 2026-01-09
Test: 2026-01-09 .. 2026-01-12
"""

#: Shares of one whole — 42 + 28 + 30 = 100, a Mermaid pie the text already states.
SHARES_ANSWER = """### Split

Firmware: 42%
DSP: 28%
Web: 30%
"""

#: Dated events — a Mermaid timeline the text already states.
DATED_ANSWER = """### Events

2026-01-04 - First DSP boot
2026-01-09 - Firmware flash
"""
