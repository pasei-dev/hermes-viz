"""The format guide ships as two prompt sections, and off is still measurably free.

The host caps a system-prompt section at ``MAX_SYSTEM_PROMPT_SECTION_CHARS = 4000`` and **drops the whole
section** when it is over — a guide 16 characters over is a guide the model never sees, silently, in
exactly the configuration that turned the most on.  So the guide is registered twice: `hermes-viz-format`
carries the rules (the mandate, the grammar, the drawing-choice map, the two walks), `hermes-viz-kinds`
carries the kind block.  Both are gated identically and both must fit the cap in every group
configuration.  With the setting on each section appears exactly once — never stacked.  With it off there
is no section to register, so the rendered prompt is byte-identical to one from a plugin that has no guide
at all.
"""

import json
import re

from _agent import agent

ROOT = agent.RULES_PATH.parent

#: The two sections a desktop session with the shipped settings actually receives:
#: `format_guide_section` is the rules half, `kinds_section` the kind block.
#: `agent.FORMAT_GUIDE` / `agent.FORMAT_GUIDE_KINDS` are the same texts with every group on.
SHIPPED = agent.format_guide_section(True)
SHIPPED_KINDS = agent.kinds_section(True)
ALL_GROUPS = ",".join(sorted({str(rule["group"]) for rule in agent.load_rules(agent.RULES_PATH)}))
#: Every group on, including the one that ships off.
EVERY_GROUP = ALL_GROUPS + ",changes"


class FakeCtx:
    """A ctx that records hooks and system-prompt sections the way Hermes' loader exposes them."""

    def __init__(self, config=None):
        self.config = dict(config or {})
        self.hooks = []
        self.sections = []

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))

    # Mirrors the host: `hermes_cli/plugins_dispatch.py` sets `MAX_SYSTEM_PROMPT_SECTION_CHARS = 4000`,
    # and `register_system_prompt_section` RAISES above it.  A fake that accepts any ceiling cannot see
    # the failure — which is how a 4800-char declaration shipped a guide that was never registered (the
    # bare `except` in `register()` swallowed the ValueError) while every test stayed green.  Enforce the
    # real ceiling here so the mismatch is a test failure, not a silently dead prompt section.
    MAX_SECTION_CHARS = 4000

    def register_system_prompt_section(self, section_id, content, *, position="after_memory", max_chars=4000):
        if not 0 < max_chars <= self.MAX_SECTION_CHARS:
            raise ValueError(
                f"system prompt section max_chars must be between 1 and {self.MAX_SECTION_CHARS}"
            )
        self.sections.append(
            {"id": section_id, "content": content, "position": position, "max_chars": max_chars}
        )


def _section(ctx, section_id):
    """The registered section with *section_id*, or a failure that names what was registered instead."""
    by_id = {section["id"]: section for section in ctx.sections}
    assert section_id in by_id, "registered: %s" % sorted(by_id)
    return by_id[section_id]


def test_the_guide_ships_on_and_off_is_still_free():
    # the setting's own contract: off is off, and the section text is what makes it free
    assert agent.DEFAULT_FORMAT_GUIDE is True
    assert agent.format_guide_section(None) is None
    assert agent.format_guide_section(False) is None
    assert agent.format_guide_section("false") is None
    assert agent.format_guide_section("off") is None
    assert agent.kinds_section(None) is None
    assert agent.kinds_section(False) is None
    # no setting at all reads the shipped default: the hook *and* the guide's two sections
    ctx = FakeCtx()
    agent.register(ctx)
    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    assert [section["id"] for section in ctx.sections] == [
        agent.FORMAT_GUIDE_SECTION_ID, agent.KINDS_SECTION_ID,
    ]
    rules = _section(ctx, agent.FORMAT_GUIDE_SECTION_ID)
    kinds = _section(ctx, agent.KINDS_SECTION_ID)
    # The content is a callable, so the guide can be withheld from a delegate_task child. Assert the
    # behaviour rather than the identity: a main session gets the guide, a child gets nothing.
    assert callable(rules["content"]), "the section must be per-session, or a child cannot be excluded"
    assert callable(kinds["content"]), "the section must be per-session, or a child cannot be excluded"
    assert rules["content"]({"platform": "desktop"}) == SHIPPED, "a desktop session gets the rules"
    assert kinds["content"]({"platform": "desktop"}) == SHIPPED_KINDS, "and the kinds too"
    assert rules["content"]({"subagent_id": "sa-0-abc"}) == "", "a delegated child gets no guide"
    assert kinds["content"]({"subagent_id": "sa-0-abc"}) == "", "and neither section"
    assert rules["content"]({"parent_session_id": "20260101_000000_aaaa"}) == "", "a child session too"
    assert kinds["content"]({"parent_session_id": "20260101_000000_aaaa"}) == ""


