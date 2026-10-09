"""Round 2: the twelve answer-shaped matchers and their emitters."""

from python.derive import MATCHERS, derive
from python.viz_dsl import to_board_directive, to_directive

from _agent import RULES
from round2_answers import (
    ARRAY_ANSWER,
    CHANGES_ANSWER,
    CHECKLIST_ANSWER,
    FACTS_ANSWER,
    FILES_ANSWER,
    HEATMAP_ANSWER,
    METRICS_ANSWER,
    OUTLINE_ANSWER,
    PARTS_ANSWER,
    RANGES_ANSWER,
    SETTINGS_ANSWER,
    TIMELINE_ANSWER,
)

CASES = [
    ("checklist", CHECKLIST_ANSWER, "checklist", [
        ["Read the archive", "done"],
        ["Verify the pin", "doing"],
        ["Flash the board", "todo"],
        ["Confirm the LED", "blocked"],
    ]),
    ("changes", CHANGES_ANSWER, "changes", [
        ["src/derive.py", "+120", "-8"],
        ["tests/test_hook.py", "+30", "-2"],
        ["rules.yaml", "+4", "-0"],
    ]),
    ("outline", OUTLINE_ANSWER, "outline", [
        ["1", "Agent half"],
        ["1.1", "Matchers"],
        ["1.2", "Emitters"],
        ["2", "Desktop half"],
        ["2.1", "Renderers"],
        ["2.2", "Themes"],
    ]),
    ("facts", FACTS_ANSWER, "facts", [
        ["Build", "passed on the first attempt"],
        ["DSP", "came up cleanly"],
        ["Codec", "needed a reflash"],
    ]),
    ("files", FILES_ANSWER, "files", [
        ["src/derive.py", "the round-2 matchers"],
        ["python/viz_dsl.py", "the twelve kinds"],
        ["rules.yaml", "the new rule rows"],
    ]),
    ("parts", PARTS_ANSWER, "parts", [
        ["U1", "MCU-1", "1"],
        ["U2", "74HC595", "2"],
        ["Y1", "24MHz", "1"],
    ]),
    ("settings", SETTINGS_ANSWER, "settings", [
        ["Telemetry", "on"],
        ["Autoflash", "off"],
        ["Verbose logs", "off"],
        ["Telemetry upload", "on"],
    ]),
    ("timeline", TIMELINE_ANSWER, "timeline", [
        ["2026-01-04", "First DSP boot", "12 ms"],
        ["2026-01-09", "Firmware flash", "1.4 s"],
        ["2026-02-02", "Audio path stable"],
    ]),
    ("ranges", RANGES_ANSWER, "ranges", [
        ["Temperature", "20..30"],
        ["Voltage", "3.2..3.6"],
        ["Duty cycle", "40..60"],
    ]),
    ("metrics", METRICS_ANSWER, "metrics", [
        ["Latency", "120 ms", "+5"],
        ["Throughput", "840", "+120"],
        ["Errors", "3", "-2"],
    ]),
    ("array", ARRAY_ANSWER, "array", [
        ["a", "b", "c"],
        ["1", "2", "3"],
        ["4", "5", "6"],
    ]),
    ("heatmap", HEATMAP_ANSWER, "heatmap", [
        ["Core 0", "3"],
        ["Core 1", "7"],
        ["Core 2", "5"],
        ["Core 3", "9"],
        ["Core 4", "2"],
        ["Core 5", "8"],
    ]),
]


def test_each_round2_matcher_fires_and_yields_its_rows():
    for group, text, kind, rows in CASES:
        specs = derive(text, RULES, group)
        assert len(specs) == 1, group
        spec = specs[0]
        assert spec["kind"] == kind, group
        assert spec["rows"] == rows, group


def test_every_round2_kind_has_a_matcher_in_the_table():
    assert set(MATCHERS) >= {kind for _, _, kind, _ in CASES}


def _emit(spec):
    line = to_directive(spec)
    assert line is not None, spec
    return line


