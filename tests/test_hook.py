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


def test_the_hook_replaces_the_derived_runs_where_they_stood():
    out = transform(ANSWER_WITH_TABLE_AND_RUN, RULES, "numbers,tables,steps", 3, "dark")

    assert out is not None
    # each derived run is replaced in place: the widget stands where the table and the run stood
    assert "| Alpha | 42 | 1 |" not in out
    assert "- Build: 42" not in out
    boards = [line for line in out.splitlines() if line.startswith("::viz{")]
    assert boards == [
        '::viz{k="board" d="bars:h=Board|Runs|Failures;Alpha=42=1;Beta=28=0;Gamma=17=2"}',
        '::viz{k="board" d="bars:Build=42;Test=18;Package=7"}',
    ]
    # heading, widget, next heading — each widget follows the heading it belongs to
    assert out.index("### Board runs") < out.index(boards[0]) < out.index("### Timing")
    assert out.index("### Timing") < out.index(boards[1])
    for line in boards:
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
        '::viz{k="board" d="kpi:Builds=128;Failures=3"}\n'
    )
    assert "k=\"board\" d=\"steps:Read the archive;Verify the pin" in (
        transform(STEPS_ANSWER, RULES, "steps", 3, "dark")
    )


def test_register_wires_the_transform_hook_from_the_config():
    ctx = FakeCtx({"palette": "light", "max_widgets": 1, "rule_groups": "tables"})
    agent.register(ctx)

    assert [name for name, _ in ctx.hooks] == ["transform_llm_output"]
    hook = ctx.hooks[0][1]

    # max_widgets=1 and group=tables: only the first table rule's widget survives
    out = hook(ANSWER_WITH_TABLE_AND_RUN, session_id="s", model="m", platform="desktop")
    assert out is not None
    assert out.count("::viz{") == 1
    assert hook(PROSE_ONLY) is None


def test_register_falls_back_to_the_declared_defaults():
    ctx = FakeCtx()
    agent.register(ctx)
    hook = ctx.hooks[0][1]
    out = hook(ANSWER_WITH_TABLE_AND_RUN, platform="desktop")
    # the answer's own `##` and its two `###` sub-headings are three sections, and the two runs under
    # them are two boards — a heading the answer already carries is never also drawn as a band, or the
    # reader gets the same words twice
    assert out is not None and out.count("::viz{") == 2
    assert "section:" not in out
    assert "## Build report" in out and "### Board runs" in out and "### Timing" in out


def test_only_the_desktop_surface_is_given_a_directive():
    """A `::viz` directive is grammar for one surface. Everywhere else it is raw text in the transcript.

    The CLI, the TUI, a chat gateway, the dashboard and an API client do not parse the directive, so the
    answer must reach them exactly as the model wrote it — and an unknown platform is treated the same
    way, because no widget is a smaller failure than a line of raw grammar in front of a reader.
    """
    hook = make_hook(RULES, groups="numbers,tables,steps", max_widgets=3, palette="dark")
    for platform in ("cli", "tui", "telegram", "discord", "slack", "dashboard", "api_server",
                     "subagent", "acp", "browser", "", None):
        assert hook(ANSWER_WITH_TABLE_AND_RUN, platform=platform) is None, platform
    assert hook(ANSWER_WITH_TABLE_AND_RUN, platform="desktop") is not None
    assert hook(ANSWER_WITH_TABLE_AND_RUN, platform="Desktop") is not None, "case is not the point"


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
    out = ctx.hooks[0][1](ANSWER_WITH_TABLE_AND_RUN, platform="desktop")
    assert out is not None and out.count("::viz{") == 2  # the table board and the run board, in place
