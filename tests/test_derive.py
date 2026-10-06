"""Derivation: the rule table drives every widget, and nothing fires outside it."""

from python.derive import MATCHERS, derive, load_rules

from _agent import RULES, agent
from answers import (
    ANSWER_WITH_TABLE_AND_RUN,
    FENCED_CODE_ONLY,
    PROSE_ONLY,
    STEPS_ANSWER,
    TWO_ROW_RUN,
)

ALL_GROUPS = "numbers,tables,steps"


def _kinds(specs):
    return [spec["kind"] for spec in specs]


def test_rule_table_loads():
    assert [rule["id"] for rule in RULES] == [
        "number-run-bars",
        "number-run-kpi",
        "numeric-table-bars",
        "wide-table",
        "steps-flow",
    ]
    assert RULES[0] == {
        "id": "number-run-bars",
        "when": "number-run",
        "kind": "bars",
        "min": 3,
        "group": "numbers",
    }
    assert set(MATCHERS) >= {"number-run", "table", "steps-list", "key-numbers"}


def test_every_rule_matcher_is_implemented():
    for rule in RULES:
        assert rule["when"] in MATCHERS, rule["id"]


def test_table_and_number_run_yield_the_expected_specs():
    specs = derive(ANSWER_WITH_TABLE_AND_RUN, RULES, ALL_GROUPS, max_widgets=3)

    # one widget per firing rule, in table order: number-run-bars, numeric-table-bars, wide-table
    assert _kinds(specs) == ["bars", "bars", "table"]

    run = specs[0]
    assert run["rows"] == [["Build", "42"], ["Test", "18"], ["Package", "7"]]
    assert run["title"] == "Timing"
    assert run.get("header") is None

    table = specs[2]
    assert table["header"] == ["Board", "Runs", "Failures"]
    assert table["rows"] == [["291e", "42", "1"], ["296e", "28", "0"], ["208e", "17", "2"]]
    assert table["title"] == "Board runs"


def test_prose_only_yields_nothing():
    assert derive(PROSE_ONLY, RULES, ALL_GROUPS) == []


def test_a_fenced_code_block_never_yields_anything():
    assert derive(FENCED_CODE_ONLY, RULES, ALL_GROUPS) == []


def test_a_rule_group_switched_off_stops_its_rules():
    tables_only = derive(ANSWER_WITH_TABLE_AND_RUN, RULES, "tables")
    assert _kinds(tables_only) == ["bars", "table"]
    assert all(spec["title"] == "Board runs" for spec in tables_only)

    numbers_only = derive(ANSWER_WITH_TABLE_AND_RUN, RULES, "numbers")
    assert _kinds(numbers_only) == ["bars"]
    assert numbers_only[0]["title"] == "Timing"

    assert derive(ANSWER_WITH_TABLE_AND_RUN, RULES, "") == []


def test_max_widgets_caps_the_output():
    assert len(derive(ANSWER_WITH_TABLE_AND_RUN, RULES, ALL_GROUPS, max_widgets=1)) == 1
    assert len(derive(ANSWER_WITH_TABLE_AND_RUN, RULES, ALL_GROUPS, max_widgets=2)) == 2
    assert derive(ANSWER_WITH_TABLE_AND_RUN, RULES, ALL_GROUPS, max_widgets=0) == []


def test_min_and_max_decide_which_rule_fires():
    # two rows: bars (min 3) is out, kpi (min 2, max 2) is in
    specs = derive(TWO_ROW_RUN, RULES, "numbers")
    assert _kinds(specs) == ["kpi"]
    assert specs[0]["rows"] == [["Builds", "128"], ["Failures", "3"]]


def test_steps_list_fires_within_its_bounds():
    specs = derive(STEPS_ANSWER, RULES, "steps")
    assert _kinds(specs) == ["steps"]
    assert specs[0]["rows"] == [
        ["Read the archive"],
        ["Verify the pin"],
        ["Flash the board"],
        ["Confirm the LED"],
    ]

    too_many = "".join("%d. step %d\n" % (i, i) for i in range(1, 11))
    assert derive(too_many, RULES, "steps") == []


def test_matchers_are_driven_by_the_table_not_by_the_name():
    # a rule pointing at a matcher nobody wrote is skipped, not crashed on
    fake = [{"id": "x", "when": "no-such-matcher", "kind": "bars", "min": 1, "group": "numbers"}]
    assert derive(ANSWER_WITH_TABLE_AND_RUN, fake, ALL_GROUPS) == []


def test_rules_round_trip_through_the_reader():
    assert load_rules(agent.RULES_PATH) == RULES
