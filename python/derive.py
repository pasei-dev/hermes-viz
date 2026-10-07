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

``structure`` is the one writer: it returns the answer with a ``### `` marker inserted in front of each
anchor the answer already treats as a heading, plus the ``section`` spec for each.  It never removes,
rewords or reorders a line — the marker is inserted, the answer's own words stay.
"""

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "derive",
    "load_rules",
    "MATCHERS",
    "STRUCTURE_MATCHERS",
    "structure",
    "match_number_run",
    "match_table",
    "match_steps_list",
]

# ------------------------------------------------------------------------------------------------
# shared shapes


_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_NUMBER_RE = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?\s*%?$")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BOLD_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")
_LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+")

# `Label: 12`, `Label — 12`, `- Label = 12`, `Label: 12 %`, `Label: 12 runs`
_NUMBER_RUN_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<label>[^:—–=]{1,60}?)[ \t]*[:—–=][ \t]*"
    r"(?P<value>[-+]?\d[\d,]*(?:\.\d+)?)[ \t]*(?P<unit>%|[A-Za-z][A-Za-z/]{0,9})?[ \t]*$"
)
_STEP_RE = re.compile(r"^[ \t]*\d{1,2}[.)][ \t]+(?P<text>.{1,80}?)[ \t]*$")

# round 2 — the answer-shaped matchers
_CHECKLIST_RE = re.compile(
    r"^[ \t]*[-*+][ \t]+\[(?P<state>[ xX/~!\\-])\][ \t]+(?P<label>.+?)[ \t]*$"
)
_CHECKLIST_STATES = {
    " ": "todo",
    "x": "done",
    "X": "done",
    "/": "doing",
    "~": "doing",
    "!": "blocked",
    "-": "blocked",
    "\\": "blocked",
}
_CHANGE_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<path>[~./A-Za-z0-9_@-]+)[ \t]+\+(?P<adds>\d+)"
    r"[ \t]+-(?P<dels>\d+)[ \t]*$"
)
_OUTLINE_RE = re.compile(
    r"^[ \t]*(?P<num>\d+(?:\.\d+)+|\d+)[.)]?[ \t]+(?P<text>.{1,90}?)[ \t]*$"
)
_LABEL_VALUE_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<label>[^:—–=]{1,60}?)[ \t]*[:—–][ \t]*(?P<value>.{1,140}?)[ \t]*$"
)
_SETTINGS_TRUE = {"on", "enabled", "true", "yes", "active"}
_SETTINGS_FALSE = {"off", "disabled", "false", "no", "inactive"}
_RANGE_RE = re.compile(
    r"^(?P<lo>[-+]?\d[\d,]*(?:\.\d+)?)[ \t]*(?:\.\.|–|—|-|to)[ \t]*"
    r"(?P<hi>[-+]?\d[\d,]*(?:\.\d+)?)$"
)
_METRIC_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<label>[^:—–=]{1,60}?)[ \t]*[:—–][ \t]*"
    r"(?P<value>[-+]?\d[\d,]*(?:\.\d+)?[ \t]*[A-Za-z%/]{0,6})[ \t]*"
    r"\((?P<delta>[-+]?\d[\d,]*(?:\.\d+)?%?)\)[ \t]*$"
)
_DATE_RE = re.compile(
    r"^(?P<when>\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?"
    r"|\d{1,2}:\d{2}(?::\d{2})?"
    r"|Q[1-4][ \t]*\d{4}|\d{4}[ \t]*Q[1-4]"
    r"|(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[ \t]+\d{1,2})"
)
_PATHISH_RE = re.compile(r"^[~./A-Za-z0-9_@-]+$")
_FILEISH_RE = re.compile(r"^[~./A-Za-z0-9_@-]+\.[A-Za-z0-9]{1,8}$")
_PARTS_REF = {"ref", "refdes", "reference", "part", "partno", "partnumber", "pn"}
_PARTS_QTY = {"qty", "quantity", "count", "qty."}

# round 3 — the UI mock's block run and the candle's OHLC cells. Both use `,`/`:` inside the value, so
# the emitter must keep those and strip only `;` `=` `~` `|` `\` (see viz_dsl.clean_value).
_WIREFRAME_BLOCKS = {"btn", "field", "text", "img", "item", "card", "chart", "circle"}
_WIREFRAME_VALUE_RE = re.compile(r"[a-z]+:[0-9]+(?:[ \t]*,[ \t]*[a-z]+:[0-9]+)*")
_CANDLE_VALUE_RE = re.compile(
    r"[-+]?\d[\d,]*(?:\.\d+)?(?::[-+]?\d[\d,]*(?:\.\d+)?){3}"
)
# an arrow chain: `A -> B -> C` (at least two arrows, so a stray `->` in prose never fires)
_FLOW_RE = re.compile(
    r"^[ \t]*(?P<chain>[A-Za-z0-9_.-]+(?:[ \t]*(?:-->|->|=>|→)[ \t]*[A-Za-z0-9_.-]+){2,})[ \t]*$"
)


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
    """The heading (or all-bold line) directly above a block, else None.

    A ``### **Heading**`` line — a bold pseudo-heading the structure layer has already promoted — keeps
    its text: the ``*`` wrapper is not part of the words.
    """
    i = index - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    if i < 0:
        return None
    for pattern in (_HEADING_RE, _BOLD_RE):
        found = pattern.match(lines[i])
        if found:
            return found.group(1).strip().strip("*").strip()
    return None


def _is_number(cell: str) -> bool:
    return bool(_NUMBER_RE.match(cell.strip()))


def _looks_like_path(text: str) -> bool:
    """A label is a path when it names a directory, or a file with a *real* extension.

    ``a.b`` and ``v1.2`` used to count as files, so a dotted prose label was misread as one.  A bare
    name now needs an alphabetic extension of at least two characters (``rules.yaml`` stays a file,
    ``a.b`` stops being one); anything with a ``/`` is still a path.
    """
    stripped = text.strip()
    if "/" in stripped:
        return bool(_PATHISH_RE.match(stripped))
    if not _FILEISH_RE.match(stripped):
        return False
    ext = stripped.rsplit(".", 1)[-1]
    return len(ext) >= 2 and ext.isalpha()


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


def _match(rows: List[List[str]], title: Optional[str]) -> Dict[str, Any]:
    return {"rows": rows, "header": None, "unit": None, "title": title}


def _run(lines: List[str], hit_one) -> List[Dict[str, Any]]:
    """Group consecutive lines that ``hit_one`` accepts into one match each."""
    found: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        rows: List[List[str]] = []
        start = i
        while i < len(lines):
            row = hit_one(lines[i])
            if row is None:
                break
            rows.append(row)
            i += 1
        if rows:
            found.append(_match(rows, _title_before(lines, start)))
        else:
            i += 1
    return found


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
            found.append(_match(rows, _title_before(lines, start)))
        else:
            i += 1
    return found


def match_checklist(lines: List[str]) -> List[Dict[str, Any]]:
    """A task-list run: ``- [x] done`` / ``- [ ] todo`` / ``- [/] doing`` / ``- [!] blocked``."""

    def hit_one(line: str):
        hit = _CHECKLIST_RE.match(line)
        if not hit:
            return None
        return [hit.group("label").strip(), _CHECKLIST_STATES.get(hit.group("state"), "todo")]

    return _run(lines, hit_one)


def match_changes(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``path +12 -3`` run, one line per file."""

    def hit_one(line: str):
        hit = _CHANGE_RE.match(line)
        if not hit:
            return None
        return [hit.group("path"), "+" + hit.group("adds"), "-" + hit.group("dels")]

    return _run(lines, hit_one)


