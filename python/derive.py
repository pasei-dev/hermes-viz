"""Derivation — the matchers named in ``rules.yaml``, plus the spec builder.

Pure functions: no I/O, no clock, no environment.  ``load_rules`` is the one exception and lives here
only so the rule schema and its reader sit together.

A **match** is a dict::

    {"rows":   [["291e", "42", "1"], ["296e", "28", "0"]],
     "header": ["Board", "Runs", "Failures"],   # or None
     "unit":   "%",                             # or None, from a number run
     "title":  "Board runs"}                    # or None, from the heading above the block

A **spec** is that plus the ``kind`` the rule asked for — what ``viz_dsl`` encodes.

Matchers take the answer's *lines* with fenced blocks already blanked (see ``_unfenced``), so a table
inside a code block is invisible to them.
"""

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "derive",
    "load_rules",
    "MATCHERS",
    "match_number_run",
    "match_table",
    "match_steps_list",
    "match_key_numbers",
]

# ------------------------------------------------------------------------------------------------
# shared shapes


_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_NUMBER_RE = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?\s*%?$")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BOLD_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")

# `Label: 12`, `Label — 12`, `- Label = 12`, `Label: 12 %`, `Label: 12 runs`
_NUMBER_RUN_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<label>[^:—–=]{1,60}?)[ \t]*[:—–=][ \t]*"
    r"(?P<value>[-+]?\d[\d,]*(?:\.\d+)?)[ \t]*(?P<unit>%|[A-Za-z][A-Za-z/]{0,9})?[ \t]*$"
)
_STEP_RE = re.compile(r"^[ \t]*\d{1,2}[.)][ \t]+(?P<text>.{1,80}?)[ \t]*$")


def _unfenced(text: str) -> List[str]:
    """The answer's lines with every fenced code block blanked out, line count preserved."""
    lines: List[str] = []
    fenced = False
    for line in str(text).splitlines():
        if _FENCE_RE.match(line):
            fenced = not fenced
            lines.append("")
        else:
            lines.append("" if fenced else line)
    return lines


def _title_before(lines: List[str], index: int) -> Optional[str]:
    """The heading (or all-bold line) directly above a block, else None."""
    i = index - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return None
    for pattern in (_HEADING_RE, _BOLD_RE):
        found = pattern.match(lines[i])
        if found:
            return found.group(1).strip()
    return None


def _is_number(cell: str) -> bool:
    return bool(_NUMBER_RE.match(cell.strip()))


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_delimiter(line: str) -> bool:
    stripped = line.strip()
    if "|" not in stripped or "-" not in stripped:
        return False
    return all(char in "|-: \t" for char in stripped)


def _tables(lines: List[str]) -> Iterable[Dict[str, Any]]:
    """Every markdown pipe table: a header row, a ``|---|`` delimiter, then body rows."""
    i = 0
    while i < len(lines):
        if (
            "|" in lines[i]
            and i + 1 < len(lines)
            and _is_delimiter(lines[i + 1])
            and lines[i].strip()
        ):
            header = _cells(lines[i])
            rows: List[List[str]] = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(_cells(lines[j]))
                j += 1
            yield {"index": i, "header": header, "rows": rows, "title": _title_before(lines, i)}
            i = j
        else:
            i += 1


# ------------------------------------------------------------------------------------------------
# the matchers


def match_number_run(lines: List[str]) -> List[Dict[str, Any]]:
    """Consecutive ``Label: 12`` / ``Label — 12`` / ``- Label: 12`` lines."""
    found: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        rows: List[List[str]] = []
        units = set()
        start = i
        while i < len(lines):
            hit = _NUMBER_RUN_RE.match(lines[i])
            if not hit:
                break
            rows.append([hit.group("label").strip(" *-"), hit.group("value")])
            units.add((hit.group("unit") or "").strip())
            i += 1
        if rows:
            unit = units.pop() if len(units) == 1 else ""
            found.append(
                {
                    "rows": rows,
                    "header": None,
                    "unit": unit or None,
                    "title": _title_before(lines, start),
                }
            )
        else:
            i += 1
    return found


def match_table(lines: List[str]) -> List[Dict[str, Any]]:
    """A markdown pipe table whose body is mostly numeric."""
    found = []
    for table in _tables(lines):
        cells = [cell for row in table["rows"] for cell in row]
        if not cells:
            continue
        numeric = sum(1 for cell in cells if _is_number(cell))
        if numeric * 2 >= len(cells):
            found.append(
                {
                    "rows": table["rows"],
                    "header": table["header"],
                    "unit": None,
                    "title": table["title"],
                }
            )
    return found