def test_an_off_setting_leaves_the_prompt_byte_identical():
    base = "You are an agent. Follow the rules.\n"
    assert agent.format_guide_prompt(base, False) == base
    assert agent.format_guide_prompt(base, None) == base
    assert agent.format_guide_prompt(base, "off") == base
    # and an explicitly-off setting still registers no section
    ctx = FakeCtx({"format_guide": False})
    agent.register(ctx)
    assert ctx.sections == []


def test_an_on_setting_appends_the_guide_exactly_once():
    base = "You are an agent. Follow the rules.\n"
    prompt = agent.format_guide_prompt(base, True)
    assert prompt.startswith(base)
    assert prompt.count(SHIPPED) == 1
    assert prompt.count(SHIPPED_KINDS) == 1
    # idempotent: an already-guided prompt is never given a second copy
    assert agent.format_guide_prompt(prompt, True) == prompt
    assert agent.format_guide_prompt("true", True).startswith("true\n\n" + SHIPPED)


def test_register_adds_both_sections_when_on():
    ctx = FakeCtx({"format_guide": True})
    agent.register(ctx)
    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    assert [section["id"] for section in ctx.sections] == [
        agent.FORMAT_GUIDE_SECTION_ID, agent.KINDS_SECTION_ID,
    ]
    for section in ctx.sections:
        # Per-session by design: the guide is withheld from a delegate_task child, whose answer is read
        # by the orchestrator. Assert the behaviour, not the identity.
        assert callable(section["content"]), "the section must be per-session, or a child cannot be excluded"
        assert section["position"] == "after_memory"
        assert section["max_chars"] == agent.FORMAT_GUIDE_MAX_CHARS
    assert _section(ctx, agent.FORMAT_GUIDE_SECTION_ID)["content"]({"platform": "desktop"}) == SHIPPED
    assert _section(ctx, agent.KINDS_SECTION_ID)["content"]({"platform": "desktop"}) == SHIPPED_KINDS
    assert _section(ctx, agent.KINDS_SECTION_ID)["content"]({"subagent_id": "sa-0-abc"}) == ""


def test_the_rules_section_carries_the_mandate():
    guide = SHIPPED
    folded = guide.lower()
    for beat in (
        "heading",
        "list",
        "table",
        "separator",
        "show what can be shown",
        "::viz{",
        # the mandate's own beats, not just the grammar
        "one drawing per idea",
        "what deserves a drawing",
        "before you answer",
        "before you send",
        "callout",
        "never invented filler",
        "mermaid",
    ):
        assert beat in folded, beat


def test_each_section_fits_the_host_cap_in_every_group_configuration():
    """The cap is per section and the host drops a section whole when it is over — so this is the load
    bearing invariant, not a size preference: 16 characters over loses the section, silently."""
    assert agent.FORMAT_GUIDE_MAX_CHARS <= 4000, "the declared ceiling exceeds the host's section limit"
    for label, groups in (
        ("shipped groups", agent.DEFAULT_RULE_GROUPS),
        ("every group on", EVERY_GROUP),
        ("everything off", ""),
    ):
        rules = agent.format_guide_section(True, groups)
        kinds = agent.kinds_section(True, groups)
        assert 0 < len(rules) < agent.FORMAT_GUIDE_MAX_CHARS, (label, len(rules))
        assert 0 < len(kinds) < agent.FORMAT_GUIDE_MAX_CHARS, (label, len(kinds))
    # with every group on the reference texts are what the gated build produces — the gate is the only
    # difference, so the ceiling is tested against the longest build of each section
    assert agent.format_guide_section(True, ALL_GROUPS) == agent.FORMAT_GUIDE
    assert agent.kinds_section(True, ALL_GROUPS) == agent.FORMAT_GUIDE_KINDS
    assert len(agent.FORMAT_GUIDE) < agent.FORMAT_GUIDE_MAX_CHARS
    assert len(agent.FORMAT_GUIDE_KINDS) < agent.FORMAT_GUIDE_MAX_CHARS


