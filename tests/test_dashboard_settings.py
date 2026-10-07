"""The settings page owns its definitions and its writes, with no manifest schema.

``config_schema`` is gone from ``plugin.yaml``, so the app folds no auto-generated "Agent settings"
form under the plugin's own page. ``dashboard/plugin_api.py`` reads the four definitions from
``dashboard/settings.json`` and writes through ``hermes_cli.plugins_state.save_plugin_setting``.

These run without the host: fastapi, pydantic and the Hermes CLI are stubbed the way
``dashboard/preview/fixture.py`` stubs them, and the stubbed writer records where a value lands, so
the assertions are about this plugin's own logic. The write lands under ``plugins.entries.
hermes-viz.settings`` — the exact subtree the agent half reads through ``ctx.get_config``.
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "dashboard" / "plugin_api.py"
SETTINGS_JSON = ROOT / "dashboard" / "settings.json"
PLUGIN_YAML = ROOT / "plugin.yaml"

# The fake profile config the stubbed writer mutates — the same subtree the plugin reads.
CONFIG = {}


def _install_host_stubs():
    fastapi = types.ModuleType("fastapi")
    fastapi.APIRouter = lambda: types.SimpleNamespace(
        get=lambda *a, **k: (lambda f: f),
        put=lambda *a, **k: (lambda f: f),
    )

    class HTTPException(Exception):
        def __init__(self, status_code=400, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.HTTPException = HTTPException

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    pydantic.BaseModel = BaseModel

    hermes_cli = types.ModuleType("hermes_cli")
    hermes_cli.__path__ = []

    config_mod = types.ModuleType("hermes_cli.config")
    config_mod.load_config_readonly = lambda: CONFIG

    plugins_settings = types.ModuleType("hermes_cli.plugins_settings")

    def _plugin_relative_segments(key):
        if not isinstance(key, str) or not key:
            raise ValueError("Expected a plugin-relative config key string")
        return tuple(key.split("."))

    plugins_settings._plugin_relative_segments = _plugin_relative_segments

    plugins_state = types.ModuleType("hermes_cli.plugins_state")

    def save_plugin_setting(plugin_id, segments, value):
        node = CONFIG.setdefault("plugins", {}).setdefault("entries", {}).setdefault(plugin_id, {})
        node = node.setdefault("settings", {})
        for segment in segments[:-1]:
            node = node.setdefault(segment, {})
        node[segments[-1]] = value

    plugins_state.save_plugin_setting = save_plugin_setting

    for name, module in (
        ("fastapi", fastapi),
        ("pydantic", pydantic),
        ("hermes_cli", hermes_cli),
        ("hermes_cli.config", config_mod),
        ("hermes_cli.plugins_settings", plugins_settings),
        ("hermes_cli.plugins_state", plugins_state),
    ):
        sys.modules[name] = module


def _load_api():
    _install_host_stubs()
    spec = importlib.util.spec_from_file_location("hermes_viz_dashboard_api_under_test", API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = _load_api()


def _put(key, value):
    """Drive the FastAPI coroutine directly — the page's PUT, without a server."""
    return asyncio.run(api.put_setting(api.Setting(key=key, value=value)))


def test_a_setting_written_through_the_page_lands_in_the_plugin_settings_subtree():
    result = _put("palette", "light")

    assert CONFIG["plugins"]["entries"]["hermes-viz"]["settings"]["palette"] == "light"
    assert result["written"] == {"key": "palette", "value": "light"}
    # the response reloads from the same store, so the page can show what it just wrote
    assert {f["key"]: f["value"] for f in result["fields"]}["palette"] == "light"


def test_an_unknown_key_is_refused():
    try:
        _put("colour", "red")
    except api.HTTPException as exc:
        assert exc.status_code == 400, exc.status_code
        assert "not editable" in exc.detail
    else:
        raise AssertionError("an undeclared key was accepted")


def test_a_bad_value_is_refused():
    for key, value in (("palette", "neon"), ("max_widgets", 99), ("max_widgets", -1),
                       ("format_guide", "maybe"), ("rule_groups", "bogus")):
        try:
            _put(key, value)
        except api.HTTPException as exc:
            assert exc.status_code == 400, (key, value, exc.status_code)
        else:
            raise AssertionError(f"{key}={value!r} was accepted")


def test_a_known_rule_group_is_still_accepted():
    _put("rule_groups", "tables,steps")
    assert CONFIG["plugins"]["entries"]["hermes-viz"]["settings"]["rule_groups"] == "tables,steps"


def test_the_manifest_carries_no_config_schema():
    # no schema, no auto-generated sub-page — the plugin owns its definitions instead
    assert "config_schema" not in PLUGIN_YAML.read_text(encoding="utf-8")


def test_the_field_list_is_the_plugins_own_definitions():
    definitions = json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))["settings"]
    fields = {field["key"]: field for field in api._fields()}

    assert set(fields) == set(definitions)
    assert fields["palette"]["choices"] == ["dark", "light", "mermaid"]
    assert fields["palette"]["type"] == "enum"
    assert fields["max_widgets"]["type"] == "number"
    assert fields["max_widgets"]["default"] == 3
    assert fields["format_guide"]["type"] == "boolean"
    assert fields["rule_groups"]["default"] == definitions["rule_groups"]["default"]
