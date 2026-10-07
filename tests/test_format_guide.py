"""The format guide ships on, and off is still measurably free.

With the setting on, the section appears exactly once — never stacked.  With it off there is no
system-prompt section to register, so the rendered prompt is byte-identical to one from a plugin that
has no guide at all.
"""

import json
import re

from _agent import agent

ROOT = agent.RULES_PATH.parent


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

    def register_system_prompt_section(self, section_id, content, *, position="after_memory", max_chars=4000):
        self.sections.append(
            {"id": section_id, "content": content, "position": position, "max_chars": max_chars}
        )


def test_the_guide_ships_on_and_off_is_still_free():
    # the setting's own contract: off is off, and the section text is what makes it free
    assert agent.DEFAULT_FORMAT_GUIDE is True
    assert agent.format_guide_section(None) is None
    assert agent.format_guide_section(False) is None
    assert agent.format_guide_section("false") is None
    assert agent.format_guide_section("off") is None
    # no setting at all reads the shipped default: the hook *and* the guide's one section
    ctx = FakeCtx()
    agent.register(ctx)
    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    assert len(ctx.sections) == 1
    # The content is a callable now, so the guide can be withheld from a delegate_task child. Assert the
    # behaviour rather than the identity: a main session gets the guide, a child gets nothing.
    content = ctx.sections[0]["content"]
    assert callable(content), "the section must be per-session, or a child cannot be excluded"
    assert content(None) == agent.FORMAT_GUIDE, "a main session still gets the guide"
    assert content({"subagent_id": "sa-0-abc"}) == "", "a delegated child gets no guide"
    assert content({"parent_session_id": "20260101_000000_aaaa"}) == "", "a child session gets no guide"


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
    assert prompt.count(agent.FORMAT_GUIDE) == 1
    # idempotent: an already-guided prompt is never given a second copy
    assert agent.format_guide_prompt(prompt, True) == prompt
    assert agent.format_guide_prompt("true", True) == "true" + "\n\n" + agent.FORMAT_GUIDE


def test_register_adds_exactly_one_section_when_on():
    ctx = FakeCtx({"format_guide": True})
    agent.register(ctx)
    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    assert len(ctx.sections) == 1
    section = ctx.sections[0]
    assert section["id"] == "hermes-viz-format"
    # Per-session by design: the guide is withheld from a delegate_task child, whose answer is read by
    # the orchestrator. Assert the behaviour, not the identity.
    assert callable(section["content"]), "the section must be per-session, or a child cannot be excluded"
    assert section["content"](None) == agent.FORMAT_GUIDE
    assert section["content"]({"subagent_id": "sa-0-abc"}) == ""
    assert section["position"] == "after_memory"
    assert section["max_chars"] == agent.FORMAT_GUIDE_MAX_CHARS


def test_the_guide_carries_the_mandate_and_stays_compact():
    guide = agent.FORMAT_GUIDE
    folded = guide.lower()
    for beat in ("heading", "list", "table", "separator", "when something can be shown", "::viz{"):
        assert beat in folded, beat
    # a prompt on every request: every character of it is paid for, every time
    assert len(guide) < 2000


def test_the_guide_names_every_kind_the_core_draws():
    """A kind the guide omits is a kind the model cannot reach.

    Eight kinds are derived by rules; the rest arrive only through an explicit `::viz`, and the guide is
    the model's only channel to learn they exist — a guide listing the eight leaves thirty-three
    undrawable in practice. Read `KINDS` off the drawing core rather than keeping a second list here.
    """
    text = (ROOT / "desktop" / "render" / "core.mjs").read_text(encoding="utf-8")
    block = text.split("const KINDS = [", 1)[1].split("]", 1)[0]
    kinds = set(re.findall(r"'([a-z0-9-]+)'", block))
    assert len(kinds) == 41, "the core draws %d kinds" % len(kinds)
    omitted = sorted(kind for kind in kinds if "`%s`" % kind not in agent.FORMAT_GUIDE)
    assert not omitted, "the guide omits: %s" % omitted
    # `board` composes the others and is not in `KINDS`; the guide must name it too
    assert "`board`" in agent.FORMAT_GUIDE


def test_the_plugins_settings_file_declares_the_guide_on_by_default():
    # the definitions left plugin.yaml with the config_schema; dashboard/settings.json holds them now
    settings = json.loads((ROOT / "dashboard" / "settings.json").read_text(encoding="utf-8"))["settings"]
    assert settings["format_guide"]["default"] is True
    # and the module's own default is that same truth, not a copy that quietly disagrees
    assert agent.DEFAULT_FORMAT_GUIDE is True


def test_the_shipped_rule_groups_name_every_group_that_has_rules():
    """Every group in the table ships on, and the default names no group the table cannot fire.

    The five subject names this list used to carry (`words`, `recipe`, `route`, `nutrition`, `matches`)
    had no rules behind them; the shapes (`records`, `grid`, `events`, `groups`) are what replaced them.
    """
    declared = agent.DEFAULT_RULE_GROUPS.split(",")
    assert len(declared) == len(set(declared)), declared
    groups = {str(rule["group"]) for rule in agent.load_rules(agent.RULES_PATH)}
    assert set(declared) == groups
    # `structure` is on because structuring the answer is the point; nothing is off by default
    assert "structure" in declared
    # and the settings page reads its own definitions from dashboard/settings.json, so the two
    # cannot drift — there is no config_schema in plugin.yaml to hold this default any more.
    settings = json.loads((ROOT / "dashboard" / "settings.json").read_text(encoding="utf-8"))
    assert settings["settings"]["rule_groups"]["default"] == agent.DEFAULT_RULE_GROUPS
