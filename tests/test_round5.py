"""Round 5: level 2 from the answer as it stands, the subject emitters, and the Mermaid kinds."""

import re

from python.derive import derive, structure
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round5_answers import (
    CAPTION_UNDER_H2,
    DATED_ANSWER,
    FLAT_ANSWER,
    MESSAGES_ANSWER,
    NESTED_ANSWER,
    SCHEDULE_ANSWER,
    SHARES_ANSWER,
    STATES_ANSWER,
)

transform = agent.transform

#: The `l=2` a board band carries for a division within a section.
_LEVEL2 = re.compile(r"section:[^;~\"]*;l=2")
#: The section keywords a board band can carry, in the order they appear in the output.
_BAND = re.compile(r"section:([^;~\"]+)(?:;l=(\d))?")


def _levels(text):
    return [int(level) if level else 1 for _, level in _BAND.findall(text)]


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


# --- level 2, from what the answer already holds ---------------------------------------------------


def test_a_nested_answer_promotes_its_sub_headings_to_level_2():
    out, sections = structure(NESTED_ANSWER, RULES, "structure")
    assert [(spec["title"], spec["level"]) for spec in sections] == [
        ("Build report", 1),
        ("Timing", 2),
        ("Failures", 2),
        ("Firmware states", 1),
        ("Schedule", 1),
    ]
    # a markdown heading the answer already carries is never touched — no marker is inserted
    assert _nonblank(out) == _nonblank(NESTED_ANSWER)


def test_a_caption_under_a_level_1_heading_is_level_2():
    _, sections = structure(CAPTION_UNDER_H2, RULES, "structure")
    assert [spec["level"] for spec in sections] == [1, 2]


def test_a_caption_with_no_level_1_open_is_only_level_1():
    lone = "Board runs\n\n| Board | Runs |\n| --- | --- |\n| 291e | 42 |\n| 296e | 28 |\n"
    _, sections = structure(lone, RULES, "structure")
    # a lone level 2 is impossible: with no level-1 band open the caption is the answer's own division
    assert [spec["level"] for spec in sections] == [1]


def test_an_answer_with_no_nesting_never_produces_level_2():
    _, sections = structure(FLAT_ANSWER, RULES, "structure")
    assert [spec["level"] for spec in sections] == [1]
    out = transform(FLAT_ANSWER, RULES, "structure,numbers", max_widgets=None)
    assert "l=2" not in out


def test_level_2_is_a_heading_under_its_parent_never_alone():
    """The level rides in the marker the layer inserts, because the derived path draws no band.

    A division *within* a section is a `###` under the `##` that opened it, so the hierarchy is legible
    from the markers alone — and a lone level 2 is still impossible.
    """
    out = transform(NESTED_ANSWER, RULES, "structure,numbers,mermaid", max_widgets=None)
    _, sections = structure(NESTED_ANSWER, RULES, "structure")
    levels = [spec["level"] for spec in sections]
    assert levels == [1, 2, 2, 1, 1]
    for position, level in enumerate(levels):
        if level == 2:
            assert 1 in levels[:position]  # its parent section was opened first
    # the parent keeps its own `##`, each sub-division its `###`, and no band repeats either
    assert "## Build report" in out
    assert "### Timing" in out and "### Failures" in out
    assert "section:" not in out


# --- the properties that must not regress ----------------------------------------------------------


def test_the_nested_transform_replaces_only_the_derived_runs():
    out = transform(NESTED_ANSWER, RULES, "structure,numbers,mermaid", max_widgets=None)
    assert out is not None
    # the numeric runs and the state/schedule runs are replaced in place …
    for gone in ("- Build: 42", "- 291e: 1", "Idle -> Running", "Build: 2026-01-04 .. 2026-01-09"):
        assert gone not in out, gone
    # … while every heading and every prose line survives untouched
    for surviving in ("## Build report", "The flash ran on three boards and every one came up.",
                      "### Timing", "### Failures", "## Firmware states", "## Schedule"):
        assert surviving in out, surviving


def test_a_second_transform_of_the_new_boards_and_fences_returns_nothing():
    once = transform(NESTED_ANSWER, RULES, "structure,numbers,mermaid", max_widgets=None)
    assert once is not None
    assert transform(once, RULES, "structure,numbers,mermaid", max_widgets=None) is None


# --- the five subject emitters ----------------------------------------------------------------------


