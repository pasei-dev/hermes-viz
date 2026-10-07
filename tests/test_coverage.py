"""Coverage: every kind the core draws renders, and every rule in rules.yaml fires and emits its kind.

The kinds themselves are rendered through the *real core* by ``node tests/desktop.test.mjs`` (its
`every kind renders a widget, not a fallback` walks all of ``KINDS``); this file proves the other
half — that every one of the 37 rules has an honest case that fires it, and that every kind a rule
emits is one the core can actually draw (or a Mermaid kind the app draws from a fence).
"""

import re
from pathlib import Path

from python.derive import STRUCTURE_MATCHERS, derive, structure
from python.viz_dsl import MERMAID_HEADERS

from _agent import RULES

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "desktop" / "render" / "core.mjs"


def _core_kinds():
    """The `KINDS` list off the drawing core — the kinds the plugin draws itself."""
    text = CORE.read_text(encoding="utf-8")
    block = text.split("const KINDS = [", 1)[1].split("]", 1)[0]
    return set(re.findall(r"'([a-z0-9-]+)'", block))


#: rule id -> (an answer that fires it with the rows its `min`/`max` ask for, the kind it emits).
FIRING = {
    "number-run-bars": ("- Build: 42\n- Test: 18\n- Package: 7\n", "bars"),
    "number-run-kpi": ("- Builds: 128\n- Failures: 3\n", "kpi"),
    "numeric-table-bars": (
        "| Board | Runs |\n| --- | --- |\n| 291e | 42 |\n| 296e | 28 |\n| 208e | 17 |\n",
        "bars",
    ),
    "steps-flow": ("1. Read the archive\n2. Verify the pin\n3. Flash the board\n", "steps"),
    "checklist-states": ("- [x] Read the archive\n- [/] Verify the pin\n", "checklist"),
    "changes-summary": ("src/derive.py +120 -8\ntests/test_hook.py +30 -2\n", "changes"),
    "outline-tree": ("1. Agent half\n1.1 Matchers\n1.2 Emitters\n", "outline"),
    "facts-card": (
        "Build: passed on the first attempt\nDSP: came up cleanly\nCodec: needed a reflash\n",
        "facts",
    ),
    "files-list": ("src/derive.py: the matchers\npython/viz_dsl.py: the kinds\n", "files"),
    "parts-bom": (
        "| Ref | Part | Qty |\n| --- | --- | --- |\n| U1 | C8051F121 | 1 |\n| U2 | 74HC595 | 2 |\n",
        "parts",
    ),
    "settings-flags": ("Telemetry: enabled\nAutoflash: disabled\n", "settings"),
    "timeline-events": (
        "2026-01-04 — First DSP boot\n2026-01-09 — Firmware flash\n",
        "timeline",
    ),
    "ranges-spans": ("Temperature: 20..30\nVoltage: 3.2..3.6\nDuty cycle: 40-60\n", "ranges"),
    "metrics-deltas": ("Latency: 120 ms (+5)\nThroughput: 840 (+120)\n", "metrics"),
    "array-grid": ("a | b | c\n1 | 2 | 3\n", "array"),
    "heatmap-ramp": ("".join("Core %d: %d\n" % (i, i * 3) for i in range(6)), "heatmap"),
    "wireframe-blocks": ("Toolbar: btn:3, field:1\nSidebar: item:6, card:2\n", "wireframe"),
    "candlestick-ohlc": ("Mon: 12:18:9:16\nTue: 16:21:14:20\n", "candlestick"),
    "flow-arrows": ("Request -> Auth -> Service\n", "flowchart"),
    "state-transitions": ("Idle -> Running\nRunning -> Halted\n", "state"),
    "sequence-messages": ("Client -> Server: GET /build\nServer -> Client: 200 OK\n", "sequence"),
    "gantt-schedule": (
        "Build: 2026-01-04 .. 2026-01-09\nTest: 2026-01-09 .. 2026-01-12\n",
        "gantt",
    ),
    "pie-shares": ("Firmware: 42%\nDSP: 28%\nWeb: 30%\n", "pie"),
    "dated-events": ("2026-01-04 - First DSP boot\n2026-01-09 - Firmware flash\n", "timeline"),
    "bracket-rounds": ("R16: Arsenal>Chelsea, Brentford>Leeds\nQF: Arsenal>Brentford\n", "bracket"),
    "gloss-lines": ("der Hund bellt=the dog barks=PRS.3SG\n", "gloss"),
    "forms-paradigm": (
        "| person | singular | plural |\n| --- | --- | --- |\n| 1st | habe | haben |\n| 2nd | hast | habt |\n",
        "forms",
    ),
    "funnel-stages": ("Visited: 1200\nSigned up: 340\nActivated: 180\n", "funnel"),
    "scatter-points": ("1=2.4\n2=3.1\n3=2.9\n", "scatter"),
    "waterfall-steps": ("Start: +120\nRefunds: -30\nNet: +45\n", "waterfall"),
    "records-rows": ("Pallet=12 crates of tile\nContainer=40 ft high cube\n", "records"),
    "grid-matrix": ("| Region | Q1 |\n| --- | --- |\n| North | 12 |\n| South | 9 |\n", "grid"),
    "events-stops": ("2026-03-01 - Kickoff\n2026-04-15 - Beta\n", "events"),
    "groups-repeats": ("Mon=Argon=Physics\nTue=Boron=Physics\n", "groups"),
}

#: The section rules emit through `structure`, not `derive`; each matcher needs one anchor it accepts.
SECTION_FIRING = {
    "section-bold": "**Build report**\n",
    "section-heading": "Board runs\n\n- Build: 42\n- Test: 18\n",
    "section-markdown": "## Build report\n",
}


def test_every_rule_has_an_honest_firing_case():
    covered = set(FIRING) | set(SECTION_FIRING)
    for rule in RULES:
        assert rule["id"] in covered, "no firing case for %s" % rule["id"]


def test_every_derived_rule_fires_and_emits_its_kind():
    for rule_id, (answer, kind) in FIRING.items():
        rule = next(rule for rule in RULES if rule["id"] == rule_id)
        kinds = [spec["kind"] for spec in derive(answer, RULES, rule["group"])]
        assert kind in kinds, "%s: %s" % (rule_id, kinds)
        assert rule["kind"] == kind, rule_id


def test_every_section_rule_fires_and_emits_a_section():
    for rule_id, answer in SECTION_FIRING.items():
        rule = next(rule for rule in RULES if rule["id"] == rule_id)
        matcher = STRUCTURE_MATCHERS[rule["when"]]
        assert matcher(answer.splitlines()), rule_id  # the matcher itself fires …
        _, specs = structure(answer, RULES, rule["group"])  # … and the rule emits a section
        assert [spec["kind"] for spec in specs] == ["section"], rule_id


def test_every_kind_the_rules_emit_is_one_something_can_draw():
    kinds = _core_kinds()
    assert len(kinds) == 41, "the core draws %d kinds" % len(kinds)
    for rule in RULES:
        kind = rule["kind"]
        assert kind in kinds or kind in MERMAID_HEADERS, "%s emits an undrawable %s" % (rule["id"], kind)


def test_the_kinds_no_rule_emits_are_the_directive_only_ones():
    """The core draws these; nothing derives them, so they arrive only through an explicit `::viz`."""
    rule_kinds = {rule["kind"] for rule in RULES}
    directive_only = _core_kinds() - rule_kinds
    assert directive_only == {
        "line", "donut", "table", "progress", "sparkline",
        "words", "recipe", "route", "nutrition", "matches",
        "pairs", "series", "stages",
    }