def match_key_numbers(lines: List[str]) -> List[Dict[str, Any]]:
    """A table whose first column is text and whose later columns are numbers."""
    found = []
    for table in _tables(lines):
        if len(table["header"]) < 2 or not table["rows"]:
            continue
        if not all(row and not _is_number(row[0]) for row in table["rows"]):
            continue
        later = [cell for row in table["rows"] for cell in row[1:]]
        if later and all(_is_number(cell) for cell in later):
            found.append(
                {
                    "rows": table["rows"],
                    "header": table["header"],
                    "unit": None,
                    "title": table["title"],
                }
            )
    return found


def match_steps_list(lines: List[str]) -> List[Dict[str, Any]]:
    """A run of consecutive ordered-list items."""
    found: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        rows: List[List[str]] = []
        start = i
        while i < len(lines):
            hit = _STEP_RE.match(lines[i])
            if not hit:
                break
            rows.append([hit.group("text").strip()])
            i += 1
        if rows:
            found.append(
                {
                    "rows": rows,
                    "header": None,
                    "unit": None,
                    "title": _title_before(lines, start),
                }
            )
        else:
            i += 1
    return found


MATCHERS = {
    "number-run": match_number_run,
    "table": match_table,
    "steps-list": match_steps_list,
    "key-numbers": match_key_numbers,
}


# ------------------------------------------------------------------------------------------------
# the table


def _parse_simple_yaml(text: str) -> List[Dict[str, Any]]:
    """The ``rules.yaml`` subset: a top-level ``rules:`` key holding a list of scalar maps.

    Only used when PyYAML is absent (the system python3 has none), so the rule table stays readable
    as data in every environment the tests run in.
    """
    rules: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    inside = False
    for raw in str(text).splitlines():
        line = raw.split("#", 1)[0] if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            inside = line.split(":", 1)[0].strip() == "rules"
            continue
        if not inside:
            continue
        item = line.strip()
        if item.startswith("- "):
            item = item[2:]
            current = {}
            rules.append(current)
        if current is None:
            continue
        key, _, value = item.partition(":")
        value = value.strip().strip('"').strip("'")
        if value == "":
            continue
        current[key.strip()] = int(value) if re.fullmatch(r"-?\d+", value) else value
    return rules


def load_rules(path) -> List[Dict[str, Any]]:
    """Read a ``rules.yaml`` into a list of rule dicts."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        return _parse_simple_yaml(text)
    data = yaml.safe_load(text) or {}
    return list(data.get("rules") or [])


# ------------------------------------------------------------------------------------------------
# derive


def _active_groups(groups) -> Optional[set]:
    """The rule groups that may fire.  ``None`` means every group; an empty selection means none."""
    if groups is None:
        return None
    if isinstance(groups, str):
        return {part.strip() for part in groups.split(",") if part.strip()}
    return {str(part).strip() for part in groups if str(part).strip()}


def _as_int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _spec(rule: Dict[str, Any], match: Dict[str, Any]) -> Dict[str, Any]:
    spec = {"kind": str(rule.get("kind") or ""), "rows": [list(row) for row in match["rows"]]}
    if match.get("header"):
        spec["header"] = list(match["header"])
    if match.get("title"):
        spec["title"] = match["title"]
    if match.get("unit"):
        spec["unit"] = match["unit"]
    return spec


def _key(spec: Dict[str, Any]):
    return (
        spec.get("kind"),
        tuple(tuple(row) for row in spec["rows"]),
        tuple(spec.get("header") or ()),
    )


def derive(text: str, rules, groups=None, max_widgets=None) -> List[Dict[str, Any]]:
    """Every widget the rule table asks for, in rule order, capped at ``max_widgets``."""
    limit = _as_int(max_widgets, 0) if max_widgets is not None else 0
    if max_widgets is not None and limit <= 0:
        return []

    active = _active_groups(groups)
    lines = _unfenced(text)
    specs: List[Dict[str, Any]] = []
    seen = set()

    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        group = str(rule.get("group") or "")
        if active is not None and group not in active:
            continue
        matcher = MATCHERS.get(str(rule.get("when") or ""))
        if matcher is None or not rule.get("kind"):
            continue
        low = _as_int(rule.get("min"), 1)
        high = rule.get("max")
        high = _as_int(high, None) if high is not None else None

        for match in matcher(lines):
            count = len(match["rows"])
            if count < low or (high is not None and count > high):
                continue
            spec = _spec(rule, match)
            key = _key(spec)
            if key in seen:
                continue
            seen.add(key)
            specs.append(spec)
            if limit and len(specs) >= limit:
                return specs

    return specs
