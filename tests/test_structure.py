"""The structure layer: it adds headings around the answer and never touches a word of it."""

from python.derive import structure
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round2_answers import STRUCTURED_ANSWER

transform = agent.transform

BOLD_ONLY = "**Build report**\n\nThe flash ran on three boards.\n"
CAPTION_LIST = "### Notes\n\nTiming\n\n- Build: 42\n- Test: 18\n- Package: 7\n"
CAPTION_TABLE = "Board runs\n\n| Board | Runs |\n| --- | --- |\n| Alpha | 42 |\n| Beta | 28 |\n"


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_an_all_bold_line_gets_a_heading_and_section():
    out, sections = structure(BOLD_ONLY, RULES, "structure")
    # the heading carries the emphasis, so the `**` markers come off — no bold heading, and a
    # promoted anchor is written at its own level: a section is `##`, exactly as the prompt says
    assert out.splitlines()[0] == "## Build report"
    assert [spec["title"] for spec in sections] == ["Build report"]
    # the answer's own words are still there, in order
    assert _nonblank(out) == ["## Build report", "The flash ran on three boards."]


def test_a_caption_above_a_list_gets_a_heading():
    out, sections = structure(CAPTION_LIST, RULES, "structure")
    assert "## Timing" in out.splitlines()
    assert [spec["kind"] for spec in sections] == ["section"]


def test_a_caption_above_a_table_gets_a_heading():
    out, sections = structure(CAPTION_TABLE, RULES, "structure")
    assert out.splitlines()[0] == "## Board runs"
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
    """Every original line's text survives; only emphasis markers come off, and only on a promoted line.

    The property is exact: an all-bold line promoted to a heading loses its outer ``**`` (the marker
    supplies the emphasis); a non-bold caption promoted is byte-identical apart from the inserted marker;
    every other line is untouched.
    """
    out, sections = structure(STRUCTURED_ANSWER, RULES, "structure")
    originals = _nonblank(STRUCTURED_ANSWER)
    produced = _nonblank(out)
    assert len(produced) == len(originals)
    markers = ("## ", "### ")
    for original, got in zip(originals, produced):
        if got == original:
            continue
        if original.startswith("**") and original.endswith("**"):
            assert got == "## " + original[2:-2]  # the only permitted removal
        else:
            assert any(got == marker + original for marker in markers)  # marker only, bytes intact
    # exactly the one all-bold line was de-emphasised, and nothing was deleted or reordered
    assert "**Build report**" not in out
    assert len(sections) == 3


def test_inline_bold_inside_a_sentence_is_never_touched():
    """A `**bold**` phrase in a normal sentence keeps its markers — only all-bold lines are promoted."""
    text = "The **flash** ran on three boards\n\n- Build: 42\n- Test: 18\n"
    out, sections = structure(text, RULES, "structure")
    assert out.splitlines()[0] == "## The **flash** ran on three boards"
    assert out.count("**flash**") == 1


def test_structure_is_idempotent():
    once, first = structure(STRUCTURED_ANSWER, RULES, "structure")
    twice, second = structure(once, RULES, "structure")
    # a promoted `##`/`###` is a heading the answer now carries, so a second pass reads it back as the
    # same sections — and changes no byte of it, which is the property that matters: never a second
    # marker, never a word moved
    assert twice == once
    assert second == first
    assert [line.split()[0] for line in once.splitlines() if line.startswith("#")] == ["##", "###", "###"]


# --- through the hook ----------------------------------------------------------------------------


def test_the_hook_inserts_the_headings_and_boards_the_sections():
    groups = "structure,numbers,tables"
    out = transform(STRUCTURED_ANSWER, RULES, groups, 4, "dark")

    assert out is not None
    assert [line for line in out.splitlines() if line.startswith("#")] == [
        "## Build report", "### Board runs", "### Timing",
    ]
    assert "### **" not in out  # no heading is also bold

    # one board per section that has data, each landing under its own heading — and no band: the heading
    # is already on the page, and a `section:` entry here would print the same title a second time
    boards = [line for line in out.splitlines() if line.startswith("::viz{")]
    assert len(boards) == 2
    assert "section:" not in out
    assert out.index("### Board runs") < out.index(boards[0]) < out.index("### Timing")
    assert out.index("### Timing") < out.index(boards[1])

    # the derived runs are replaced in place; every other line's words survive untouched
    assert "| Board | Runs | Failures |" not in out
    assert "- Build: 42" not in out
    for surviving in ("## Build report", "The flash ran on three boards and every one came up.",
                      "### Board runs", "### Timing"):
        assert surviving in out, surviving


def test_no_heading_is_ever_drawn_twice():
    """The bug this round fixes: a heading the answer already renders is never also drawn as a band.

    Every derived section used to ride as a `section:` entry inside its board, so `## Builds` — or an
    inserted `### Builds` — stood on the page *and* inside a widget: the same words, twice.  Read the
    headings the answer ends up with and demand each of them appears exactly once outside the directives.
    """
    for answer in (
        "## Builds\n\nAlpha: 42\nDelta: 17\n",  # a markdown heading the answer already carries
        "**Builds**\n\nAlpha: 42\nDelta: 17\n",  # a bold pseudo-heading the layer promotes
        "**Firmware**\n\nprose only, no widget under this one.\n",  # a section with no data at all
        STRUCTURED_ANSWER,
    ):
        out = transform(answer, RULES, "structure,numbers,tables", 8, "dark")
        assert out is not None, answer
        headings = [line.strip().lstrip("#").strip() for line in out.splitlines()
                    if line.strip().startswith("#")]
        assert headings, answer
        for title in headings:
            # over the WHOLE answer, directives included: the doubling was the title sitting inside a
            # `section:` entry while the same words stood on the page
            assert out.count(title) == 1, "%r is drawn twice:\n%s" % (title, out)


def test_the_hook_is_idempotent_through_the_directive_guard():
    groups = "structure,numbers,tables"
    once = transform(STRUCTURED_ANSWER, RULES, groups, 4, "dark")
    assert once is not None
    assert once.count("::viz{") == 2  # one board per section that has data
    # a second pass sees the directive and does nothing, so headings never stack
    assert transform(once, RULES, groups, 4, "dark") is None


def test_structure_alone_still_returns_the_answer():
    out = transform("**Only a caption**\n\nprose follows.\n", RULES, "structure", 3, "dark")
    assert out is not None
    assert out.startswith("## Only a caption")
    # a section with no widget gets its heading and nothing else — never a band of its own
    assert "::viz{" not in out
    assert "prose follows." in out


def test_a_section_encodes_as_a_board_entry_and_a_directive():
    line = to_directive({"kind": "section", "title": "Board runs", "rows": []})
    assert line == '::viz{k="section" d="" t="Board runs"}'
