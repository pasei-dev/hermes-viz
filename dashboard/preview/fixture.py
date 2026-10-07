#!/usr/bin/env python3
"""Print the exact GET /settings payload the page fetches, so the preview renders real data.

The dashboard bundle is useless without the host: it needs the SDK globals *and* a server. Rather
than hand-write a fixture (which would drift from plugin_api.py the moment a group is added), this
imports the real module with a small stub for the bits only the host provides (fastapi, pydantic, the
shared settings reader) and dumps `_resolved()`. The settings reader is stubbed by reading the four
fields straight out of plugin.yaml, so the labels and the cost text on the page are the real ones.

    python3 dashboard/preview/fixture.py
"""

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_DIR = HERE.parent.parent
API_PATH = HERE.parent / "plugin_api.py"
PLUGIN_YAML = PLUGIN_DIR / "plugin.yaml"


def parse_config_schema(text):
    """A minimal reader for plugin.yaml's `config_schema:` block (str/int/bool + `>-` folded prose).

    Deliberately tiny: this is a preview helper, and PyYAML is not a dependency of the plugin. It
    handles exactly the shape plugin.yaml uses — a 2-space key, 4-space attributes, and `>-` blocks.
    """
    fields = []
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "config_schema:"), None)
    if start is None:
        return fields
    current = None
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() and not line.startswith("  "):
            break
        m_key = re.match(r"^  ([A-Za-z0-9_]+):\s*$", line)
        if m_key:
            current = {"key": m_key.group(1)}
            fields.append(current)
            i += 1
            continue
        if current is not None:
            m_attr = re.match(r"^    ([A-Za-z0-9_]+):\s*(.*)$", line)
            if m_attr:
                name, value = m_attr.group(1), m_attr.group(2).strip()
                if value in (">-", ">", "|", "|-"):
                    block = []
                    i += 1
                    while i < len(lines) and (not lines[i].strip() or lines[i].startswith("      ")):
                        block.append(lines[i].strip())
                        i += 1
                    current[name] = " ".join(part for part in block if part)
                    continue
                current[name] = value.strip('"')
        i += 1
    return fields


def _stub_host():
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
    sys.modules["fastapi"] = fastapi

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        pass

    pydantic.BaseModel = BaseModel
    sys.modules["pydantic"] = pydantic

    # The shared settings reader, stubbed from plugin.yaml.
    hermes_cli = types.ModuleType("hermes_cli")
    plugins_settings = types.ModuleType("hermes_cli.plugins_settings")

    def plugin_settings_fields(plugin_id, plugin_dir):
        text = Path(plugin_dir, "plugin.yaml").read_text(encoding="utf-8")
        out = []
        for field in parse_config_schema(text):
            kind = field.get("type", "str")
            default = field.get("default", "")
            if kind == "int":
                try:
                    default = int(default)
                except (TypeError, ValueError):
                    default = 0
            elif kind == "bool":
                default = str(default).strip().lower() == "true"
            out.append({
                "key": field.get("key"),
                "label": field.get("label", field.get("key")),
                "description": field.get("description", ""),
                "type": kind,
                "default": default,
                "value": default,
            })
        return out

    plugins_settings.plugin_settings_fields = plugin_settings_fields
    hermes_cli.plugins_settings = plugins_settings
    sys.modules["hermes_cli"] = hermes_cli
    sys.modules["hermes_cli.plugins_settings"] = plugins_settings


def main():
    _stub_host()
    spec = importlib.util.spec_from_file_location("hermes_viz_dashboard_api", API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module._resolved()
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
