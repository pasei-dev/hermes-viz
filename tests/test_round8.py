"""Round 8: the shapes, level 2 from a bold sub-division, and the more specific shape winning.

A subject kind is a skin over a shape, never a new engine (SPEC.md, "Shapes, not subjects"): these four
shapes are what makes the shipped rule-group default honest, and a new subject needs no new rule at all.
"""

from python.derive import derive, structure
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round5_answers import NESTED_ANSWER
from round6_answers import GENUINE_ANSWER as GLOSS_ANSWER
from round8_answers import (
    BOLD_SIBLINGS,
    BOLD_UNDER_H2,
    MATCHES_ANSWER,
    RECIPE_ANSWER,
    ROUTE_ANSWER,
    SIX_ROW_RAMP,
    SIX_STAGE_FUNNEL,
    UNFAMILIAR_ANSWER,
)

transform = agent.transform

#: One group per shape — `structure` stays out of it, so nothing but the shapes fires.
ROUND8 = "records,grid,events,groups"


def _kinds(specs):
    return [spec["kind"] for spec in specs]


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


# --- the shapes, on data no subject rule knows -----------------------------------------------------


def test_the_round8_shapes_encode_the_spec_payloads():
    assert to_directive({
        "kind": "records",
        "rows": [["Pallet", "12 crates"], ["Container", "40 ft"]],
    }) == '::viz{k="records" d="Pallet=12 crates;Container=40 ft"}'

    # a grid is a header row plus equal-width cells: a `|` kind, like the table and the BOM
    assert to_directive({
        "kind": "grid",
        "header": ["Ingredient", "Amount"],
        "rows": [["Flour", "500 g"], ["Water", "325 g"]],
    }) == '::viz{k="grid" d="h=Ingredient|Amount;Flour|500 g;Water|325 g"}'

    assert to_directive({
        "kind": "events",
        "rows": [["08:12", "Cathedral", "5 min"], ["08:40", "Market Square", "12 min"]],
    }) == '::viz{k="events" d="08:12=Cathedral=5 min;08:40=Market Square=12 min"}'

    assert to_directive({
        "kind": "groups",
        "rows": [
            ["18:00", "Arsenal 2-1 Chelsea", "League Cup"],
            ["20:45", "Liverpool 0-2 Everton", "League Cup"],
        ],
    }) == (
        '::viz{k="groups" d="18:00=Arsenal 2-1 Chelsea=League Cup'
        ';20:45=Liverpool 0-2 Everton=League Cup"}'
    )


def test_unfamiliar_data_renders_as_a_shape():
    # a subject with no kind of its own — the shape is all a new subject needs
    specs = derive(UNFAMILIAR_ANSWER, RULES, "records")
    assert _kinds(specs) == ["records"]
    assert specs[0]["rows"] == [
        ["Pallet", "12 crates of tile"],
        ["Container", "40 ft high cube"],
        ["Customs", "cleared for release"],
    ]
    directive = to_directive(specs[0])
    assert directive is not None
    assert 'k="records"' in directive
    assert "Pallet=12 crates of tile" in directive


def test_the_same_shape_carries_two_different_subjects():
    # the point of a shape: plumbing or tile, the same `label=value` run derives the same widget
    one = derive("Weight=12 t\nVolume=8 cu\n", RULES, "records")
    two = derive("Pallet=12 crates\nContainer=40 ft\n", RULES, "records")
    assert _kinds(one) == _kinds(two) == ["records"]
    assert [row[0] for row in one[0]["rows"]] == ["Weight", "Volume"]


def test_a_recipe_is_a_grid_and_a_route_is_events():
    grid = derive(RECIPE_ANSWER, RULES, "grid")
    assert _kinds(grid) == ["grid"]
    assert grid[0]["header"] == ["Ingredient", "Amount", "Note"]
    assert grid[0]["rows"] == [["Flour", "500 g", "strong"], ["Water", "325 g", "warm"]]

    events = derive(ROUTE_ANSWER, RULES, "events")
    assert _kinds(events) == ["events"]
    assert events[0]["rows"] == [["08:12", "Cathedral", "5 min"], ["08:40", "Market Square", "12 min"]]


