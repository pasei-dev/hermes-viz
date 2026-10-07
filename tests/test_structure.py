"""The structure layer: it adds headings around the answer and never touches a word of it."""

from python.derive import structure
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round2_answers import STRUCTURED_ANSWER

transform = agent.transform

BOLD_ONLY = "**Build report**\n\nThe flash ran on three boards.\n"
CAPTION_LIST = "### Notes\n\nTiming\n\n- Build: 42\n- Test: 18\n- Package: 7\n"
CAPTION_TABLE = "Board runs\n\n| Board | Runs |\n| --- | --- |\n| 291e | 42 |\n| 296e | 28 |\n"


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_an_all_bold_line_gets_a_heading_and_section():
    out, sections = structure(BOLD_ONLY, RULES, "structure")
    assert out.splitlines()[0] == "### **Build report**"
    assert [spec["title"] for spec in sections] == ["Build report"]
    # the answer's own words are still there, in order
    assert _nonblank(out) == ["### **Build report**", "The flash ran on three boards."]


def test_a_caption_above_a_list_gets_a_heading():
    out, sections = structure(CAPTION_LIST, RULES, "structure")
    assert "### Timing" in out.splitlines()
    assert [spec["kind"] for spec in sections] == ["section"]


def test_a_caption_above_a_table_gets_a_heading():
    out, sections = structure(CAPTION_TABLE, RULES, "structure")
    assert out.splitlines()[0] == "### Board runs"
    assert sections[0]["title"] == "Board runs"


def test_prose_and_existing_headings_are_left_alone():
    assert structure("The board flashed cleanly.\n", RULES, "structure") == (
        "The board flashed cleanly.\n",
        [],
    )
    assert structure("### Already a heading\n\n- a\n- b\n", RULES, "structure") == (
        "### Already a heading\n\n- a\n- b\n",
        [],
    )


def test_a_line_ending_in_a_full_stop_is_not_a_caption():
    out, sections = structure(
        "The flash ran cleanly.\n\n- Build: 42\n- Test: 18\n- Package: 7\n", RULES, "structure"
    )
    assert sections == []
    assert out == "The flash ran cleanly.\n\n- Build: 42\n- Test: 18\n- Package: 7\n"


def test_a_fenced_block_is_never_restructured():
    fenced = "**Caption**\n\n```python\n**not a heading**\n- not a list\n```\n"
    out, sections = structure(fenced, RULES, "structure")
    assert [spec["title"] for spec in sections] == ["Caption"]
    assert "### **not a heading**" not in out
    assert "**not a heading**" in out


def test_the_group_switch_turns_the_whole_layer_off():
    assert structure(STRUCTURED_ANSWER, RULES, "numbers") == (STRUCTURED_ANSWER, [])
    assert structure(STRUCTURED_ANSWER, RULES, "") == (STRUCTURED_ANSWER, [])


# --- the safety property -------------------------------------------------------------------------


def test_never_rewords_or_deletes_property():
    """Every original line survives verbatim (as its own line, or inside the heading inserted for it)."""
    out, sections = structure(STRUCTURED_ANSWER, RULES, "structure")
    for line in _nonblank(STRUCTURED_ANSWER):
        assert line in out, line
    # nothing was deleted or reordered: strip the inserted marker and the answer is line-for-line intact
    originals = _nonblank(STRUCTURED_ANSWER)
    kept = [line[4:] if line.startswith("### ") else line for line in _nonblank(out)]
    assert kept == originals
    assert len(sections) == 3


def test_structure_is_idempotent():
    once, first = structure(STRUCTURED_ANSWER, RULES, "structure")
    twice, second = structure(once, RULES, "structure")
    assert twice == once
    assert second == []
    assert once.count("### ") == 3


# --- through the hook ----------------------------------------------------------------------------


def test_the_hook_inserts_the_headings_and_boards_the_sections():
    groups = "structure,numbers,tables"
    out = transform(STRUCTURED_ANSWER, RULES, groups, 4, "dark")

    assert out is not None
    assert "### **Build report**" in out
    assert "### Board runs" in out
    assert "### Timing" in out
    assert out.count("### ") == 3

    # one board per section: each band rides with the widgets that follow it, in reading order
    boards = [line for line in out.splitlines() if line.startswith("::viz{")]
    assert len(boards) == 3
    build, runs, timing = boards
    assert build == '::viz{k="board" d="section:Build report"}'
    assert runs.startswith('::viz{k="board" d="section:Board runs;l=2~bars:')
    assert timing.startswith('::viz{k="board" d="section:Timing;l=2~bars:')

    # the answer's own division is level 1 (the default, not carried); a division within one is level 2
    assert "l=" not in build
    assert "Board runs;l=2" in runs
    assert "Timing;l=2" in timing

    # and the answer's own words are untouched
    for line in _nonblank(STRUCTURED_ANSWER):
        assert line in out, line


def test_the_hook_is_idempotent_through_the_directive_guard():
    groups = "structure,numbers,tables"
    once = transform(STRUCTURED_ANSWER, RULES, groups, 4, "dark")
    assert once is not None
    assert once.count("::viz{") == 3  # one board per section
    # a second pass sees the directive and does nothing, so headings never stack
    assert transform(once, RULES, groups, 4, "dark") is None


def test_structure_alone_still_returns_the_answer():
    out = transform("**Only a caption**\n\nprose follows.\n", RULES, "structure", 3, "dark")
    assert out is not None
    assert out.startswith("### **Only a caption**")
    assert 'd="section:Only a caption"' in out


def test_a_section_encodes_as_a_board_entry_and_a_directive():
    line = to_directive({"kind": "section", "title": "Board runs", "rows": []})
    assert line == '::viz{k="section" d="" t="Board runs"}'
