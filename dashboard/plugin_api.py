"""hermes-viz dashboard plugin — backend API routes.

Mounted by the Hermes web server at ``/api/plugins/hermes-viz/`` while the plugin is enabled.

Routes:
    GET  /settings           the plugin's config_schema fields, the palettes, and the rule groups
    PUT  /settings           write one value into this plugin's settings subtree

**One store.** The page writes exactly the subtree the plugin reads — ``plugins.entries.hermes-viz.
settings`` — through ``hermes_cli.plugins_settings.save_plugin_settings``, the same writer
``ctx.set_config`` and the Desktop Plugins pane use. There is no mirror and no second precedence
level, so a value changed here is the value the transform hook reads on its next call; that
round-trip is the whole point of this page. Reads go through ``plugin_settings_fields`` for the same
reason: the page and the plugin can never disagree about a default.

**Derivation is data.** The rule groups are read from ``rules.yaml`` rather than hard-coded, so
adding a rule with a new ``group`` there makes the toggle appear here without touching this code.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_log = logging.getLogger(__name__)
router = APIRouter()

PLUGIN_ID = "hermes-viz"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = PLUGIN_DIR / "rules.yaml"
SETTINGS_PATH = f"plugins.entries.{PLUGIN_ID}.settings"

# The three palettes plugin.yaml names in prose. Kept here because `palette`'s config_schema carries
# no machine-readable choices; a fourth palette must edit plugin.yaml's description and this tuple.
PALETTES: tuple = ("dark", "light", "mermaid")

_GROUP_LINE_RE = re.compile(r"^\s*group:\s*([A-Za-z0-9_.-]+)\s*$")


def _rules() -> List[Mapping[str, Any]]:
    """The rule rows from ``rules.yaml``, or ``[]`` when the file is missing or unreadable.

    ``fast_safe_load`` is the same loader the host uses for plugin YAML; the regex fallback keeps the
    group list derived even if that import is unavailable, so an added group still shows up.
    """
    if not RULES_PATH.is_file():
        return []
    text = RULES_PATH.read_text(encoding="utf-8-sig")
    try:
        from utils import fast_safe_load

        data = fast_safe_load(text) or {}
        rules = data.get("rules") if isinstance(data, Mapping) else None
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, Mapping)]
    except Exception:
        _log.debug("hermes-viz: fast_safe_load failed for %s; falling back to a line scan", RULES_PATH)
    return [{"group": m.group(1)} for m in (_GROUP_LINE_RE.match(line) for line in text.splitlines()) if m]


def _group_rows(active: List[str]) -> List[Dict[str, Any]]:
    """One row per distinct ``group`` in declaration order, with its rule count and active flag."""
    order: List[str] = []
    counts: Dict[str, int] = {}
    for rule in _rules():
        group = str(rule.get("group") or "").strip()
        if not group:
            continue
        if group not in counts:
            order.append(group)
            counts[group] = 0
        counts[group] += 1
    return [{"id": group, "rules": counts[group], "active": group in active} for group in order]


def _fields() -> List[Dict[str, Any]]:
    """The plugin's declared settings fields with their current values (the shared reader)."""
    from hermes_cli.plugins_settings import plugin_settings_fields

    return plugin_settings_fields(PLUGIN_ID, PLUGIN_DIR)


def _config_path() -> str:
    try:
        from hermes_cli.config import get_config_path

        return str(get_config_path())
    except Exception:
        return ""


def _resolved() -> Dict[str, Any]:
    """Everything the page shows, in one payload: the schema fields, the derived group list, and
    where both came from. A settings page's first job is answering "why is this value not taking
    effect", so the store path and the rules path are explicit."""
    fields = _fields()
    current = {str(f.get("key")): f.get("value") for f in fields}
    raw_groups = current.get("rule_groups")
    active = [part.strip() for part in str(raw_groups or "").split(",") if part.strip()]
    return {
        "plugin": PLUGIN_ID,
        "settings_path": SETTINGS_PATH,
        "config_path": _config_path(),
        "rules_path": str(RULES_PATH),
        "fields": fields,
        "palettes": list(PALETTES),
        "current": {
            "palette": current.get("palette") or "dark",
            "max_widgets": current.get("max_widgets"),
            "rule_groups": active,
        },
        "groups": _group_rows(active),
    }


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    try:
        return _resolved()
    except Exception:
        _log.exception("hermes-viz settings read failed")
        raise HTTPException(status_code=500, detail="Could not read the hermes-viz settings")


class Setting(BaseModel):
    key: str
    value: Any = None


def _known_groups() -> List[str]:
    return [row["id"] for row in _group_rows([])]


def _coerce(key: str, value: Any) -> Any:
    """Validate one field before the shared writer sees it. Raises HTTPException(400) on anything the
    page could not have meant, so a bad request reads as a bad request, not a server error."""
    if key == "max_widgets":
        if isinstance(value, bool) or value is None:
            raise HTTPException(status_code=400, detail="max_widgets must be a whole number")
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_widgets must be a whole number")
    if key == "palette":
        text = str(value or "").strip()
        if text not in PALETTES:
            raise HTTPException(status_code=400, detail="palette must be one of " + ", ".join(PALETTES))
        return text
    if key == "rule_groups":
        known = _known_groups()
        requested = [part.strip() for part in str(value or "").split(",") if part.strip()]
        unknown = [part for part in requested if part not in known]
        if unknown:
            raise HTTPException(status_code=400, detail="unknown rule group(s): " + ", ".join(unknown))
        seen: List[str] = []
        for part in requested:
            if part not in seen:
                seen.append(part)
        return ",".join(seen)
    raise HTTPException(status_code=400, detail=f"{key!r} is not editable from this page")


@router.put("/settings")
async def put_setting(setting: Setting) -> Dict[str, Any]:
    value = _coerce(setting.key, setting.value)
    try:
        from hermes_cli.plugins_settings import save_plugin_settings

        save_plugin_settings(PLUGIN_ID, PLUGIN_DIR, {setting.key: value})
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("hermes-viz settings write failed")
        raise HTTPException(status_code=500, detail=f"Could not write {setting.key}: {exc}") from exc
    resolved = _resolved()
    resolved["written"] = {"key": setting.key, "value": value}
    return resolved