def test_a_repeated_label_is_groups_never_records():
    # the shared cell *is* the grouping, so the general record shape stands down for it
    assert _kinds(derive(MATCHES_ANSWER, RULES, "groups")) == ["groups"]
    assert _kinds(derive(MATCHES_ANSWER, RULES, "records,groups")) == ["groups"]
    # with `groups` off the same rows are still a record run — no shape is lost, only specialised
    assert _kinds(derive(MATCHES_ANSWER, RULES, "records")) == ["records"]


def test_a_records_run_with_no_repeat_is_never_groups():
    # `records` accepts it; the repeat that makes it `groups` is absent
    assert _kinds(derive(UNFAMILIAR_ANSWER, RULES, "groups")) == []


def test_no_shape_fires_when_the_shape_is_absent():
    # prose, a `label: value` run (facts' shape, colon), a ragged table, and a lone pairing
    assert derive("The board flashed cleanly and nothing else was touched.\n", RULES, ROUND8) == []
    assert derive("Hund: dog\nDer Hund bellt - the dog barks.\n", RULES, ROUND8) == []
    assert derive("| a | b | c |\n| --- | --- | --- |\n| 1 | 2 |\n", RULES, ROUND8) == []
    assert derive("08:12 - Cathedral\n", RULES, ROUND8) == []
    # a single record is not a run of them
    assert derive("Pallet=12 crates\n", RULES, ROUND8) == []


def test_records_stands_down_where_a_specific_kind_claims_the_rows():
    # a word-aligned gloss is a `record` of three cells; the gloss kind is the more specific shape
    assert _kinds(derive(GLOSS_ANSWER, RULES, "gloss,records")) == ["gloss"]
    # and with the specific group off the same rows are the generic record shape
    records = derive(GLOSS_ANSWER, RULES, "records")
    assert _kinds(records) == ["records"]
    assert records[0]["rows"][0] == ["der Hund bellt", "the dog barks", "PRS.3SG"]


def test_grid_stands_down_where_a_numeric_table_is_bars():
    # one table, one widget: the numeric table is the more specific shape
    table = "| Board | Runs |\n| --- | --- |\n| 291e | 42 |\n| 296e | 28 |\n| 208e | 17 |\n"
    assert _kinds(derive(table, RULES, "grid")) == ["grid"]
    assert _kinds(derive(table, RULES, "tables,grid")) == ["bars"]


def test_groups_stands_down_where_a_gloss_claims_the_rows():
    # a gloss's note column repeats down the run, which is not the grouping `groups` is for
    assert _kinds(derive(GLOSS_ANSWER, RULES, "gloss,groups")) == ["gloss"]


def test_the_shape_replaces_the_subject_rule_entirely():
    # nothing in the table names a subject: the five names the default used to carry have no rules
    subjects = {"words", "recipe", "route", "nutrition", "matches"}
    groups = {str(rule["group"]) for rule in RULES}
    assert subjects & groups == set()
    assert {"records", "grid", "events", "groups"} <= groups


# --- level 2, from the answer as it stands ---------------------------------------------------------


def test_a_bold_sub_division_under_an_open_section_is_level_2():
    out, specs = structure(BOLD_UNDER_H2, RULES, "structure")
    assert [(spec["title"], spec["level"]) for spec in specs] == [
        ("Build report", 1),
        ("Board runs", 2),
        ("Timing", 2),
    ]
    assert "\n### Board runs\n" in out
    assert "### Build report" not in out  # the `##` is the level 1


