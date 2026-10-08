"""Round 7: funnel, scatter and waterfall — the actual last three.

The kind's payload encodes as SPEC says; each matcher fires only on the shape the text states and never
on the ordinary data it resembles; and the properties that must not regress stay green.
"""

from python.derive import derive
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round5_answers import NESTED_ANSWER
from round7_answers import (
    ABSENT_ANSWER,
    ALL_POSITIVE_SIGNED,
    GENUINE_ANSWER,
    LABEL_VALUE_RUN,
    PLAIN_DESCENDING,
    TWO_COLUMN_TABLE,
    UNSIGNED_RUN,
)

transform = agent.transform

#: The three groups this round adds — structure stays out of it, so nothing but the new kinds fires.
ROUND7 = "funnel,scatter,waterfall"


def _kinds(specs):
    return [spec["kind"] for spec in specs]


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


# --- the emitters, against the SPEC payloads -------------------------------------------------------


def test_the_round7_kinds_encode_the_spec_examples():
    assert to_directive({
        "kind": "funnel",
        "rows": [["Visited", "1200"], ["Signed up", "340"], ["Activated", "180"], ["Paid", "64"]],
    }) == '::viz{k="funnel" d="Visited=1200;Signed up=340;Activated=180;Paid=64"}'

    assert to_directive({
        "kind": "scatter",
        "rows": [["1", "2.4"], ["2", "3.1"], ["3", "2.9"]],
    }) == '::viz{k="scatter" d="1=2.4;2=3.1;3=2.9"}'

    assert to_directive({
        "kind": "waterfall",
        "rows": [["Start", "+120"], ["Refunds", "-30"], ["Costs", "-45"], ["Net", "+45"]],
    }) == '::viz{k="waterfall" d="Start=+120;Refunds=-30;Costs=-45;Net=+45"}'


def test_reserved_characters_are_stripped_from_the_new_kinds():
    # the parser cannot carry `; = ~ | \`, so a cell keeps its words and loses the separator
    assert to_directive({
        "kind": "funnel",
        "rows": [["Visited~", "1;200"]],
    }) == '::viz{k="funnel" d="Visited=1 200"}'

    assert to_directive({
        "kind": "scatter",
        "rows": [["1", "2;4"]],
    }) == '::viz{k="scatter" d="1=2 4"}'

    assert to_directive({
        "kind": "waterfall",
        "rows": [["Net", "+4=5"]],
    }) == '::viz{k="waterfall" d="Net=+4 5"}'


# --- the matchers fire on the shape, and not on its lookalike --------------------------------------


def test_a_narrowing_stage_run_derives_as_a_funnel():
    specs = derive(GENUINE_ANSWER, RULES, "funnel")
    assert _kinds(specs) == ["funnel"]
    assert specs[0]["rows"] == [
        ["Visited", "1200"],
        ["Signed up", "340"],
        ["Activated", "180"],
        ["Paid", "64"],
    ]


def test_a_plain_descending_list_is_not_a_funnel():
    # narrows exactly like a funnel, but `Build`/`Test`/`Package` name no stage of one process
    assert derive(PLAIN_DESCENDING, RULES, "funnel") == []


def test_a_non_decreasing_stage_run_is_not_a_funnel():
    # the stages are named, but the counts rise — a funnel narrows
    rising = "Visited: 1\nSigned up: 2\nActivated: 3\n"
    assert derive(rising, RULES, "funnel") == []


def test_a_single_stage_word_is_not_a_funnel():
    # one stage label among unrelated counts is not a staged run
    mixed = "Visited: 30\nOther: 20\nThing: 10\n"
    assert derive(mixed, RULES, "funnel") == []


def test_numeric_pairs_derive_as_a_scatter():
    specs = derive(GENUINE_ANSWER, RULES, "scatter")
    assert _kinds(specs) == ["scatter"]
    assert specs[0]["rows"] == [["1", "2.4"], ["2", "3.1"], ["3", "2.9"], ["4", "4.1"]]


