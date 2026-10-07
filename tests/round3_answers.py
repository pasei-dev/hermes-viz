"""Round-3 fixtures — the two new kinds, the Mermaid path, and the paired-sections answer.

Kept apart from ``answers.py`` and ``round2_answers.py`` so the earlier fixtures stay exactly as they
were.
"""

#: A UI mock: `Label: block:count, block:count` — the block run uses commas and colons, never a pipe.
WIREFRAME_ANSWER = """### Layout

Toolbar: btn:3, field:1
Sidebar: item:6, card:2
Footer: text:2, img:1
"""

#: OHLC candles: `when: open:high:low:close`.
CANDLE_ANSWER = """### Prices

Mon: 12:18:9:16
Tue: 16:21:14:20
Wed: 15:19:11:18
"""

#: An arrow chain — the one shape that genuinely wants a Mermaid diagram.
FLOW_ANSWER = """### Pipeline

Request -> Auth -> Service -> Store
Fetch -> Cache -> Render
"""

#: A rows-only `timeline` *widget* beside a body-carrying `flowchart`: the first boards, the second fences.
TIMELINE_AND_FLOW = """### Events

2026-01-04 — First DSP boot — 12 ms
2026-01-09 — Firmware flash — 1.4 s

### Pipeline

Request -> Auth -> Service
"""

#: A dotted prose label — `a.b` used to read as a file path.
DOTTED_PROSE = [
    "a.b: a dotted prose label",
    "x.y: another dotted one",
    "p.q: and a third",
]

#: A ~20-line answer with two clear sections, each holding a table and a list.
TWO_SECTIONS_ANSWER = """**Build report**

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

**Flash report**

The field image verified on two units.

Voltages

| Rail | Volts |
| --- | --- |
| 3V3 | 3.29 |
| 5V0 | 5.02 |
| 12V | 12.1 |

Current draw

- Idle: 21
- Peak: 84
- Average: 40
"""