def test_the_drawing_rule_is_a_trigger_not_a_judgement():
    """A judgement is not a rule: "where a drawing fits" leaves the choice to the model. The trigger
    names the shapes that are drawn, and there is deliberately no line budget beside it."""
    guide = SHIPPED
    assert (
        "Any two or more quantities, paths, statuses, steps, dates or options are drawn, not described."
        in guide
    )
    assert "Where a drawing fits" not in guide, "the judgement sentence is gone"
    both = SHIPPED + SHIPPED_KINDS
    assert not re.search(r"\d+\s+lines?\b", both), "a line budget crept in"


def test_the_closing_offer_is_named_not_banned():
    """`no closing offer` was violated 22% of the time because it named nothing. The rule names the
    three shapes, says why they are wrong, and says where the impulse belongs."""
    guide = SHIPPED
    for shape in ("`say the word`", "`want me to`", "`if you want`"):
        assert shape in guide, shape
    assert "offer work nobody asked for" in guide
    assert "first line" in guide


def test_the_drawing_cap_ships_at_six():
    assert agent.DEFAULT_MAX_WIDGETS == 6
    settings = json.loads((ROOT / "dashboard" / "settings.json").read_text(encoding="utf-8"))["settings"]
    assert settings["max_widgets"]["default"] == 6
    assert (settings["max_widgets"]["min"], settings["max_widgets"]["max"]) == (0, 10)
    # the guide's own close prints the live number, taken from the same constant
    assert "at most 6 drawings" in SHIPPED
    assert "at most 3 drawings" not in SHIPPED


def test_the_stated_cost_is_in_one_place_and_shown_live_in_the_others():
    """The README states the guide's cost; the two settings pages compute it live instead.

    The guide is two registered sections, so the figure the README states is their **sum** — what one
    request carries.  A number restated in a setting's description is a lie the reader acts on the moment
    the guide changes, and it is the one thing they weigh the guide's worth against.  So the description
    says where the live figure is and carries no figure of its own, and both surfaces render what the API
    recomposes for the groups as they stand — a toggle moves it in the same round trip.
    """
    both = SHIPPED + SHIPPED_KINDS
    size = len(both)
    words = len(both.split())
    tokens = round(size / 4.05)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert str(tokens) in readme, "README does not state the guide's live cost (%d tokens)" % tokens
    assert "%d characters" % size in readme, "README does not state the character count"
    assert str(words) in readme, "README does not state the word count"

    description = json.loads((ROOT / "dashboard" / "settings.json").read_text(
        encoding="utf-8"))["settings"]["format_guide"]["description"]
    assert "%d characters" % size not in description, "the description must not repeat a number"
    assert str(tokens) not in description, "nor a stale token count"
    assert "live" in description.lower(), "it points at the figure that is live instead"

    bundle = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
    page = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    for name, text in (("the web page", bundle), ("the desktop settings page", page)):
        assert "state.guide" in text and "guide.tokens" in text, "%s renders the live cost" % name
        assert "%d characters" % size not in text, "%s must not hard-code a number it can fetch" % name


def test_both_sections_are_withheld_from_a_surface_that_cannot_draw():
    """Same gate as the hook: a surface that does not parse a directive is not asked to write one.

    The guide's whole content is structure *and* the `::viz` grammar, so a session that cannot draw must
    not carry it — the model would write directives into an answer that renders them as literal text.
    """
    ctx = FakeCtx({"format_guide": True})
    agent.register(ctx)
    for section_id in (agent.FORMAT_GUIDE_SECTION_ID, agent.KINDS_SECTION_ID):
        content = _section(ctx, section_id)["content"]
        assert content({"platform": "desktop"})
        for platform in ("cli", "tui", "telegram", "dashboard", "api_server", "", None):
            assert content({"platform": platform}) == "", (section_id, platform)
        assert content(None) == "", "an unknown session is not asked to write a directive"
        assert content({"platform": "desktop", "subagent_id": "sa-0-abc"}) == "", "a child still gets nothing"


