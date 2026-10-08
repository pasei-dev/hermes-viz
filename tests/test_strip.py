"""A surface that cannot draw is never handed raw grammar — not even the model's own.

The transform never writes a `::viz` directive onto a surface that does not parse one. The other half of
that rule is here: a model *can* write one anyway, because a session resumed from the desktop app carries
directives in its own history and a model imitates what it can see. On the CLI, the TUI, a gateway or the
dashboard that is a line of raw grammar in front of the reader — the exact failure the platform gate exists
to avoid — so the hook takes it back out.
"""

from _agent import RULES, agent

strip_directives = agent.strip_directives
make_hook = agent.make_hook

DIRECTIVE = '::viz{k="bars" d="Budget=45;Actual=95" t="Lane wall time, minutes"}'


def test_a_directive_paragraph_is_taken_out_with_its_line():
    text = "## Landed\n\n%s\n\nThe rest.\n" % DIRECTIVE
    # the line goes with the directive, and no double gap is left where it stood
    assert strip_directives(text) == "## Landed\n\nThe rest.\n"


def test_a_directive_written_mid_sentence_leaves_the_sentence():
    text = "The shape is %s in the answer.\n" % DIRECTIVE
    assert strip_directives(text) == "The shape is in the answer.\n"


def test_a_fenced_block_keeps_the_grammar_a_reader_is_being_shown():
    text = "Write it like this:\n\n```\n%s\n```\n\nAnd that is all.\n" % DIRECTIVE
    assert strip_directives(text) == text


def test_a_directive_that_is_not_viz_is_left_alone():
    # the app's own directives belong to the app, and the plugin does not eat them
    text = '::preview{file="chart.html"}\n\n::viz{k="bars" d="a=1;b=2"}\n'
    assert strip_directives(text) == '::preview{file="chart.html"}\n'


def test_an_answer_with_nothing_to_strip_is_returned_untouched():
    for text in ("Plain prose.\n", "", "std::vector is not a directive.\n"):
        assert strip_directives(text) == text


def test_a_bare_name_is_a_directive_too():
    """`::viz` with no attrs is a directive the app recognises — a card with no data, not prose."""
    assert strip_directives("a ::viz word\n") == "a word\n"
    assert strip_directives("::viz\n") == ""


def test_a_name_whose_attrs_were_refused_stays_the_text_it_is():
    """Half of a directive is not one — the app's rule, and the reason a cap here matches it.

    A brace group past the 1200-char cap is refused by the parser, and a name with no attrs is not a
    widget. Stripping the name and leaving `{…}` behind would be the worst of both.
    """
    text = "::viz{%s}\n" % ("x" * 1300)
    assert strip_directives(text) == text


def test_the_hook_strips_on_every_surface_that_cannot_draw():
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    text = "## Runs\n\n%s\n" % DIRECTIVE
    for platform in ("cli", "tui", "telegram", "dashboard", "api_server", "", None):
        assert hook(text, platform=platform) == "## Runs\n", platform
    # and nothing to strip is still nothing to rewrite
    assert hook("## Runs\n\nPlain prose.\n", platform="cli") is None


def test_the_hook_leaves_the_desktop_surface_to_the_transform():
    """On desktop the directive is the drawing: the stripper never runs there."""
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    text = "## Runs\n\n%s\n" % DIRECTIVE
    # nothing to derive from a directive-only answer, so it is returned as the model wrote it
    assert hook(text, platform="desktop") is None
    assert hook(text, platform="Desktop") is None
