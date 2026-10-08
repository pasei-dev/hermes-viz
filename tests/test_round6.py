"""Round 6: bracket, gloss and forms — the last three of the catalogue.

The kind's payload encodes as SPEC says; the matcher fires only on the shape the text states; and the
properties that must not regress stay green.
"""

from python.derive import derive
from python.viz_dsl import to_directive

from _agent import RULES, agent
from round5_answers import NESTED_ANSWER
from round6_answers import ABSENT_ANSWER, BRACKET_THREE, GENUINE_ANSWER

transform = agent.transform

#: The three groups this round adds — structure stays out of it, so nothing but the new kinds fires.
ROUND6 = "bracket,gloss,forms"


def _kinds(specs):
    return [spec["kind"] for spec in specs]


def _nonblank(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


# --- the emitters, against the SPEC payloads -------------------------------------------------------


def test_the_round6_kinds_encode_the_spec_examples():
    assert to_directive({
        "kind": "bracket",
        "rows": [["R16", "Arsenal>Chelsea,Brentford>Leeds"], ["QF", "Arsenal>Brentford"]],
    }) == '::viz{k="bracket" d="R16=Arsenal>Chelsea,Brentford>Leeds;QF=Arsenal>Brentford"}'

    assert to_directive({
        "kind": "gloss",
        "rows": [["der Hund bellt", "the dog barks", "PRS.3SG"]],
    }) == '::viz{k="gloss" d="der Hund bellt=the dog barks=PRS.3SG"}'

    # a forms grid is a pipe kind, its header carried like a table's
    assert to_directive({
        "kind": "forms",
        "header": ["person", "singular", "plural"],
        "rows": [["1st", "habe", "haben"], ["2nd", "hast", "habt"]],
    }) == '::viz{k="forms" d="h=person|singular|plural;1st|habe|haben;2nd|hast|habt"}'


def test_reserved_characters_are_stripped_from_the_new_kinds():
    # the parser cannot carry `; = ~ | \`, so a cell keeps its words and loses the separator
    assert to_directive({
        "kind": "bracket",
        "rows": [["R16", "A>B;C>D"]],
    }) == '::viz{k="bracket" d="R16=A>B C>D"}'

    assert to_directive({
        "kind": "gloss",
        "rows": [["der Hund~", "the dog"]],
    }) == '::viz{k="gloss" d="der Hund=the dog"}'

    assert to_directive({
        "kind": "forms",
        "header": ["person", "singular|plural"],
        "rows": [["1st", "habe", "haben"]],
    }) == '::viz{k="forms" d="h=person|singular plural;1st|habe|haben"}'


# --- the matchers fire on the shape, and not on its lookalike --------------------------------------


def test_bracket_rounds_derive_as_rounds_of_pairings():
    specs = derive(GENUINE_ANSWER, RULES, "bracket")
    assert _kinds(specs) == ["bracket"]
    assert specs[0]["rows"] == [
        ["R16", "Arsenal>Chelsea,Brentford>Leeds"],
        ["QF", "Arsenal>Brentford"],
    ]


def test_a_single_pairing_is_not_a_bracket():
    # one round of one pairing is a result, not a bracket — the rule's `min` of two rounds rules it out
    assert derive("R16: Arsenal>Chelsea\n", RULES, "bracket") == []
    single = "## Cup\n\nR16: Arsenal>Chelsea\n"
    assert derive(single, RULES, "bracket") == []


def test_a_sentence_with_a_dash_is_not_a_gloss():
    assert derive("Der Hund bellt - the dog barks.\n", RULES, "gloss") == []
    assert derive("Der Hund bellt — the dog barks.\n", RULES, "gloss") == []


def test_a_plain_definition_is_not_a_gloss():
    # a `word : meaning` line is facts/words, and an `=`-pair that is not word-aligned is refused
    assert derive("Hund: dog\n", RULES, "gloss") == []
    assert derive("Hund=dog\n", RULES, "gloss") == []
    # three source words against two gloss words: not aligned, so nothing to align
    assert derive("der Hund bellt=the dog barks now\n", RULES, "gloss") == []


def test_a_word_aligned_source_and_gloss_derive():
    specs = derive("der Hund bellt=the dog barks=PRS.3SG\n", RULES, "gloss")
    assert _kinds(specs) == ["gloss"]
    assert specs[0]["rows"] == [["der Hund bellt", "the dog barks", "PRS.3SG"]]


def test_a_two_column_list_is_not_a_paradigm():
    assert derive("| Word | Meaning |\n| --- | --- |\n| haben | to have |\n| gehen | to go |\n",
                  RULES, "forms") == []


def test_a_numeric_table_is_not_a_paradigm():
    table = "| Board | Runs |\n| --- | --- |\n| 291e | 42 |\n| 296e | 28 |\n"
    assert derive(table, RULES, "forms") == []


def test_a_labelled_paradigm_derives():
    specs = derive(GENUINE_ANSWER, RULES, "forms")
    assert _kinds(specs) == ["forms"]
    assert specs[0]["header"] == ["person", "singular", "plural"]
    assert specs[0]["rows"] == [["1st", "habe", "haben"], ["2nd", "hast", "habt"]]


def test_facts_stands_down_for_a_bracket_shape():
    # three rounds would otherwise be a `facts` card as well as a bracket — one dataset, one widget
    assert derive(BRACKET_THREE, RULES, "facts") == []
    assert _kinds(derive(BRACKET_THREE, RULES, "bracket")) == ["bracket"]


# --- the properties that must not regress ----------------------------------------------------------


def test_the_absent_answer_emits_nothing():
    # a plain definition, a dash sentence, a two-column list and a single pairing are all lookalikes
    assert derive(ABSENT_ANSWER, RULES, ROUND6) == []
    assert transform(ABSENT_ANSWER, RULES, ROUND6) is None


def test_the_genuine_answer_emits_all_three_and_a_second_pass_returns_nothing():
    once = transform(GENUINE_ANSWER, RULES, ROUND6, max_widgets=None)
    assert once is not None
    # one board, three entries — the new kinds are board widgets, not diagrams
    for entry in ("bracket:", "gloss:", "forms:"):
        assert entry in once
    assert 'k="board"' in once
    assert transform(once, RULES, ROUND6, max_widgets=None) is None


def test_the_round6_transform_replaces_only_the_derived_runs():
    out = transform(GENUINE_ANSWER, RULES, ROUND6, max_widgets=None)
    assert out is not None
    # the gloss, the paradigm and the bracket runs are replaced in place …
    lines = out.splitlines()
    for gone in ("der Hund bellt=the dog barks=PRS.3SG", "| 1st | habe | haben |",
                 "R16: Arsenal>Chelsea, Brentford>Leeds"):
        assert gone not in lines, gone
    # … while every heading and every prose line survives untouched
    for surviving in ("## Language notes", "The German present tense is regular here.",
                      "## The verb haben", "## Cup"):
        assert surviving in out, surviving


def test_the_round6_transform_does_not_disturb_the_structure_layer():
    # an answer whose headings are already markdown is left alone: the layer has nothing to insert, and
    # no band is drawn over a heading that already renders
    assert transform(NESTED_ANSWER, RULES, "structure,bracket,gloss,forms", max_widgets=None) is None
