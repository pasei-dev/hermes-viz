"""A surface that cannot draw gets the data, not the grammar.

The transform never writes a `::viz` directive onto a surface that does not parse one.  The other half
of that rule is here: a model *can* write one anyway — a session resumed from the desktop app carries
directives in its own history and a model imitates what it can see — and on the CLI, the TUI, a gateway
or the dashboard the reader is owed the **values**, not the encoding.

So a directive is *demoted*: the payload becomes the markdown it would have drawn, its computed cells
are resolved, and only a directive with nothing left to carry leaves no line behind.  The same pass
runs on the desktop for a directive the app and the core would refuse — a group past the cap, a brace in
the attrs, a kind the core does not draw, a computed cell its own rows cannot compute — where the
alternative is grammar or an empty frame in front of a reader.
"""

import json
import re

from _agent import RULES, agent
from python.viz_dsl import KNOWN_KINDS, MAX_DIRECTIVE_CHARS, demote_directives, is_drawable

make_hook = agent.make_hook

BARS = '::viz{k="bars" d="Budget=45;Actual=95" t="Lane wall time, minutes"}'


def test_a_directive_becomes_the_data_it_carried():
    text = "## Landed\n\n%s\n\nThe rest.\n" % BARS
    assert demote_directives(text) == (
        "## Landed\n\n"
        "**Lane wall time, minutes**\n"
        "- **Budget** — 45\n"
        "- **Actual** — 95\n"
        "\nThe rest.\n"
    )
    # the encoding is gone, the values are not
    assert "::viz" not in demote_directives(text) and "95" in demote_directives(text)


def test_a_payload_with_a_header_row_becomes_a_table():
    text = '::viz{k="table" d="h=Layer|What it is;Inference format|markdown + JSX tags;Runtime|nothing"}\n'
    assert demote_directives(text) == (
        "| Layer | What it is |\n"
        "| --- | --- |\n"
        "| Inference format | markdown + JSX tags |\n"
        "| Runtime | nothing |\n"
    )


def test_a_grid_payload_becomes_a_list_when_it_has_no_header_to_name_its_columns():
    """A markdown table needs a header, and inventing one writes a word the answer never had."""
    assert demote_directives('::viz{k="array" d="a|b|c;d|e|f"}\n') == "- **a** — b — c\n- **d** — e — f\n"


def test_a_bare_run_is_a_list_and_a_run_of_numbers_is_one_line():
    assert demote_directives('::viz{k="steps" d="Read the archive;Patch the entry"}\n') == (
        "- Read the archive\n- Patch the entry\n"
    )
    # three bullets for three numbers is not a demotion, it is a column of noise
    assert demote_directives('::viz{k="sparkline" d="12;18;9;16"}\n') == "12, 18, 9, 16\n"


def test_the_unit_and_the_computed_cells_survive_the_demotion():
    text = '::viz{k="metrics" d="Prose=43;Bullets=42.2;Read line by line=sum(Prose, Bullets)" u="%"}\n'
    assert demote_directives(text) == (
        "- **Prose** — 43%\n- **Bullets** — 42.2%\n- **Read line by line** — 85.2%\n"
    )
    # a run of bare numbers is the one payload that is *only* numbers: the unit rides on every one
    assert demote_directives('::viz{k="sparkline" d="12;18;9" u="ms"}\n') == "12ms, 18ms, 9ms\n"
    # a call the payload cannot compute is printed as written: the reader sees what did not add up
    assert "sum(A, Missing)" in demote_directives('::viz{k="kpi" d="A=1;B=sum(A, Missing)"}\n')


def test_a_board_keeps_the_caption_and_the_unit_its_widget_carried():
    """A board entry carries neither (SPEC.md), so the widget's own `t=` and `u=` ride the block."""
    text = '::viz{k="board" d="kpi:Builds=128;Fails=3~bars:A=1;B=2" t="CI board" u="runs"}\n'
    assert demote_directives(text) == (
        "**CI board**\n"
        "- **Builds** — 128runs\n"
        "- **Fails** — 3runs\n"
        "\n"
        "- **A** — 1runs\n"
        "- **B** — 2runs\n"
    )


