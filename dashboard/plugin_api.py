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

**Every group is explained.** ``groups.json`` carries one title, one plain-language blurb and one
section per group — a name alone tells a reader nothing, so a group with no note is a bug, not a
default. ``make_samples.mjs`` renders what each group draws from the pure core into ``samples.json``;
the page shows it, so a toggle is not the only thing a reader has to go on. Neither file is code:
a new group is a data row here as much as it is in ``rules.yaml``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_log = logging.getLogger(__name__)
router = APIRouter()

PLUGIN_ID = "hermes-viz"
PLUGIN_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = PLUGIN_DIR / "rules.yaml"
HERE = Path(__file__).resolve().parent
GROUPS_PATH = HERE / "groups.json"
SAMPLES_PATH = HERE / "samples.json"
SETTINGS_PATH = f"plugins.entries.{PLUGIN_ID}.settings"

# The three palettes plugin.yaml names in prose. Kept here because `palette`'s config_schema carries
# no machine-readable choices; a fourth palette must edit plugin.yaml's description and this tuple.
PALETTES: tuple = ("dark", "light", "mermaid")

# `max_widgets` is a bounded number, and the page offers it as a bounded dropdown for that reason.
MAX_WIDGETS_CEILING = 10

_GROUP_LINE_RE = re.compile(r"^\s*group:\s*([A-Za-z0-9_.-]+)\s*$")


def _rules() -> list[Mapping[str, Any]]:
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


def _notes() -> dict[str, Any]:
    """``groups.json``: the per-group title, blurb, section and sample spec, plus the section order.

    Read fresh on every request (it is 8 KB) so an edit shows without a restart, the same bargain
    ``rules.yaml`` makes. A missing or unreadable file degrades to ``{}`` — the page then falls back
    to the group id, but ``selfcheck.py`` fails the build long before that ships.
    """
    try:
        data = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        _log.warning("hermes-viz: could not read %s", GROUPS_PATH)
        return {}


def _samples() -> dict[str, Any]:
    """``samples.json``: the group-keyed markup rendered from the pure core, plus its CSS.

    The markup is produced by ``desktop/render/core.mjs`` at build time and checked for drift by
    ``selfcheck.py``, so the page shows a real drawing without carrying a second renderer.
    """
    try:
        data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        _log.warning("hermes-viz: could not read %s", SAMPLES_PATH)
        return {}


def _group_rows(active: list[str]) -> list[dict[str, Any]]:
    """One row per distinct ``group`` in declaration order.

    Each row carries its rule count and active flag (from ``rules.yaml``), the kinds it draws, and the
    title, one-line blurb, section and rendered sample from ``groups.json`` / ``samples.json``. A group
    the notes have never heard of still gets a row — named by its id, in a fallback section — because a
    switch that exists must be visible; ``selfcheck.py`` is what refuses to let it ship unnamed.
    """
    notes = _notes().get("groups") or {}
    samples = _samples().get("markup") or {}
    order: list[str] = []
    counts: dict[str, int] = {}
    kinds: dict[str, list[str]] = {}
    for rule in _rules():
        group = str(rule.get("group") or "").strip()
        if not group:
            continue
        if group not in counts:
            order.append(group)
            counts[group] = 0
            kinds[group] = []
        counts[group] += 1
        kind = str(rule.get("kind") or "").strip()
        if kind and kind not in kinds[group]:
            kinds[group].append(kind)
    rows: list[dict[str, Any]] = []
    for group in order:
        note = notes.get(group) or {}
        rows.append({
            "id": group,
            "title": str(note.get("title") or group),
            "blurb": str(note.get("blurb") or ""),
            "category": str(note.get("category") or "other"),
            "rules": counts[group],
            "kinds": kinds[group],
            "active": group in active,
            "sample": samples.get(group) or "",
            "sample_kind": (note.get("sample") or {}).get("k") or "",
        })
    return rows


def _fields() -> list[dict[str, Any]]:
    """The plugin's declared settings fields with their current values (the shared reader)."""
    from hermes_cli.plugins_settings import plugin_settings_fields

    return plugin_settings_fields(PLUGIN_ID, PLUGIN_DIR)


def _config_path() -> str:
    try:
        from hermes_cli.config import get_config_path

        return str(get_config_path())
    except Exception:
        return ""