def test_bold_siblings_with_no_section_above_are_all_level_1():
    # no `##` is open, so each all-bold line is the answer's own division — a level 2 would be invented
    out, specs = structure(BOLD_SIBLINGS, RULES, "structure")
    assert [(spec["title"], spec["level"]) for spec in specs] == [("Build report", 1), ("Timing", 1)]


def test_a_lone_level_2_stays_impossible():
    # a caption with no level-1 band open is the answer's own division
    _, specs = structure("Timing\n\n- Build: 42\n- Test: 18\n", RULES, "structure")
    assert [spec["level"] for spec in specs] == [1]
    # and a `###` with no `##` above it is not an anchor at all
    _, specs = structure("### Timing\n\n- Build: 42\n", RULES, "structure")
    assert specs == []


def test_a_markdown_sub_heading_still_promotes_to_level_2():
    # the round-5 behaviour is unchanged: `###` under `##`, and nothing else
    _, specs = structure(NESTED_ANSWER, RULES, "structure")
    assert [spec["level"] for spec in specs] == [1, 2, 2, 1, 1]


# --- one run, one shape ----------------------------------------------------------------------------


def test_a_funnel_is_never_also_a_heatmap_at_any_length():
    # six named stages narrow: `funnel` and `heatmap` claim the very same rows, so heatmap stands down
    assert _kinds(derive(SIX_STAGE_FUNNEL, RULES, "funnel")) == ["funnel"]
    assert _kinds(derive(SIX_STAGE_FUNNEL, RULES, "heatmap")) == ["heatmap"]
    assert _kinds(derive(SIX_STAGE_FUNNEL, RULES, "funnel,heatmap")) == ["funnel"]
    assert _kinds(derive(SIX_STAGE_FUNNEL, RULES, "numbers,funnel,heatmap")) == ["funnel"]


def test_a_six_row_ramp_is_a_heatmap_and_no_funnel():
    assert _kinds(derive(SIX_ROW_RAMP, RULES, "heatmap")) == ["heatmap"]
    assert _kinds(derive(SIX_ROW_RAMP, RULES, "funnel,heatmap")) == ["heatmap"]


def test_one_dataset_emits_one_widget_under_every_group():
    # the fixtures above, with every group on: one spec each, and never a duplicate kind
    for answer, expected in (
        (UNFAMILIAR_ANSWER, ["records"]),
        (RECIPE_ANSWER, ["grid"]),
        (ROUTE_ANSWER, ["timeline"]),  # the specific kind wins; `events` stands down
        (MATCHES_ANSWER, ["groups"]),
        (SIX_STAGE_FUNNEL, ["funnel"]),
    ):
        kinds = _kinds(derive(answer, RULES, agent.DEFAULT_RULE_GROUPS))
        assert kinds == expected, answer


# --- the properties that must not regress ----------------------------------------------------------


def test_the_round8_transform_replaces_only_the_derived_runs():
    out = transform(UNFAMILIAR_ANSWER, RULES, ROUND8, max_widgets=None)
    assert out is not None
    # the record run is replaced in place; the heading survives untouched
    assert "Pallet=12 crates of tile" not in out.splitlines()
    assert "## Cargo manifest" in out
    assert "records:Pallet=12 crates of tile;Container=40 ft high cube;Customs=cleared for release" in out


def test_a_round8_transform_is_idempotent():
    once = transform(UNFAMILIAR_ANSWER, RULES, ROUND8, max_widgets=None)
    assert once is not None
    assert 'k="board"' in once
    assert "records:Pallet=12 crates of tile" in once
    assert transform(once, RULES, ROUND8, max_widgets=None) is None


def test_the_shapes_leave_the_structure_layer_alone():
    out = transform(BOLD_UNDER_H2, RULES, "structure," + ROUND8, max_widgets=None)
    assert out is not None
    assert ";l=2" in out  # the bold sub-divisions stayed level 2 through the widget pass
    for line in _nonblank(BOLD_UNDER_H2):
        word = line[2:-2] if (line.startswith("**") and line.endswith("**")) else line
        assert word in out