def test_the_kinds_section_names_every_kind_the_core_draws():
    """A kind the guide omits is a kind the model cannot reach.

    Eight kinds are derived by rules; the rest arrive only through an explicit `::viz`, and the guide is
    the model's only channel to learn they exist — a guide listing the eight leaves the rest undrawable in
    practice. Read `KINDS` off the drawing core rather than keeping a second list here.
    """
    text = (ROOT / "desktop" / "render" / "core.mjs").read_text(encoding="utf-8")
    block = text.split("const KINDS = [", 1)[1].split("]", 1)[0]
    kinds = set(re.findall(r"'([a-z0-9-]+)'", block))
    assert len(kinds) == 46, "the core draws %d kinds" % len(kinds)
    omitted = sorted(kind for kind in kinds if "`%s`" % kind not in agent.FORMAT_GUIDE_KINDS)
    assert not omitted, "the kinds section omits: %s" % omitted
    # `board` composes the others and is not in `KINDS`; the kinds section must name it too
    assert "`board`" in agent.FORMAT_GUIDE_KINDS


def test_a_group_that_is_off_leaves_the_prompt_entirely():
    """A disabled feature is absent from the prompt — never present-and-annotated.

    The kind block is composed from the live rule table, so a group turned off takes its kinds out of the
    prompt.  A line reading "`changes` is OFF" would spend tokens describing a kind the model may not
    write, which is the failure this replaced.
    """
    # the shipped configuration: `changes` is off, and the kind is nowhere in either section
    assert "`changes`" not in SHIPPED_KINDS
    assert "OFF" not in SHIPPED and "changed-files" not in SHIPPED
    # with every group on it IS there, so the absence above is the gate rather than a missing word
    assert "`changes`" in agent.kinds_section(True, ALL_GROUPS)

    # any group, not just that one: `heatmap` alone carries `heatmap`, and `bars` does not ride on it
    without_heatmap = agent.kinds_section(True, ALL_GROUPS.replace(",heatmap", ""))
    assert "`heatmap`" not in without_heatmap
    assert "`bars`" in without_heatmap

    # a kind no rule emits has no group to gate it, so the `::viz`-only kinds survive everything off
    nothing_on = agent.kinds_section(True, "")
    for kind in ("line", "donut", "table", "sparkline", "words", "recipe", "matches", "section", "board"):
        assert "`%s`" % kind in nothing_on, kind
    for kind in ("bars", "kpi", "changes", "heatmap", "checklist", "wireframe"):
        assert "`%s`" % kind not in nothing_on, kind
    # a line whose kinds are all gone goes with them, note and all — no stranded lead
    assert "`path=+a=-d`" not in nothing_on
    assert not re.search(r"—\s*$", nothing_on, re.M), "a lead with no kinds under it"


def test_the_guide_names_the_computed_cells_and_the_composition_rule():
    """A kind the guide does not name is a kind nobody draws; a call it does not name is arithmetic.

    Round 12's two halves, and the reason they live in the guide: the model composes the answer, and a
    total it can name is a call the halves compute rather than a number it works out in its head.
    """
    guide = SHIPPED
    for beat in ("sum(A, B)", "share(A, B)", "diff(A, B)", "a call on the payload's own rows"):
        assert beat in guide, beat
    # the composition rule: the widget carries the data, the prose carries what the drawing cannot
    assert "never its numbers again" in guide
    # a call is not a kind, so no group gates it: it survives every group being off
    nothing_on = agent.format_guide_section(True, "")
    for beat in ("sum(A, B)", "share(A, B)", "diff(A, B)"):
        assert beat in nothing_on, beat


def test_the_computed_cell_rule_is_the_one_both_halves_implement():
    """One table, two implementations: the guide may only name the calls `tests/cells.json` covers."""
    vectors = json.loads((ROOT / "tests" / "cells.json").read_text(encoding="utf-8"))["vectors"]
    payloads = " ".join(vector["payload"] for vector in vectors)
    for name in ("sum(", "share(", "diff("):
        assert name in payloads, name
        assert name in agent.FORMAT_GUIDE, name


def test_the_settings_file_declares_the_guide_on_by_default():
    # the definitions left plugin.yaml with the config_schema; dashboard/settings.json holds them now
    settings = json.loads((ROOT / "dashboard" / "settings.json").read_text(encoding="utf-8"))["settings"]
    assert settings["format_guide"]["default"] is True
    # and the module's own default is that same truth, not a copy that quietly disagrees
    assert agent.DEFAULT_FORMAT_GUIDE is True