def _sections(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The groups folded into their sections, in the order ``groups.json`` declares them.

    This is what turns 30 switches into four decisions: the page renders one block per section
    instead of one flat list. A group whose section the notes do not name lands in a trailing
    "More" block rather than vanishing — visible and named, which is the whole requirement.
    """
    notes = _notes()
    declared = [c for c in (notes.get("categories") or []) if isinstance(c, Mapping)]
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(row["category"], []).append(row)

    sections: list[dict[str, Any]] = []
    seen: set = set()
    for category in declared:
        cid = str(category.get("id") or "").strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        members = buckets.get(cid) or []
        if not members:
            continue
        sections.append({
            "id": cid,
            "title": str(category.get("title") or cid),
            "blurb": str(category.get("blurb") or ""),
            "groups": members,
        })

    rest = [row for row in rows if row["category"] not in seen]
    if rest:
        sections.append({
            "id": "more",
            "title": "More groups",
            "blurb": "Groups with no section of their own yet — give them one in groups.json.",
            "groups": rest,
        })
    return sections


def _field_default(fields: list[dict[str, Any]], key: str, fallback: Any = None) -> Any:
    for field in fields:
        if field.get("key") == key and field.get("default") is not None:
            return field.get("default")
    return fallback


def field_default_int(fields: list[dict[str, Any]], key: str, fallback: int = 0) -> int:
    """The declared integer default for a key, coerced — the store can hold it as a string."""
    try:
        return int(str(_field_default(fields, key, fallback)).strip())
    except (TypeError, ValueError):
        return fallback


def _truthy(value: Any) -> bool:
    """A checkbox may reach the store as a bool or as the string it was serialized to."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "on", "yes")


def _resolved() -> dict[str, Any]:
    """Everything the page shows, in one payload: the schema fields, the group list folded into its
    sections, the rendered samples, and where all of it came from. A settings page's first job is
    answering "why is this value not taking effect", so the store path and the rules path are explicit.
    """
    fields = _fields()
    current = {str(f.get("key")): f.get("value") for f in fields}
    raw_groups = current.get("rule_groups")
    active = [part.strip() for part in str(raw_groups or "").split(",") if part.strip()]
    rows = _group_rows(active)
    widgets = current.get("max_widgets")
    try:
        widgets = None if widgets is None else int(str(widgets).strip())
    except (TypeError, ValueError):
        widgets = field_default_int(fields, "max_widgets")
    return {
        "plugin": PLUGIN_ID,
        "settings_path": SETTINGS_PATH,
        "config_path": _config_path(),
        "rules_path": str(RULES_PATH),
        "fields": fields,
        "palettes": list(PALETTES),
        "max_widgets_ceiling": MAX_WIDGETS_CEILING,
        "samples_css": str((_samples().get("css") or "")),
        "current": {
            "palette": str(current.get("palette") or _field_default(fields, "palette", "dark")),
            "max_widgets": widgets,
            "rule_groups": active,
            "format_guide": _truthy(current.get("format_guide")),
        },
        "sections": _sections(rows),
        "groups": rows,
    }


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    try:
        return _resolved()
    except Exception:
        _log.exception("hermes-viz settings read failed")
        raise HTTPException(status_code=500, detail="Could not read the hermes-viz settings")


class Setting(BaseModel):
    key: str
    value: Any = None


def _known_groups() -> list[str]:
    return [row["id"] for row in _group_rows([])]


def _coerce(key: str, value: Any) -> Any:
    """Validate one field before the shared writer sees it. Raises HTTPException(400) on anything the
    page could not have meant, so a bad request reads as a bad request, not a server error."""
    if key == "max_widgets":
        if isinstance(value, bool) or value is None:
            raise HTTPException(status_code=400, detail="max_widgets must be a whole number")
        try:
            number = value if isinstance(value, int) else int(str(value).strip())
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_widgets must be a whole number")
        if number < 0 or number > MAX_WIDGETS_CEILING:
            raise HTTPException(
                status_code=400,
                detail=f"max_widgets must be between 0 and {MAX_WIDGETS_CEILING}",
            )
        return number
    if key == "palette":
        text = str(value or "").strip()
        if text not in PALETTES:
            raise HTTPException(status_code=400, detail="palette must be one of " + ", ".join(PALETTES))
        return text
    if key == "format_guide":
        # A toggle, so the page can only mean on or off — accept what a checkbox sends, reject prose.
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "1", "on", "yes"):
            return True
        if text in ("false", "0", "off", "no"):
            return False
        raise HTTPException(status_code=400, detail="format_guide must be true or false")
    if key == "rule_groups":
        known = _known_groups()
        requested = [part.strip() for part in str(value or "").split(",") if part.strip()]
        unknown = [part for part in requested if part not in known]
        if unknown:
            raise HTTPException(status_code=400, detail="unknown rule group(s): " + ", ".join(unknown))
        seen: list[str] = []
        for part in requested:
            if part not in seen:
                seen.append(part)
        return ",".join(seen)
    raise HTTPException(status_code=400, detail=f"{key!r} is not editable from this page")


@router.put("/settings")
async def put_setting(setting: Setting) -> dict[str, Any]:
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