def test_a_label_value_run_is_not_a_scatter():
    # a word on the left is a labelled count (`bars`), not a coordinate
    assert derive(LABEL_VALUE_RUN, RULES, "scatter") == []


def test_a_two_column_table_is_not_a_scatter():
    assert derive(TWO_COLUMN_TABLE, RULES, "scatter") == []


def test_two_numeric_pairs_are_not_a_scatter():
    # the rule's `min` of three rules out a couple of points
    assert derive("1=2.4\n2=3.1\n", RULES, "scatter") == []


def test_a_signed_up_and_down_run_derives_as_a_waterfall():
    specs = derive(GENUINE_ANSWER, RULES, "waterfall")
    assert _kinds(specs) == ["waterfall"]
    assert specs[0]["rows"] == [
        ["Start", "+120"],
        ["Refunds", "-30"],
        ["Costs", "-45"],
        ["Net", "+45"],
    ]


def test_an_unsigned_run_is_not_a_waterfall():
    assert derive(UNSIGNED_RUN, RULES, "waterfall") == []


def test_a_signed_run_that_only_rises_is_not_a_waterfall():
    # the sign is present, but nothing steps down — a waterfall steps both ways around its total
    assert derive(ALL_POSITIVE_SIGNED, RULES, "waterfall") == []


def test_bars_stands_down_where_a_round7_kind_claims_the_rows():
    # one dataset, one widget: with the numbers group on as well, the claimed run is not also `bars`
    funnel = "Visited: 1200\nSigned up: 340\nPaid: 64\n"
    assert [spec["kind"] for spec in derive(funnel, RULES, "numbers,funnel")] == ["funnel"]
    scatter = "1=2.4\n2=3.1\n3=2.9\n"
    assert [spec["kind"] for spec in derive(scatter, RULES, "numbers,scatter")] == ["scatter"]
    waterfall = "Start: +120\nRefunds: -30\nNet: +45\n"
    assert [spec["kind"] for spec in derive(waterfall, RULES, "numbers,waterfall")] == ["waterfall"]
    # with the group off there is no scatter spec, so the run stays `bars`
    assert [spec["kind"] for spec in derive(scatter, RULES, "numbers")] == ["bars"]


# --- the properties that must not regress ----------------------------------------------------------


def test_the_absent_answer_emits_nothing():
    # a descending list, a label=value run, a two-column table and an unsigned run are all lookalikes
    assert derive(ABSENT_ANSWER, RULES, ROUND7) == []
    assert transform(ABSENT_ANSWER, RULES, ROUND7) is None


def test_the_genuine_answer_emits_all_three_and_a_second_pass_returns_nothing():
    once = transform(GENUINE_ANSWER, RULES, ROUND7, max_widgets=None)
    assert once is not None
    # one board, three entries — the new kinds are board widgets, not diagrams
    for entry in ("funnel:", "scatter:", "waterfall:"):
        assert entry in once
    assert 'k="board"' in once
    assert transform(once, RULES, ROUND7, max_widgets=None) is None


def test_the_round7_transform_replaces_only_the_derived_runs():
    out = transform(GENUINE_ANSWER, RULES, ROUND7, max_widgets=None)
    assert out is not None
    # the funnel, the scatter points and the waterfall run are replaced in place …
    lines = out.splitlines()
    for gone in ("Visited: 1200", "1=2.4", "Start: +120"):
        assert gone not in lines, gone
    # … while every heading survives untouched
    for surviving in ("## Acquisition", "## Response times", "## Cash flow"):
        assert surviving in out, surviving


def test_the_round7_transform_does_not_disturb_the_structure_layer():
    # an answer whose headings are already markdown is left alone: the layer has nothing to insert, and
    # no band is drawn over a heading that already renders
    assert transform(NESTED_ANSWER, RULES, "structure,funnel,scatter,waterfall", max_widgets=None) is None
