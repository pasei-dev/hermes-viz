"""The answering-format post-pass: the two repairs the model's own drawings still need.

Round 13 gives the agent half a narrow licence to act on an answer's own directives on a surface that
draws, and only for what is provable: the same drawing twice is drawn once, and no answer is given
more than `max_widgets` drawings — the model's own and the ones `transform` derives counted together.
Everything else is left exactly as written, so an answer that violates nothing is byte-identical.
"""

import re

from _agent import RULES, agent
from answers import STEPS_ANSWER
from python.shape import MERMAID_FENCE_RE, drawing_count, drawing_key, shape

make_hook = agent.make_hook

BARS = '::viz{k="bars" d="Budget=45;Actual=95"}'
BARS_TITLED = '::viz{k="bars" d="Budget=45;Actual=95" t="another caption"}'
KPI = '::viz{k="kpi" d="Builds=128;Fails=3"}'
STEPS = '::viz{k="steps" d="a;b;c"}'
FACTS = '::viz{k="facts" d="x=1;y=2"}'

MERMAID_A = "```mermaid\nflowchart TD\n  A --> B\n```"
MERMAID_B = "```mermaid\nflowchart LR\n  C --> D\n```"


def _directives(text):
    """Every `::viz` directive the text carries, verbatim."""
    return re.findall(r"::viz\{[^}]*\}", text)


# ------------------------------------------------------------------------------------------------
# the invariants

def test_an_answer_that_violates_nothing_comes_back_byte_identical():
    for text in (
        "Plain prose with no drawing at all.\n",
        "",
        "std::vector is not a directive.\n",
        "## Runs\n\n%s\n" % BARS,            # one drawing, well under any cap, no repeat
        "## Runs\n\n%s\n" % KPI,
    ):
        assert shape(text, 3) == text
        assert shape(text, None) == text


def test_prose_headings_tables_and_preview_are_never_touched():
    text = (
        "## Runs\n\nA table the answer wrote:\n\n"
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        '::preview{file="chart.html"}\n\n'
        "%s\n" % BARS
    )
    out = shape(text, 3)
    assert out == text
    assert "| A | B |" in out and '::preview{file="chart.html"}' in out


def test_the_pass_never_invents_a_directive():
    text = "## A\n\n%s\n\n%s\n\n%s\n\n%s\n" % (BARS, BARS_TITLED, KPI, STEPS)
    out = shape(text, 3)
    before = _directives(text)
    after = _directives(out)
    assert len(after) == 3
    assert all(d in before for d in after), "a directive appears that the answer never carried"


# ------------------------------------------------------------------------------------------------
# repair 2 — the same kind with the same payload is drawn once

def test_a_repeated_drawing_is_drawn_once():
    text = "## A\n\n%s\n\n%s\n" % (BARS, BARS)
    assert _directives(shape(text, 5)) == [BARS]


def test_a_repeat_is_the_same_kind_and_payload_even_with_a_different_title():
    # a `t=` (and a `u=`) is the widget's, not a new drawing: same kind, same rows, is a repeat
    text = "## A\n\n%s\n\n%s\n" % (BARS, BARS_TITLED)
    assert _directives(shape(text, 5)) == [BARS]


def test_a_different_payload_is_a_different_drawing():
    text = "## A\n\n%s\n\n::viz{k=\"bars\" d=\"a=1\"}\n" % BARS
    assert len(_directives(shape(text, 5))) == 2


def test_a_board_draws_once():
    text = '## A\n\n::viz{k="board" d="kpi:x=1~bars:a=2"}\n\n::viz{k="board" d="kpi:x=1~bars:a=2"}\n'
    assert _directives(shape(text, 5)) == ['::viz{k="board" d="kpi:x=1~bars:a=2"}']


# ------------------------------------------------------------------------------------------------
# repair 3 — no more than max_widgets drawings, the first in the answer's own order

def test_more_drawings_than_the_cap_keeps_the_first_in_order():
    text = "## A\n\n%s\n\n%s\n\n%s\n\n%s\n" % (BARS, KPI, STEPS, FACTS)
    out = shape(text, 3)
    assert _directives(out) == [BARS, KPI, STEPS]
    assert FACTS not in out, "the extra is dropped"
    # and the first three kept their order
    assert out.index(BARS) < out.index(KPI) < out.index(STEPS)


def test_a_cap_of_zero_drops_every_drawing():
    text = "## A\n\n%s\n\n%s\n" % (BARS, KPI)
    assert _directives(shape(text, 0)) == []
    assert "::viz" not in shape(text, 0)


def test_no_cap_keeps_every_distinct_drawing():
    text = "## A\n\n%s\n\n%s\n\n%s\n" % (BARS, KPI, STEPS)
    assert len(_directives(shape(text, None))) == 3