def test_a_board_demotes_entry_by_entry():
    text = '::viz{k="board" d="metrics:Prose=43;Bullets=42.2~bars:A=1;B=2"}\n'
    assert demote_directives(text) == "- **Prose** — 43\n- **Bullets** — 42.2\n\n- **A** — 1\n- **B** — 2\n"


def test_a_directive_paragraph_is_replaced_where_it_stood():
    text = "## Landed\n\n%s\n\n%s\n" % (BARS, '::viz{k="kpi" d="Builds=128;Fails=3"}')
    out = demote_directives(text)
    assert out.startswith("## Landed\n\n**Lane wall time") and out.endswith("- **Builds** — 128\n- **Fails** — 3\n")


def test_a_directive_written_mid_sentence_leaves_the_sentence_with_its_rows_inline():
    text = "The shape is %s in the answer.\n" % '::viz{k="bars" d="Budget=45;Actual=95"}'
    assert demote_directives(text) == "The shape is **Budget** — 45; **Actual** — 95 in the answer.\n"


def test_a_fenced_block_keeps_the_grammar_a_reader_is_being_shown():
    text = "Write it like this:\n\n```\n%s\n```\n\nAnd that is all.\n" % BARS
    assert demote_directives(text) == text


def test_a_directive_that_is_not_viz_is_left_alone():
    # the app's own directives belong to the app, and the plugin does not eat them
    text = '::preview{file="chart.html"}\n\n::viz{k="bars" d="a=1;b=2"}\n'
    assert demote_directives(text) == '::preview{file="chart.html"}\n\n- **a** — 1\n- **b** — 2\n'


def test_an_answer_with_nothing_to_demote_is_returned_untouched():
    for text in ("Plain prose.\n", "", "std::vector is not a directive.\n", "plain ::viz-less text"):
        assert demote_directives(text) == text


def test_a_directive_with_nothing_to_carry_leaves_no_line():
    assert demote_directives("a ::viz word\n") == "a word\n"
    assert demote_directives("::viz\n") == ""
    # a name with no attrs is a directive the app recognises, and there is no data behind it
    assert demote_directives("::viz{k=\"barz\"}\n") == ""
    # a brace group past the cap is refused by the parser, and 1300 characters of nothing carry nothing
    assert demote_directives("::viz{%s}\n" % ("x" * 1300)) == ""


def test_a_refused_group_still_gives_up_the_data_it_carried():
    """The directives worth rescuing are exactly the ones the app refuses — so the reader is owed one."""
    payload = "Budget=45;Actual=95;" + ";".join("Row%d=%d" % (i, i) for i in range(200))
    text = '::viz{k="bars" d="%s"}\n' % payload
    assert len(text) > MAX_DIRECTIVE_CHARS
    out = demote_directives(text)
    assert out.startswith("- **Budget** — 45\n- **Actual** — 95\n- **Row0** — 0\n"), out[:120]
    assert "::viz" not in out


def test_the_hook_demotes_on_every_surface_that_cannot_draw():
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    text = "## Runs\n\n%s\n" % BARS
    for platform in ("cli", "tui", "telegram", "dashboard", "api_server", "", None):
        out = hook(text, platform=platform)
        assert out is not None and out.startswith("## Runs\n\n**Lane wall time"), platform
        assert "::viz" not in out and "95" in out, platform
    # and nothing to demote is still nothing to rewrite
    assert hook("## Runs\n\nPlain prose.\n", platform="cli") is None


def test_the_hook_leaves_a_directive_the_desktop_can_draw_exactly_as_it_was():
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    text = "## Runs\n\n%s\n" % BARS
    assert hook(text, platform="desktop") is None
    assert hook(text, platform="Desktop") is None