def test_the_subject_kinds_encode_the_spec_examples():
    assert to_directive({
        "kind": "words",
        "rows": [["der Hund", "[deːɐ hʊnt]", "the dog", "Der Hund bellt."]],
    }) == '::viz{k="words" d="der Hund=[deːɐ hʊnt]=the dog=Der Hund bellt."}'

    assert to_directive({
        "kind": "route",
        "rows": [["09:40", "Kastrup", "Check in"], ["11:10", "Gate B", "Board"]],
    }) == '::viz{k="route" d="09:40=Kastrup=Check in;11:10=Gate B=Board"}'

    # nutrition uses the `of` form
    assert to_directive({
        "kind": "nutrition",
        "rows": [["Calories", "1850 of 2200"], ["Protein", "132 g of 150"]],
    }) == '::viz{k="nutrition" d="Calories=1850 of 2200;Protein=132 g of 150"}'

    assert to_directive({
        "kind": "matches",
        "rows": [
            ["18:00", "Arsenal 2-1 Chelsea", "League Cup"],
            ["20:45", "Liverpool 0-2 Everton", "League Cup"],
        ],
    }) == ('::viz{k="matches" d="18:00=Arsenal 2-1 Chelsea=League Cup;'
           '20:45=Liverpool 0-2 Everton=League Cup"}')


def test_recipe_is_a_grid_not_label_value_pairs():
    assert to_directive({
        "kind": "recipe",
        "header": ["Ingredient", "amount", "note"],
        "rows": [["Flour", "250 g", "sifted"], ["Butter", "125 g", "cold"], ["Sugar", "100 g", "fine"]],
    }) == ('::viz{k="recipe" d="h=Ingredient|amount|note;'
           'Flour|250 g|sifted;Butter|125 g|cold;Sugar|100 g|fine"}')


def test_reserved_characters_are_stripped_from_subject_values():
    # `;` `=` `~` `|` `\` would break the payload, so the emitter strips them from every cell
    assert to_directive({
        "kind": "route",
        "rows": [["09:40", "Kastrup|Gate;4", "Check in"]],
    }) == '::viz{k="route" d="09:40=Kastrup Gate 4=Check in"}'
    assert to_directive({
        "kind": "matches",
        "rows": [["18:00", "Arsenal 2-1 \\Chelsea", "League~Cup=1"]],
    }) == '::viz{k="matches" d="18:00=Arsenal 2-1 Chelsea=League Cup 1"}'


# --- Mermaid kinds the derivation can reach ---------------------------------------------------------


def _kinds(text, groups="mermaid"):
    return [(spec["kind"], spec.get("body")) for spec in derive(text, RULES, groups)]


def test_a_run_of_states_becomes_a_state_diagram():
    assert _kinds(STATES_ANSWER) == [("state", ["Idle --> Running", "Running --> Halted", "Halted --> Idle"])]
    out = transform(STATES_ANSWER, RULES, "mermaid", max_widgets=None)
    assert "```mermaid" in out and "stateDiagram-v2" in out


def test_an_exchange_of_messages_becomes_a_sequence_diagram():
    assert _kinds(MESSAGES_ANSWER) == [
        ("sequence", ["Client->>Server: GET /build", "Server->>Client: 200 OK"])
    ]
    out = transform(MESSAGES_ANSWER, RULES, "mermaid", max_widgets=None)
    assert "```mermaid" in out and "sequenceDiagram" in out


def test_a_schedule_with_dates_becomes_a_gantt():
    assert _kinds(SCHEDULE_ANSWER) == [
        ("gantt", ["dateFormat YYYY-MM-DD", "Build :2026-01-04, 2026-01-09", "Test :2026-01-09, 2026-01-12"])
    ]
    out = transform(SCHEDULE_ANSWER, RULES, "mermaid", max_widgets=None)
    assert "```mermaid" in out and "\ngantt\n" in out


def test_shares_of_one_whole_become_a_pie():
    assert _kinds(SHARES_ANSWER) == [("pie", ['"Firmware" : 42', '"DSP" : 28', '"Web" : 30'])]
    out = transform(SHARES_ANSWER, RULES, "mermaid", max_widgets=None)
    assert "```mermaid" in out and "\npie\n" in out


def test_dated_events_become_a_timeline_fence():
    assert _kinds(DATED_ANSWER) == [
        ("timeline", ["2026-01-04 : First DSP boot", "2026-01-09 : Firmware flash"])
    ]
    out = transform(DATED_ANSWER, RULES, "mermaid", max_widgets=None)
    assert "```mermaid" in out and "\ntimeline\n" in out


def test_a_kind_whose_shape_is_absent_emits_nothing():
    # one transition is not a run of states
    assert _kinds("Idle -> Running\n") == []
    # an arrow chain is the flow matcher's shape, not the state matcher's
    assert _kinds("Request -> Auth -> Service\nFetch -> Cache -> Render\n") == []
    # shares that do not add up to a whole are not a pie
    assert _kinds("A: 10%\nB: 20%\n") == []
    # a single dated event is not a schedule
    assert _kinds("Build: 2026-01-04 .. 2026-01-09\n") == []
    # prose states no shape at all
    assert _kinds("The board flashed cleanly and the DSP came up.\n") == []
    for absent in (
        "Idle -> Running\n",
        "Request -> Auth -> Service\nFetch -> Cache -> Render\n",
        "A: 10%\nB: 20%\n",
        "Build: 2026-01-04 .. 2026-01-09\n",
    ):
        assert transform(absent, RULES, "mermaid", max_widgets=None) is None
