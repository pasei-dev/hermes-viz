"""Round 3: one board per section, the wireframe/candlestick emitters, the overlap fixes, the Mermaid path."""

from python.derive import derive, match_candlestick, match_facts, match_files, match_wireframe, structure
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round2_answers import HEATMAP_ANSWER
from round3_answers import (
    CANDLE_ANSWER,
    DOTTED_PROSE,
    FLOW_ANSWER,
    TIMELINE_AND_FLOW,
    TWO_SECTIONS_ANSWER,
    WIREFRAME_ANSWER,
)

transform = agent.transform


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


# --- the wireframe and candlestick emitters ------------------------------------------------------


def test_the_wireframe_emitter_keeps_commas_and_colons_and_strips_the_reserved_chars():
    line = to_directive({"kind": "wireframe", "rows": [["Toolbar", "btn:3,field:1"]]})
    assert line == '::viz{k="wireframe" d="Toolbar=btn:3,field:1"}'

    # the block run is commas and colons — never a pipe — and `;` `=` `~` `|` `\` are stripped
    dirty = to_directive({"kind": "wireframe", "rows": [["Tool|bar", "btn:3;field=1~img:2\\card:1"]]})
    assert dirty == '::viz{k="wireframe" d="Tool bar=btn:3 field 1 img:2 card:1"}'


def test_the_candlestick_emitter_carries_the_ohlc_cells():
    line = to_directive({"kind": "candlestick", "rows": [["Mon", "12:18:9:16"]]})
    assert line == '::viz{k="candlestick" d="Mon=12:18:9:16"}'


def test_both_new_kinds_derive_from_an_answer():
    wireframe = derive(WIREFRAME_ANSWER, RULES, "wireframe", 4)
    assert [spec["kind"] for spec in wireframe] == ["wireframe"]
    assert wireframe[0]["rows"][0] == ["Toolbar", "btn:3,field:1"]
    assert wireframe[0]["title"] == "Layout"

    candles = derive(CANDLE_ANSWER, RULES, "candlestick", 4)
    assert [spec["kind"] for spec in candles] == ["candlestick"]
    assert candles[0]["rows"] == [["Mon", "12:18:9:16"], ["Tue", "16:21:14:20"], ["Wed", "15:19:11:18"]]


# --- the two heuristic overlaps that used to double-fire ------------------------------------------


def test_heatmap_and_bars_are_mutually_exclusive_on_the_same_run():
    both = [spec["kind"] for spec in derive(HEATMAP_ANSWER, RULES, "numbers,heatmap", 6)]
    assert both == ["heatmap"]  # heatmap wins …
    assert "bars" not in both  # … and bars stands down, so the run is emitted once

    # with the heatmap group off, there is no heatmap and bars keeps the run
    assert [spec["kind"] for spec in derive(HEATMAP_ANSWER, RULES, "numbers", 6)] == ["bars"]


def test_facts_and_files_are_mutually_exclusive_on_a_dotted_prose_label():
    assert match_files(DOTTED_PROSE) == []  # a.b is a prose label, not a path any more
    assert match_facts(DOTTED_PROSE)  # so facts is the one that fires

    # and the converse still holds: a real file list is files', never facts'
    files = ["src/derive.py: the matchers", "python/viz_dsl.py: the kinds", "rules.yaml: the rows"]
    assert match_facts(files) == []
    assert match_files(files)


def test_a_wireframe_block_run_is_not_also_a_fact():
    assert match_wireframe(["Toolbar: btn:3, field:1", "Sidebar: item:6, card:2"]) != []
    assert match_facts(["Toolbar: btn:3, field:1"]) == []
    assert match_candlestick(["Mon: 12:18:9:16"]) != []
    assert match_facts(["Mon: 12:18:9:16"]) == []


# --- the Mermaid path ----------------------------------------------------------------------------


def test_a_rows_only_spec_boards_while_a_body_carrying_one_becomes_a_fence():
    out = transform(TIMELINE_AND_FLOW, RULES, "timeline,flow", 3, "dark")
    assert out is not None

    boards = [line for line in out.splitlines() if line.startswith("::viz{")]
    assert len(boards) == 1
    assert "timeline:" in boards[0]  # a rows-only spec boards
    assert "flowchart" not in boards[0]

    # the arrow chain carries a body, so it is routed to a Mermaid fence instead of the board
    assert "```mermaid" in out
    assert "flowchart TD" in out
    assert "Request --> Auth --> Service" in out


# --- one board per section -----------------------------------------------------------------------


def test_each_section_band_rides_with_the_widgets_that_follow_it():
    groups = "structure,numbers,tables"
    out = transform(TWO_SECTIONS_ANSWER, RULES, groups, 8, "dark")
    assert out is not None

    boards = [line for line in out.splitlines() if line.startswith("::viz{")]
    assert len(boards) == 6  # one board per section band

    # heading, its own data, next heading — the band and its widgets are paired, never collected up top
    assert boards[0] == '::viz{k="board" d="section:Build report"}'
    assert boards[1].startswith('::viz{k="board" d="section:Board runs;l=2~bars:')
    assert boards[2].startswith('::viz{k="board" d="section:Timing;l=2~bars:')
    assert boards[3] == '::viz{k="board" d="section:Flash report"}'
    assert boards[4].startswith('::viz{k="board" d="section:Voltages;l=2~bars:')
    assert boards[5].startswith('::viz{k="board" d="section:Current draw;l=2~bars:')

    # level 1 is the answer's own division (the default, not carried); level 2 is a division within one
    assert "l=" not in boards[0] and "l=" not in boards[3]
    assert "Board runs;l=2" in boards[1] and "Timing;l=2" in boards[2]
    assert "Voltages;l=2" in boards[4] and "Current draw;l=2" in boards[5]


def test_the_paired_sections_never_change_a_word_and_are_idempotent():
    groups = "structure,numbers,tables"
    out = transform(TWO_SECTIONS_ANSWER, RULES, groups, 8, "dark")
    assert out is not None

    # every original line's text survives in order; the two bold pseudo-headings lose only their outer `**`
    originals = _nonblank(TWO_SECTIONS_ANSWER)
    for line in originals:
        word = line[2:-2] if (line.startswith("**") and line.endswith("**")) else line
        assert word in out, line
    kept = [line[4:] if line.startswith("### ") else line for line in _nonblank(out) if not line.startswith("::viz{")]
    expected = [line[2:-2] if (line.startswith("**") and line.endswith("**")) else line for line in originals]
    assert kept == expected

    # a second transform sees the directives and returns nothing
    assert transform(out, RULES, groups, 8, "dark") is None


def test_the_structure_specs_carry_a_level_and_a_position():
    _, sections = structure(TWO_SECTIONS_ANSWER, RULES, "structure")
    assert [spec["title"] for spec in sections] == [
        "Build report",
        "Board runs",
        "Timing",
        "Flash report",
        "Voltages",
        "Current draw",
    ]
    assert [spec["level"] for spec in sections] == [1, 2, 2, 1, 2, 2]
    assert [spec["at"] for spec in sections] == sorted(spec["at"] for spec in sections)


def test_a_flow_answer_never_reaches_a_board():
    out = transform(FLOW_ANSWER, RULES, "flow", 3, "dark")
    assert out is not None
    assert "::viz{" not in out
    assert "```mermaid" in out and "flowchart TD" in out