def test_the_hook_demotes_a_directive_the_desktop_would_refuse():
    """Grammar in front of the reader is the failure the platform gate exists to avoid — here too."""
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    for broken in (
        '::viz{k="barz" d="a=1;b=2"}',                    # a kind the core does not draw
        '::viz{k="kpi" d="A=1;B=sum(A, Missing)"}',       # a cell its own rows cannot compute
        '::viz{k="bars" d=a=1}',                          # not the app's attr grammar
        '::viz{k="bars" d="%s"}' % ("x" * 1300),          # past the cap the parser accepts
    ):
        out = hook("See:\n\n%s\n" % broken, platform="desktop")
        assert out is not None and "::viz" not in out, broken


def test_the_demoter_knows_exactly_the_kinds_the_core_draws():
    """A literal here and a list in `core.mjs` would drift; this is what stops it."""
    source = (agent.RULES_PATH.parent / "desktop" / "render" / "core.mjs").read_text(encoding="utf-8")
    block = source.split("const KINDS = [", 1)[1].split("]", 1)[0]
    kinds = set(re.findall(r"'([a-z0-9-]+)'", block))
    assert kinds | {"board"} == set(KNOWN_KINDS), sorted(kinds ^ set(KNOWN_KINDS))
    assert len(kinds) == 46, "the core draws %d kinds" % len(kinds)


def test_drawable_is_a_narrow_fence():
    """Only what can be *proved* undrawable is demoted: a directive left alone is the safe direction."""
    assert is_drawable('k="bars" d="a=1;b=2"')
    assert is_drawable('k="board" d="bars:a=1;b=2~kpi:x=1"')
    assert is_drawable('k="section" t="Builds"')
    assert is_drawable('k="table" d="h=A|B;x|1"')

    assert not is_drawable("")
    assert not is_drawable('d="a=1"'), "no kind"
    assert not is_drawable('k="barz" d="a=1"'), "a kind the core does not draw"
    assert not is_drawable('k="flowchart" d="a=1"'), "a Mermaid type is a fence, not a directive"
    assert not is_drawable('k="bars"'), "no data and no title"
    assert not is_drawable('k="board" d="bars:"'), "an entry with no payload draws as its own `kind:` text"
    assert not is_drawable('k="bars" d="A=1;B=sum(A, C)"'), "an unresolvable computed cell"
    assert not is_drawable('k="board" d="bars:a=1~bars:T=sum(A, C)"'), "an unresolvable cell in an entry"
    assert not is_drawable('k="bars" d=a=1'), "not `key=\"value\"`"
    assert not is_drawable('k="bars" d="a={1}"'), "a brace the app refuses"
    assert not is_drawable("x" * (MAX_DIRECTIVE_CHARS + 1)), "past the cap"
    # An attr the app does not know is NOT a reason to demote: the parser ignores what it does not
    # read, and `x=` (SPEC.md round 11) is a real attr this fence must never eat.
    assert is_drawable('k="steps" d="a;b" x="toggle"')
    assert is_drawable('k="bars" d="a=1;b=2" oops="1"')
    # a board the core would DRAW is never demoted: one bad entry degrades to prose for that cell
    # alone while the rest of the board renders, so neither an unknown kind nor a missing one counts
    assert is_drawable('k="board" d="bars:a=1~justtext"')
    assert is_drawable('k="board" d="bars:a=1~note:see here"')


def test_the_demotion_never_leaves_a_brace_or_a_run_of_blank_lines():
    text = "## A\n\n\n\n%s\n\n\n\n## B\n" % BARS
    out = demote_directives(text)
    assert "{" not in out and "}" not in out
    assert "\n\n\n" not in out


def test_an_unresolvable_call_is_the_declared_kind_of_broken():
    """The validator and the shared vector table agree on which calls are unresolved."""
    vectors = json.loads((agent.RULES_PATH.parent / "tests" / "cells.json").read_text(encoding="utf-8"))
    for vector in vectors["vectors"]:
        attrs = 'k="metrics" d="%s"' % vector["payload"]
        assert is_drawable(attrs) is not bool(vector["unresolved"]), vector["why"]
