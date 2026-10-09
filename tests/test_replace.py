"""The losslessness rule: a widget replaces its source in place, and only when it carries every word.

Both sides are pinned: a source the widget covers exactly is replaced where it stood; a source richer
than the rows is left as prose and emits no widget at all.
"""

from python.derive import derive

from _agent import RULES, agent

transform = agent.transform


#: Three plain `Label: 12` rows — the widget's own cells, nothing the emitter would strip.
COVERED = """### Timing

- Build: 42
- Test: 18
- Package: 7
"""

#: A source richer than the rows: the emitter squashes the `;` to a space, so the facts widget would
#: not carry the line faithfully.  The matcher still fires — the losslessness rule is what drops it.
RICHER_SEMICOLON = """### Notes

Build — one tagged release build from a clean tree; record the hex hash.
Test — run the suite on the pinned toolchain; keep the log.
Flash — write the image to the board; power-cycle the rig.
"""

#: A source richer than the rows the other way: every value runs past the emitter's 100-char cap, so
#: the tail of each line would be truncated away.
LONG_VALUE = "### Detail\n\n" + "".join(
    "Row %d: %s\n" % (i, "x" * 110) for i in (1, 2, 3)
)

#: One covered run (the table) beside one richer-than-rows run (the dashed prose): only the table is
#: replaced, so a widget never costs the answer a line it could not carry.
MIXED = """### Reports

| Board | Runs |
| --- | --- |
| Alpha | 42 |
| Beta | 28 |
| Gamma | 17 |

Build — one tagged release build from a clean tree; record the hex hash.
Test — run the suite on the pinned toolchain; keep the log.
Flash — write the image to the board; power-cycle the rig.
"""


def test_a_covered_source_is_replaced_in_place():
    out = transform(COVERED, RULES, "structure,numbers", None, "dark")

    assert out is not None
    # the three rows are gone; the widget stands exactly where they stood, under their heading
    assert "- Build: 42" not in out
    lines = out.splitlines()
    board = next(line for line in lines if line.startswith("::viz{"))
    assert "bars:Build=42;Test=18;Package=7" in board
    assert lines.index("### Timing") < lines.index(board)


def test_a_source_richer_than_the_rows_emits_no_widget():
    # the matcher does fire — so it is the losslessness rule, not a miss, that withholds the widget
    assert [spec["kind"] for spec in derive(RICHER_SEMICOLON, RULES, "facts")] == ["facts"]

    out = transform(RICHER_SEMICOLON, RULES, "facts", None, "dark")
    assert out is None  # nothing changed: the prose stays exactly as it was, no widget


def test_a_value_past_the_emitter_cap_also_emits_no_widget():
    assert [spec["kind"] for spec in derive(LONG_VALUE, RULES, "facts")] == ["facts"]
    assert transform(LONG_VALUE, RULES, "facts", None, "dark") is None


def test_in_one_answer_only_the_covered_run_is_replaced():
    out = transform(MIXED, RULES, "tables,facts", None, "dark")

    assert out is not None
    # the table is gone and its widget stands there …
    assert "| Alpha | 42 |" not in out
    assert "bars:h=Board|Runs;Alpha=42;Beta=28;Gamma=17" in out
    # … while every word of the richer run survives as prose
    for line in ("Build — one tagged release build from a clean tree; record the hex hash.",
                 "Test — run the suite on the pinned toolchain; keep the log.",
                 "Flash — write the image to the board; power-cycle the rig."):
        assert line in out, line


def test_the_replaced_board_is_never_also_left_as_prose():
    out = transform(COVERED, RULES, "structure,numbers", None, "dark")
    # no duplicate: a row appears either as its source line or as the widget, never both
    assert out.count("Build") == out.count("::viz{")  # once in the board, never in a surviving line
    assert "- Build: 42" not in out