def test_the_shipped_rule_groups_name_every_group_that_has_rules():
    """Every group in the table is either on, or off AND declared: nothing goes quiet by accident.

    The five subject names this list used to carry (`words`, `recipe`, `route`, `nutrition`, `matches`)
    had no rules behind them; the shapes (`records`, `grid`, `events`, `groups`) are what replaced them.
    `changes` is the one off group — the host draws its own changed-files list — so it must be in
    `DEFAULT_RULE_GROUPS_OFF`, which is the only licence to be missing from the default.
    """
    declared = agent.DEFAULT_RULE_GROUPS.split(",")
    assert len(declared) == len(set(declared)), declared
    groups = {str(rule["group"]) for rule in agent.load_rules(agent.RULES_PATH)}
    off = set(agent.DEFAULT_RULE_GROUPS_OFF)
    assert set(declared) == groups - off, sorted(groups - off - set(declared))
    assert off <= groups, "a declared-off group must still have rules: %s" % sorted(off - groups)
    assert not (off & set(declared)), "a group cannot be both on and declared off"
    assert off == {"changes"}, "the only off group is `changes`, and that is a deliberate exception"
    # `structure` is on because structuring the answer is the point
    assert "structure" in declared
    # and the settings page reads its own definitions from dashboard/settings.json, so the two
    # cannot drift — there is no config_schema in plugin.yaml to hold this default any more.
    settings = json.loads((ROOT / "dashboard" / "settings.json").read_text(encoding="utf-8"))
    assert settings["settings"]["rule_groups"]["default"] == agent.DEFAULT_RULE_GROUPS


def test_a_group_toggled_while_running_is_read_again():
    """A setting changed in the settings page is read on the next call, not frozen at register.

    Both channels re-read the config: the sections when a session starts, and the hook on every answer —
    so enabling a group takes effect without a restart, and a kind that was out of the prompt is offered
    again from the next session on.
    """
    ctx = FakeCtx()
    agent.register(ctx)
    kinds = _section(ctx, agent.KINDS_SECTION_ID)["content"]
    hook = ctx.hooks[0][1]

    assert "`changes`" not in kinds({"platform": "desktop"}), "off: the shipped groups do not name it"
    # the user switches the group on while the process is running
    ctx.config["rule_groups"] = agent.DEFAULT_RULE_GROUPS + ",changes"
    assert "`changes`" in kinds({"platform": "desktop"}), "the section reads the groups again"
    assert hook("### Changes\n\nsrc/derive.py +120 -8\ntests/test_hook.py +30 -2\n", platform="desktop"), (
        "and the hook derives from the group it was just given"
    )


def test_a_group_that_is_off_is_a_derivation_gate_not_a_capability_gate():
    """The prompt is the only thing a disabled group changes: the core still draws every kind it has.

    So an answer that already carries a directive is left exactly as written — the transform neither
    strips it nor re-derives it — and the desktop core renders `changes` on request however the group is
    set.  Turning a group off cannot reach into a drawing, only into what the model is told about.
    """
    hook = agent.make_hook(agent.load_rules(agent.RULES_PATH), groups="numbers,tables", max_widgets=3)
    written = 'Done. Two files.\n\n::viz{k="changes" d="a.mjs=+12=-3"}\n'
    assert hook(written, platform="desktop") is None, "a directive the model wrote is left alone"
    assert hook(written, platform="cli") is not None, "and on a surface that cannot draw it comes back out"


def test_the_guide_kinds_are_the_prompt_s_own_list():
    """`guide_kinds` is what the settings page counts, so it has to be the same list the text names."""
    all_groups = ALL_GROUPS
    named = agent.guide_kinds(all_groups)
    assert "changes" in named and "section" in named and "board" in named
    kinds_text = agent.kinds_section(True, all_groups)
    for kind in named:
        assert "`%s`" % kind in kinds_text, kind
    # and the shipped list is the same list minus the gated kind
    shipped = agent.guide_kinds()
    assert "changes" not in shipped
    assert sorted(shipped) == sorted(k for k in named if k != "changes")
    # a kind no rule emits survives every group being off
    for kind in ("line", "table", "words", "section", "board"):
        assert kind in agent.guide_kinds("")
