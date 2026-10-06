"""The hook: it appends widgets to the answer, or returns None and never touches the text."""

from _agent import RULES, agent
from answers import ANSWER_WITH_TABLE_AND_RUN, PROSE_ONLY, STEPS_ANSWER, TWO_ROW_RUN

transform = agent.transform
make_hook = agent.make_hook


class FakeCtx:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.hooks = []

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_the_hook_appends_the_derived_widgets():
    out = transform(ANSWER_WITH_TABLE_AND_RUN, RULES, "numbers,tables,steps", 3, "dark")

    assert out is not None
    assert out.startswith(ANSWER_WITH_TABLE_AND_RUN.rstrip())
    body = out[len(ANSWER_WITH_TABLE_AND_RUN.rstrip()) :]
    lines = [line for line in body.splitlines() if line.strip()]

    assert len(lines) == 3
    assert lines[0] == '::viz{k="bars" d="Build=42;Test=18;Package=7" t="Timing"}'
    assert lines[1] == (
        '::viz{k="bars" d="h=Board|Runs|Failures;291e=42=1;296e=28=0;208e=17=2" t="Board runs"}'
    )
    assert lines[2] == (
        '::viz{k="table" d="h=Board|Runs|Failures;291e|42|1;296e|28|0;208e|17|2" t="Board runs"}'
    )
    for line in lines:
        assert line.startswith("::viz{") and "{" not in line[6:-1] and len(line) <= 1200


def test_a_prose_only_answer_is_left_alone():
    assert transform(PROSE_ONLY, RULES, "numbers,tables,steps", 3, "dark") is None
    assert transform("", RULES, "numbers,tables,steps", 3, "dark") is None


def test_an_answer_that_already_carries_a_directive_is_left_alone():
    text = 'See this:\n\n::viz{k="bars" d="a=1;b=2"}\n'
    assert transform(text, RULES, "numbers,tables,steps", 3, "dark") is None


def test_max_widgets_and_rule_groups_reach_the_hook():
    assert transform(ANSWER_WITH_TABLE_AND_RUN, RULES, "tables", 1, "dark").count("::viz{") == 1
    assert transform(ANSWER_WITH_TABLE_AND_RUN, RULES, "steps", 3, "dark") is None
    assert transform(TWO_ROW_RUN, RULES, "numbers", 1, "dark").endswith(
        '::viz{k="kpi" d="Builds=128;Failures=3" t="Delta"}\n'
    )
    assert "::viz{k=\"steps\" d=\"Read the archive;Verify the pin;Flash the board;Confirm the LED\"" in (
        transform(STEPS_ANSWER, RULES, "steps", 3, "dark")
    )


def test_register_wires_the_transform_hook_from_the_config():
    ctx = FakeCtx({"palette": "light", "max_widgets": 1, "rule_groups": "tables"})
    agent.register(ctx)

    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    hook = ctx.hooks[0][1]

    # max_widgets=1 and group=tables: only the first table rule's widget survives
    out = hook(ANSWER_WITH_TABLE_AND_RUN, session_id="s", model="m", platform="cli")
    assert out is not None
    assert out.count("::viz{") == 1
    assert hook(PROSE_ONLY) is None


def test_register_falls_back_to_the_declared_defaults():
    ctx = FakeCtx()
    agent.register(ctx)
    hook = ctx.hooks[0][1]
    out = hook(ANSWER_WITH_TABLE_AND_RUN)
    assert out is not None and out.count("::viz{") == 3


def test_it_loads_the_way_hermes_loads_a_plugin_package():
    """Hermes builds the spec with submodule_search_locations, so the package path is the real one."""
    import importlib.util
    import pathlib
    import sys

    root = pathlib.Path(agent.__file__).resolve().parent
    assert agent.__file__ is not None
    name = "hermes_viz_packaged_test"
    spec = importlib.util.spec_from_file_location(
        name, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    module.__package__ = name
    module.__path__ = [str(root)]
    sys.modules[name] = module
    spec.loader.exec_module(module)

    ctx = FakeCtx({"rule_groups": "numbers,tables,steps"})
    module.register(ctx)
    assert [hook_name for hook_name, _ in ctx.hooks] == ["transform_llm_output"]
    out = ctx.hooks[0][1](ANSWER_WITH_TABLE_AND_RUN)
    assert out is not None and out.count("::viz{") == 3