def test_the_round2_emitters_encode_the_spec_payloads():
    checklist = derive(CHECKLIST_ANSWER, RULES, "checklist")[0]
    assert _emit(checklist) == (
        '::viz{k="checklist" d="Read the archive=done;Verify the pin=doing'
        ';Flash the board=todo;Confirm the LED=blocked" t="Flash checklist"}'
    )

    changes = derive(CHANGES_ANSWER, RULES, "changes")[0]
    assert _emit(changes) == (
        '::viz{k="changes" d="src/derive.py=+120=-8;tests/test_hook.py=+30=-2'
        ';rules.yaml=+4=-0" t="Changes"}'
    )

    outline = derive(OUTLINE_ANSWER, RULES, "outline")[0]
    assert _emit(outline) == (
        '::viz{k="outline" d="1=Agent half;1.1=Matchers;1.2=Emitters'
        ';2=Desktop half;2.1=Renderers;2.2=Themes"}'
    )

    facts = derive(FACTS_ANSWER, RULES, "facts")[0]
    assert _emit(facts) == (
        '::viz{k="facts" d="Build=passed on the first attempt;DSP=came up cleanly'
        ';Codec=needed a reflash" t="Facts"}'
    )

    files = derive(FILES_ANSWER, RULES, "files")[0]
    assert _emit(files) == (
        '::viz{k="files" d="src/derive.py=the round-2 matchers'
        ';python/viz_dsl.py=the twelve kinds;rules.yaml=the new rule rows" t="Touched files"}'
    )

    parts = derive(PARTS_ANSWER, RULES, "parts")[0]
    assert _emit(parts) == (
        '::viz{k="parts" d="h=Ref|Part|Qty;U1|MCU-1|1;U2|74HC595|2;Y1|24MHz|1" t="BOM"}'
    )

    settings = derive(SETTINGS_ANSWER, RULES, "settings")[0]
    assert _emit(settings) == (
        '::viz{k="settings" d="Telemetry=on;Autoflash=off;Verbose logs=off'
        ';Telemetry upload=on" t="Switches"}'
    )

    timeline = derive(TIMELINE_ANSWER, RULES, "timeline")[0]
    assert _emit(timeline) == (
        '::viz{k="timeline" d="2026-01-04=First DSP boot=12 ms'
        ';2026-01-09=Firmware flash=1.4 s;2026-02-02=Audio path stable" t="Events"}'
    )

    ranges = derive(RANGES_ANSWER, RULES, "ranges")[0]
    assert _emit(ranges) == (
        '::viz{k="ranges" d="Temperature=20..30;Voltage=3.2..3.6;Duty cycle=40..60" t="Windows"}'
    )

    metrics = derive(METRICS_ANSWER, RULES, "metrics")[0]
    assert _emit(metrics) == (
        '::viz{k="metrics" d="Latency=120 ms=+5;Throughput=840=+120;Errors=3=-2" t="Metrics"}'
    )

    array = derive(ARRAY_ANSWER, RULES, "array")[0]
    assert _emit(array) == '::viz{k="array" d="a|b|c;1|2|3;4|5|6"}'

    heatmap = derive(HEATMAP_ANSWER, RULES, "heatmap")[0]
    assert _emit(heatmap) == (
        '::viz{k="heatmap" d="Core 0=3;Core 1=7;Core 2=5;Core 3=9;Core 4=2;Core 5=8" t="Load"}'
    )


def test_a_grid_kind_joins_its_cells_with_a_pipe_and_a_value_kind_with_an_equals():
    # the BOM and the raw array are grids; everything else is label=value
    assert '|' in _emit(derive(PARTS_ANSWER, RULES, "parts")[0])
    assert '|' in _emit(derive(ARRAY_ANSWER, RULES, "array")[0])
    assert '|' not in _emit(derive(FACTS_ANSWER, RULES, "facts")[0])
    assert '|' not in _emit(derive(METRICS_ANSWER, RULES, "metrics")[0])


def test_the_emitter_strips_the_separators_not_the_renderer():
    from python.viz_dsl import clean_value

    assert clean_value("a;b|c=d~e\\f") == "a b c d e f"

    spec = {"kind": "facts", "rows": [["a;b|c=d~e\\f", "{g}"], ["h", "i=j"]], "title": "t;s|u"}
    line = _emit(spec)
    assert 'd="a b c d e f=g;h=i j"' in line
    assert 't="t s u"' in line
    assert "\\" not in line and "{" not in line[6:-1] and "}" not in line[6:-1]


def test_a_round2_entry_boards_fine():
    line = to_board_directive(derive(PARTS_ANSWER, RULES, "parts"))
    assert line == '::viz{k="board" d="parts:h=Ref|Part|Qty;U1|MCU-1|1;U2|74HC595|2;Y1|24MHz|1"}'