def match_outline(lines: List[str]) -> List[Dict[str, Any]]:
    """A dotted-number run (``1. Title`` / ``1.1 Sub``); at least one prefix must be dotted."""
    found: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        rows: List[List[str]] = []
        dotted = False
        start = i
        while i < len(lines):
            hit = _OUTLINE_RE.match(lines[i])
            if not hit:
                break
            dotted = dotted or ("." in hit.group("num"))
            rows.append([hit.group("num"), hit.group("text").strip()])
            i += 1
        if rows:
            if dotted and len(rows) >= 2:
                found.append(_match(rows, _title_before(lines, start)))
        else:
            i += 1
    return found


def match_facts(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``Label: value`` run whose values are text, not numbers."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        value = hit.group("value").strip()
        if not label or not value or label.startswith("["):
            return None
        if _is_number(value) or _looks_like_path(label):
            return None
        # a wireframe block run or an OHLC cell is a widget of its own — facts stands down
        if _WIREFRAME_VALUE_RE.fullmatch(value) or _CANDLE_VALUE_RE.fullmatch(value):
            return None
        return [label, value]

    return _run(lines, hit_one)


def match_files(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``path: meta`` run whose labels look like file paths."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        value = hit.group("value").strip()
        if not label or not value or not _looks_like_path(label):
            return None
        return [label, value]

    return _run(lines, hit_one)


def match_parts(lines: List[str]) -> List[Dict[str, Any]]:
    """A markdown table with a ref/part column and a qty column — a bill of materials."""
    found = []
    for table in _tables(lines):
        header = [cell.strip().lower() for cell in table["header"]]
        if not table["rows"]:
            continue
        has_ref = any(cell in _PARTS_REF for cell in header)
        has_qty = any(cell in _PARTS_QTY for cell in header)
        if has_ref and has_qty:
            found.append(
                {
                    "rows": table["rows"],
                    "header": table["header"],
                    "unit": None,
                    "title": table["title"],
                }
            )
    return found


def match_settings(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``Label: on`` / ``Label: off`` run, the state normalised to ``on`` / ``off``."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        value = hit.group("value").strip().lower().rstrip(".")
        if not label:
            return None
        if value in _SETTINGS_TRUE:
            return [label, "on"]
        if value in _SETTINGS_FALSE:
            return [label, "off"]
        return None

    return _run(lines, hit_one)


def match_ranges(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``Label: lo..hi`` run; the endpoints are normalised to ``lo..hi``."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        rng = _RANGE_RE.match(hit.group("value").strip())
        if not rng:
            return None
        return [hit.group("label").strip(), "%s..%s" % (rng.group("lo"), rng.group("hi"))]

    return _run(lines, hit_one)


def match_metrics(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``Label: value (delta)`` run."""

    def hit_one(line: str):
        hit = _METRIC_RE.match(line)
        if not hit:
            return None
        return [hit.group("label").strip(), hit.group("value").strip(), hit.group("delta").strip()]

    return _run(lines, hit_one)


def _split_when(line: str) -> Optional[List[str]]:
    text = _LIST_ITEM_RE.sub("", line).strip()
    hit = _DATE_RE.match(text)
    if not hit:
        return None
    rest = text[hit.end():].lstrip()
    rest = re.sub(r"^[—–:\-][ \t]*", "", rest)
    if not rest:
        return None
    parts = re.split(r"[ \t]*[—–][ \t]*|[ \t]+-[ \t]+", rest, maxsplit=1)
    if len(parts) == 2 and _CANDLE_VALUE_RE.fullmatch(parts[1].strip()):
        return None  # an OHLC row, not a dated event — candlestick's, not timeline's
    return [hit.group("when")] + [part.strip() for part in parts]


def match_timeline(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``when — label[ — detail]`` run; ``when`` is a date or a clock time."""
    return _run(lines, _split_when)


def match_array(lines: List[str]) -> List[Dict[str, Any]]:
    """A run of ``a | b | c`` rows that is not a markdown table (no delimiter row)."""
    inside_table = set()
    for table in _tables(lines):
        inside_table.add(table["index"])
        inside_table.add(table["index"] + 1)
        j = table["index"] + 2
        while j < len(lines) and "|" in lines[j] and lines[j].strip():
            inside_table.add(j)
            j += 1

    def hit_one_at(index: int):
        if index in inside_table or "|" not in lines[index]:
            return None
        cells = _cells(lines[index])
        if len(cells) < 2 or not all(cells):
            return None
        return cells

    found: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        rows: List[List[str]] = []
        start = i
        while i < len(lines):
            row = hit_one_at(i)
            if row is None:
                break
            rows.append(row)
            i += 1
        if rows:
            found.append(_match(rows, _title_before(lines, start)))
        else:
            i += 1
    return found


def match_heatmap(lines: List[str]) -> List[Dict[str, Any]]:
    """A long numeric run (>= 6 rows) — the same shape as ``bars``, drawn as a ramp."""
    return [run for run in match_number_run(lines) if len(run["rows"]) >= 6]


def match_wireframe(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``Label: block:count, block:count`` run — a UI mock, one row per band."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        value = hit.group("value").strip()
        if not label or not value or not _WIREFRAME_VALUE_RE.fullmatch(value):
            return None
        blocks = []
        for part in value.split(","):
            name, _, count = part.strip().partition(":")
            if name not in _WIREFRAME_BLOCKS:
                return None
            blocks.append("%s:%d" % (name, int(count)))
        return [label, ",".join(blocks)]

    return _run(lines, hit_one)


def match_candlestick(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``when: open:high:low:close`` run — one candle per line."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        when = hit.group("label").strip()
        value = hit.group("value").strip()
        if not when or not _CANDLE_VALUE_RE.fullmatch(value):
            return None
        return [when, value]

    return _run(lines, hit_one)


def match_flow(lines: List[str]) -> List[Dict[str, Any]]:
    """An ``A -> B -> C`` arrow chain — the one shape that genuinely wants a Mermaid diagram.

    The rows carry the normalised chain so ``min`` counts it, and ``body`` carries the flowchart's own
    lines, which is what routes the spec to a fence instead of a board.
    """
    found = _run(lines, lambda line: _flow_hit(line))
    for run in found:
        run["body"] = [row[0] for row in run["rows"]]
    return found


def _flow_hit(line: str):
    hit = _FLOW_RE.match(line)
    if not hit:
        return None
    chain = hit.group("chain").replace("→", "-->")
    chain = re.sub(r"[ \t]*(?:-->|->|=>)[ \t]*", " --> ", chain)
    return [chain.strip()]


MATCHERS = {
    "number-run": match_number_run,
    "table": match_table,
    "steps-list": match_steps_list,
    "checklist": match_checklist,
    "changes": match_changes,
    "outline": match_outline,
    "facts": match_facts,
    "files": match_files,
    "parts": match_parts,
    "settings": match_settings,
    "timeline": match_timeline,
    "ranges": match_ranges,
    "metrics": match_metrics,
    "array": match_array,
    "heatmap": match_heatmap,
    "wireframe": match_wireframe,
    "candlestick": match_candlestick,
    "flow-arrows": match_flow,
}


# ------------------------------------------------------------------------------------------------
# the structure layer


def _starts_block(lines: List[str], index: int) -> bool:
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return False
    if _LIST_ITEM_RE.match(lines[index]):
        return True
    return (
        "|" in lines[index]
        and index + 1 < len(lines)
        and _is_delimiter(lines[index + 1])
    )


def match_section_bold(lines: List[str]) -> List[Dict[str, Any]]:
    """An all-bold line that is not yet a heading — the answer already treats it as one."""
    found = []
    for index, line in enumerate(lines):
        if _HEADING_RE.match(line):
            continue
        hit = _BOLD_RE.match(line)
        if not hit:
            continue
        title = hit.group(1).strip()
        if title:
            found.append({"at": index, "title": title, "rows": [[title]],
                          "header": None, "unit": None})
    return found


def match_section_heading(lines: List[str]) -> List[Dict[str, Any]]:
    """A short heading-like line directly above a list or a table."""
    found = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        if (
            _HEADING_RE.match(line)
            or _BOLD_RE.match(line)
            or _LIST_ITEM_RE.match(line)
            or "|" in line
            or _is_delimiter(line)
            or _NUMBER_RUN_RE.match(line)
        ):
            continue
        if stripped[-1] in ".!?;":
            continue
        if not _starts_block(lines, index + 1):
            continue
        found.append({"at": index, "title": stripped, "rows": [[stripped]],
                      "header": None, "unit": None})
    return found


STRUCTURE_MATCHERS = {
    "section-bold": match_section_bold,
    "section-heading": match_section_heading,
}

# An all-bold line *is* one of the answer's own divisions (level 1); a bare caption directly above a
# list or table is a division *within* one (level 2). The renderer ranks by type size, not colour.
_SECTION_LEVELS = {"section-bold": 1, "section-heading": 2}


def structure(text: str, rules, groups=None):
    """Return ``(structured_text, section_specs)``.

    Every anchor an active ``section`` rule matches — an all-bold line, or a short heading-like line
    directly above a list or table — gets a ``### `` marker inserted in front of it, and a ``section``
    spec whose title is the anchor's own words.  Each spec also carries ``at`` (the anchor's line index,
    so the transform can pair it with the widgets that follow) and ``level`` (1 for a division of the
    answer, 2 for a division within one).  The answer's lines are never removed, reworded or
    reordered: the words survive verbatim, the marker is inserted ahead of them.  Already-structured
    text (a ``### `` heading) matches nothing, so a second pass changes nothing.
    """
    active = _active_groups(groups)
    lines = _unfenced(text)
    anchors: List[Any] = []
    for rule in rules or []:
        if not isinstance(rule, dict) or str(rule.get("kind") or "") != "section":
            continue
        group = str(rule.get("group") or "")
        if active is not None and group not in active:
            continue
        when = str(rule.get("when") or "")
        matcher = STRUCTURE_MATCHERS.get(when)
        if matcher is None:
            continue
        low = _as_int(rule.get("min"), 1)
        hits = matcher(lines)
        if len(hits) < low:
            continue
        level = _SECTION_LEVELS.get(when, 1)
        anchors.extend((hit["at"], hit["title"], level) for hit in hits)

    if not anchors:
        return text, []

    source = str(text).splitlines()
    seen = set()
    specs: List[Dict[str, Any]] = []
    for index, title, level in sorted(anchors):
        if index in seen or not (0 <= index < len(source)):
            continue
        seen.add(index)
        line = source[index]
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        source[index] = indent + "### " + stripped
        specs.append({"kind": "section", "title": title, "rows": [], "at": index, "level": level})
    return "\n".join(source), specs


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
    if match.get("body"):
        spec["body"] = list(match["body"])
    if match.get("level"):
        spec["level"] = match["level"]
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
                specs = _stand_down_bars(specs)
                return specs

    return _stand_down_bars(specs)


def _rows_key(spec: Dict[str, Any]):
    return tuple(tuple(row) for row in spec.get("rows") or ())


def _stand_down_bars(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`heatmap` and `bars` match the same numeric run (>= 6 rows).

    Where a run became a heatmap, the ``bars`` widget for those exact rows stands down, so one dataset
    is emitted once.  With the heatmap group off there is no heatmap spec and ``bars`` keeps them.
    """
    heatmap_rows = {_rows_key(spec) for spec in specs if spec.get("kind") == "heatmap"}
    if not heatmap_rows:
        return specs
    return [spec for spec in specs if not (spec.get("kind") == "bars" and _rows_key(spec) in heatmap_rows)]