def test_a_repeat_does_not_spend_the_budget():
    # the repeat is dropped first, so the three *distinct* drawings all fit a cap of three
    text = "## A\n\n%s\n\n%s\n\n%s\n\n%s\n" % (BARS, BARS, KPI, STEPS)
    assert _directives(shape(text, 3)) == [BARS, KPI, STEPS]


# ------------------------------------------------------------------------------------------------
# the fences, and what a drawing is

def test_a_directive_inside_a_fenced_code_block_is_left_alone():
    text = "Shown:\n\n```\n%s\n```\n\n%s\n" % (BARS, BARS)
    # the fenced copy is grammar the reader is being shown, not a drawing: it is neither counted
    # nor touched, and the one bare directive is the only drawing — so the whole answer is unchanged
    assert shape(text, 1) == text
    assert drawing_count(text) == 1


def test_a_fenced_directive_does_not_consume_the_cap():
    text = "Shown:\n\n```\n%s\n```\n\n%s\n\n%s\n" % (STEPS, KPI, KPI)
    out = shape(text, 1)
    # the fenced one stays; the first bare KPI is kept and the repeat is dropped
    assert "```\n%s\n```" % STEPS in out
    assert out.count(KPI) == 1
    assert drawing_count(out) == 1, "the fenced directive is not a drawing"


def test_a_mermaid_fence_is_one_drawing():
    text = "## A\n\n%s\n\n%s\n" % (MERMAID_A, MERMAID_A)
    assert shape(text, 5).count("```mermaid") == 1, "the repeat diagram is dropped"


def test_two_different_mermaid_diagrams_are_two_drawings():
    text = "## A\n\n%s\n\n%s\n" % (MERMAID_A, MERMAID_B)
    out = shape(text, 1)
    assert out.count("```mermaid") == 1 and MERMAID_A in out and MERMAID_B not in out


def test_the_mermaid_fence_recogniser_matches_the_guide_s_fence():
    assert MERMAID_FENCE_RE.match("```mermaid")
    assert MERMAID_FENCE_RE.match("~~~mermaid")
    assert not MERMAID_FENCE_RE.match("```python")
    assert not MERMAID_FENCE_RE.match("prose")


def test_drawing_key_is_kind_and_payload_only():
    assert drawing_key({"k": "Bars", "d": "a=1", "t": "x", "u": "%"}) == ("bars", "a=1")


# ------------------------------------------------------------------------------------------------
# through the hook, on the desktop surface only

def test_the_hook_caps_the_models_own_directives():
    hook = make_hook(RULES, groups="steps,numbers", max_widgets=3, palette="dark")
    text = "## A\n\n%s\n\n%s\n\n%s\n\n%s\n" % (BARS, KPI, STEPS, FACTS)
    out = hook(text, platform="desktop")
    assert out is not None
    assert _directives(out) == [BARS, KPI, STEPS]


def test_the_hook_drops_a_repeated_drawing():
    hook = make_hook(RULES, groups="steps,numbers", max_widgets=3, palette="dark")
    text = "## A\n\n%s\n\n%s\n" % (BARS, BARS)
    out = hook(text, platform="desktop")
    assert out is not None and _directives(out) == [BARS]


def test_the_cap_counts_derived_and_authored_alike():
    """A diagram the model wrote and a board `transform` derives share the one budget."""
    hook = make_hook(RULES, groups="steps", max_widgets=1, palette="dark")
    text = "## X\n\n%s\n\n%s" % (MERMAID_A, STEPS_ANSWER)
    # the authored diagram already spends the only slot, so the derivation is handed none: no board
    assert hook(text, platform="desktop") is None
    assert drawing_count(text) == 1

    # given room for two, the derived board lands beside the model's diagram
    roomy = make_hook(RULES, groups="steps", max_widgets=2, palette="dark")
    out = roomy(text, platform="desktop")
    assert out is not None and MERMAID_A in out
    assert '::viz{k="board" d="steps:' in out


def test_the_hook_leaves_a_clean_desktop_answer_untouched():
    hook = make_hook(RULES, groups="steps,numbers", max_widgets=3, palette="dark")
    assert hook("## Runs\n\n%s\n" % BARS, platform="desktop") is None
    assert hook("Plain prose with no directive.\n", platform="desktop") is None


def test_the_post_pass_runs_on_demoted_text_too():
    """A valid directive beside one the core refuses is still bounded by the cap."""
    hook = make_hook(RULES, groups="steps,numbers", max_widgets=1, palette="dark")
    broken = '::viz{k="barz" d="a=1;b=2"}'
    text = "See:\n\n%s\n\n%s\n\n%s\n" % (broken, KPI, STEPS)
    out = hook(text, platform="desktop")
    assert out is not None
    assert "barz" not in out and "::viz" in out          # the refused one is demoted to markdown
    assert out.count("::viz{") == 1                      # the two drawable ones are capped to one
    assert KPI in out and STEPS not in out
