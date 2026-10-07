"""Round-2 fixtures — one answer per answer-shaped kind, and one that wants structure.

Kept apart from ``answers.py`` so the original fixtures stay exactly as they were.
"""

CHECKLIST_ANSWER = """### Flash checklist

- [x] Read the archive
- [/] Verify the pin
- [ ] Flash the board
- [!] Confirm the LED
"""

CHANGES_ANSWER = """### Changes

src/derive.py +120 -8
tests/test_hook.py +30 -2
rules.yaml +4 -0
"""

OUTLINE_ANSWER = """1. Agent half
1.1 Matchers
1.2 Emitters
2. Desktop half
2.1 Renderers
2.2 Themes
"""

FACTS_ANSWER = """### Facts

Build: passed on the first attempt
DSP: came up cleanly
Codec: needed a reflash
"""

FILES_ANSWER = """### Touched files

src/derive.py: the round-2 matchers
python/viz_dsl.py: the twelve kinds
rules.yaml: the new rule rows
"""

PARTS_ANSWER = """### BOM

| Ref | Part | Qty |
| --- | --- | --- |
| U1 | C8051F121 | 1 |
| U2 | 74HC595 | 2 |
| Y1 | 24MHz | 1 |
"""

SETTINGS_ANSWER = """### Switches

Telemetry: enabled
Autoflash: disabled
Verbose logs: off
Telemetry upload: on
"""

TIMELINE_ANSWER = """### Events

2026-01-04 — First DSP boot — 12 ms
2026-01-09 — Firmware flash — 1.4 s
2026-02-02 — Audio path stable
"""

RANGES_ANSWER = """### Windows

Temperature: 20..30
Voltage: 3.2..3.6
Duty cycle: 40-60
"""

METRICS_ANSWER = """### Metrics

Latency: 120 ms (+5)
Throughput: 840 (+120)
Errors: 3 (-2)
"""

ARRAY_ANSWER = """a | b | c
1 | 2 | 3
4 | 5 | 6
"""

HEATMAP_ANSWER = """### Load

Core 0: 3
Core 1: 7
Core 2: 5
Core 3: 9
Core 4: 2
Core 5: 8
"""

#: A realistic ~15-line answer with a bold pseudo-heading, a bare caption, a table, a list and numbers.
#: The structure layer should give the three caption lines a `### ` marker and nothing else.
STRUCTURED_ANSWER = """**Build report**

The flash ran on three boards and every one came up.

Board runs

| Board | Runs | Failures |
| --- | --- | --- |
| 291e | 42 | 1 |
| 296e | 28 | 0 |
| 208e | 17 | 2 |

Timing

- Build: 42
- Test: 18
- Package: 7
"""
