"""Test helper — load the plugin's root module the way the tests need it.

Puts the repo root on ``sys.path`` (so ``python.derive`` imports directly) and loads ``__init__.py``
by path, the way Hermes' loader does.
"""

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_NAME = "hermes_viz_under_test"


def _load():
    if _NAME in sys.modules:
        return sys.modules[_NAME]
    spec = importlib.util.spec_from_file_location(_NAME, ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_NAME] = module
    spec.loader.exec_module(module)
    return module


agent = _load()
RULES = agent.load_rules(agent.RULES_PATH)
