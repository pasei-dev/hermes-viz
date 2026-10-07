#!/usr/bin/env python3
"""Print the exact GET /settings payload the page fetches, so the preview renders real data.

The dashboard bundle is useless without the host: it needs the SDK globals *and* a server. Rather
than hand-write a fixture (which would drift from plugin_api.py the moment a group is added), this
imports the real module with a small stub for the bits only the host provides (fastapi, pydantic)
and dumps `_resolved()`. The settings definitions are read by the real code from the plugin's own
`dashboard/settings.json`; with no `hermes_cli.config` to read, each field shows its declared
default, which is what a fresh install displays anyway.

    python3 dashboard/preview/fixture.py
"""

import importlib.util
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_PATH = HERE.parent / "plugin_api.py"


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
