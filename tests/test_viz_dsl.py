"""Emission: one brace-free paragraph under the cap, and Mermaid fences with the right header."""

from python.viz_dsl import (
    MAX_CELL_CHARS,
    MAX_DIRECTIVE_CHARS,
    clean_value,
    mermaid_fence,
    to_directive,
)

BARS = {
    "kind": "bars",
    "rows": [["Firmware", "42"], ["DSP", "28"], ["Codec", "14"]],
}

TABLE = {
    "kind": "table",
    "header": ["Board", "Runs"],
    "rows": [["291e", "42"], ["296e", "28"], ["208e", "17"]],
}

KPI = {
    "kind": "kpi",
    "rows": [["Builds", "128", "+12"], ["Fails", "3", "-1"]],
}

STEPS = {
    "kind": "steps",
    "rows": [["Read the archive"], ["Verify the pin"], ["Flash the board"]],
}


def _emit(spec):
    line = to_directive(spec)
    assert line is not None, spec
    return line


def test_the_four_spec_md_examples_encode_exactly():
    """SPEC.md's worked examples, re-encoded from a spec."""
    assert _emit({"kind": "bars", "rows": [["Firmware", "42"], ["DSP", "28"], ["Web", "18"]],
                  "unit": "%"}) == '::viz{k="bars" d="Firmware=42;DSP=28;Web=18" u="%"}'
    assert _emit({"kind": "kpi", "rows": [["Builds", "128", "+12"], ["Fails", "3", "-1"]]}) == (
        '::viz{k="kpi" d="Builds=128=+12;Fails=3=-1"}'
    )
    assert _emit({"kind": "table", "header": ["Board", "Runs"],
                  "rows": [["291e", "42"], ["223e", "17"]]}) == (
        '::viz{k="table" d="h=Board|Runs;291e|42;223e|17"}'
    )
    assert _emit({"kind": "steps", "rows": [["Read the archive"], ["Patch the entry"],
                                            ["Flash over EC3"]]}) == (
        '::viz{k="steps" d="Read the archive;Patch the entry;Flash over EC3"}'
    )


def test_bars_join_label_and_value_with_an_equals():
    assert _emit(BARS) == '::viz{k="bars" d="Firmware=42;DSP=28;Codec=14"}'


def test_a_table_carries_its_header_as_the_h_row_of_d():
    assert _emit(TABLE) == '::viz{k="table" d="h=Board|Runs;291e|42;296e|28;208e|17"}'


def test_kpi_carries_its_delta():
    assert _emit(KPI) == '::viz{k="kpi" d="Builds=128=+12;Fails=3=-1"}'


def test_steps_are_one_row_per_item():
    assert _emit(STEPS) == '::viz{k="steps" d="Read the archive;Verify the pin;Flash the board"}'


def test_title_unit_and_palette_ride_along():
    line = _emit(dict(BARS, title="Runs by board", unit="%", palette="light"))
    assert 't="Runs by board"' in line
    assert 'u="%"' in line
    assert 'p="light"' in line
    assert line.startswith('::viz{k="bars" d="')


def test_values_are_brace_free_and_carry_no_separators():
    assert clean_value("a;b|c=d{e}") == "a b c d e"
    assert clean_value("12\n34") == "12 34"
    assert clean_value('quo"ted') == "quo ted"
    assert clean_value("1\\2") == "1 2"
    assert len(clean_value("x" * 400)) <= MAX_CELL_CHARS

    spec = {"kind": "bars", "rows": [["a;b|c=d{e}", "12\n34"]], "title": 't"1', "unit": "a|b"}
    line = _emit(spec)
    body = line[len("::viz{") : -1]
    assert "{" not in body and "}" not in body and "\n" not in line
    assert 't="t 1"' in line
    assert 'u="a b"' in line


def test_a_header_cell_is_stripped_too():
    line = _emit({"kind": "table", "header": ["a;b|c", "d=e"], "rows": [["1", "2"]]})
    assert line == '::viz{k="table" d="h=a b c|d e;1|2"}'


def test_every_emitted_line_is_brace_free_and_under_the_cap():
    for spec in (BARS, TABLE, KPI, STEPS, dict(BARS, title="x", unit="%")):
        line = _emit(spec)
        assert len(line) <= MAX_DIRECTIVE_CHARS
        assert line.startswith("::viz{")
        assert line.endswith("}")
        assert "{" not in line[6:-1] and "}" not in line[6:-1]
        assert "\n" not in line


def test_a_spec_too_long_to_encode_is_trimmed_to_fit():
    spec = {
        "kind": "table",
        "header": ["Col A", "Col B"],
        "rows": [["row %d %s" % (i, "x" * 80), str(i)] for i in range(60)],
    }
    line = _emit(spec)
    assert len(line) <= MAX_DIRECTIVE_CHARS
    # the tail was dropped, the head was kept
    assert 'd="h=Col A|Col B;row 0' in line
    assert "row 59" not in line


def test_an_oversized_header_is_dropped_before_the_line_overflows():
    spec = {"kind": "table", "header": ["h" * MAX_CELL_CHARS] * 13, "rows": [["1", "2"]]}
    line = _emit(spec)
    assert len(line) <= MAX_DIRECTIVE_CHARS
    # the header row went with the value row, and the paragraph still stands
    assert "h=" not in line
    assert line == '::viz{k="table" d=""}'


def test_an_unknown_kind_is_sanitised_or_refused():
    assert _emit({"kind": "Bars!", "rows": [["a", "1"]]}) == '::viz{k="bars" d="a=1"}'
    assert to_directive({"kind": "!!", "rows": [["a", "1"]]}) is None
    assert to_directive({"kind": "", "rows": []}) is None


def test_mermaid_fence_bakes_the_palette_for_dark_and_light_and_leaves_mermaid_alone():
    spec = {"body": ["  A --> B", "  B --> C"]}

    dark = mermaid_fence("flowchart", spec, "dark")
    light = mermaid_fence("flowchart", spec, "light")
    plain = mermaid_fence("flowchart", spec, "mermaid")

    dark_lines = dark.splitlines()
    assert dark_lines[0] == "```mermaid"
    assert dark_lines[1].startswith("%%{init:{'theme':'base','themeVariables':{")
    assert dark_lines[1].endswith("}}}%%")
    assert "'primaryColor':'#1f2020'" in dark_lines[1]
    assert "'background':'transparent'" in dark_lines[1]
    assert dark_lines[2] == "flowchart TD"
    assert dark_lines[3:] == ["  A --> B", "  B --> C", "```"]

    assert "'primaryColor':'#f6f7f9'" in light
    assert "%%{init" not in plain
    assert plain.splitlines() == ["```mermaid", "flowchart TD", "  A --> B", "  B --> C", "```"]


def test_mermaid_fence_accepts_a_string_body():
    fence = mermaid_fence("pie", {"body": '  "a" : 1\n  "b" : 2'}, "dark")
    assert fence.splitlines()[-4:] == ["pie", '  "a" : 1', '  "b" : 2', "```"]
