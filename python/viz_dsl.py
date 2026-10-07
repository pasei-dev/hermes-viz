"""The ``::viz{...}`` encoder and the Mermaid fence emitter.

The app's parser (``lib/transcript-directives.ts``) takes one paragraph, one line, and no braces
inside the attrs — so a value may not carry ``;``, ``|``, ``=``, ``~``, a quote, a brace, a backslash
or a newline, and the whole directive has to stay inside the 1200-char cap.  A ``board`` packs several
widget specs into one paragraph, its entries joined by ``~``.
"""

import re
from typing import Any, Dict, List, Optional

__all__ = [
    "MAX_DIRECTIVE_CHARS",
    "MERMAID_HEADERS",
    "to_directive",
    "to_board_directive",
    "mermaid_fence",
    "clean_value",
]

#: SPEC.md: a directive is one paragraph and must not exceed this.
MAX_DIRECTIVE_CHARS = 1200

#: A chart cell is a label, not a paragraph.
MAX_CELL_CHARS = 100

_KIND_RE = re.compile(r"[^a-z0-9-]+")
_STRIP = ('"', "{", "}", "\\", ";", "|", "=", "~")
_SPACE_RE = re.compile(r"\s+")

#: A grid-shaped kind separates its cells with `|`; a value kind separates label from value with `=`.
_CELL_SEPARATOR = "|"

#: Kinds whose cells form a grid rather than label=value pairs: the table, the BOM and the raw array.
_PIPE_KINDS = frozenset({"table", "parts", "array", "recipe"})


def _separator(kind: str) -> str:
    return _CELL_SEPARATOR if kind in _PIPE_KINDS else "="


def clean_value(value: Any) -> str:
    """A value the directive parser can carry: no separators, no braces, one line, bounded."""
    text = str(value)
    for char in _STRIP:
        text = text.replace(char, " ")
    text = _SPACE_RE.sub(" ", text).strip()
    if len(text) > MAX_CELL_CHARS:
        text = text[: MAX_CELL_CHARS - 3].rstrip() + "..."
    return text


def clean_kind(kind: Any) -> str:
    """The ``k`` attr: ``[a-z][a-z0-9-]*``."""
    text = _KIND_RE.sub("-", str(kind or "").strip().lower()).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text if re.match(r"^[a-z][a-z0-9-]*$", text) else ""


def _row(separator: str, cells: List[Any]) -> str:
    return separator.join(clean_value(cell) for cell in cells)


def _render(
    kind: str,
    rows: List[str],
    title: Optional[str],
    unit: Optional[str],
    palette: Optional[str] = None,
    level: Optional[int] = None,
) -> str:
    attrs = ['k="%s"' % kind, 'd="%s"' % ";".join(rows)]
    if palette:
        attrs.append('p="%s"' % palette)
    if title:
        attrs.append('t="%s"' % clean_value(title))
    if unit:
        attrs.append('u="%s"' % clean_value(unit))
    if level and level != 1:
        attrs.append('l="%d"' % level)
    return "::viz{" + " ".join(attrs) + "}"


def to_directive(spec: Dict[str, Any]) -> Optional[str]:
    """A spec as one ``::viz{...}`` line, always within the cap, or None if it cannot be built.

    SPEC.md's encoding: ``d`` holds every row, cells split on ``|``, value rows split on ``=``, and a
    row beginning ``h=`` is the header.  Rows are dropped from the tail until the paragraph fits — a
    shorter widget beats a clipped directive.  ``spec`` carries ``kind``, ``rows`` (a list of cell
    lists) and optional ``header``, ``title``, ``unit`` and ``palette``.
    """
    kind = clean_kind(spec.get("kind"))
    if not kind:
        return None

    separator = _separator(kind)
    title = spec.get("title") or None
    unit = spec.get("unit") or None
    palette = clean_kind(spec.get("palette")) if spec.get("palette") else None

    rows: List[str] = []
    if spec.get("header"):
        rows.append("h=" + _row("|", list(spec["header"])))
    rows.extend(_row(separator, list(row)) for row in spec.get("rows") or [])

    level = spec.get("level")
    try:
        level = int(level) if level is not None else None
    except (TypeError, ValueError):
        level = None

    while True:
        line = _render(kind, rows, title, unit, palette, level)
        if len(line) <= MAX_DIRECTIVE_CHARS:
            return line
        if rows:
            rows.pop()
            continue
        if title:
            title = None
            continue
        if unit:
            unit = None
            continue
        return None


def _widget_payload(spec: Dict[str, Any]) -> Optional[str]:
    """One board entry: ``kind:payload``, the payload using ``;``/``|``/``=`` exactly as ``d`` does.

    A ``section`` carries no rows: its heading is the payload, so the board can draw the header band.
    """
    kind = clean_kind(spec.get("kind"))
    if not kind:
        return None

    if kind == "section":
        heading = clean_value(spec.get("title") or "")
        if not heading:
            return None
        # `l=2` is a division within one; level 1 is the default and is not carried.
        raw = spec.get("level")
        try:
            level = int(raw) if raw is not None else 1
        except (TypeError, ValueError):
            level = 1
        return "section:" + heading + (";l=%d" % level if level != 1 else "")

    separator = _separator(kind)
    rows: List[str] = []
    if spec.get("header"):
        rows.append("h=" + _row("|", list(spec["header"])))
    rows.extend(_row(separator, list(row)) for row in spec.get("rows") or [])
    return kind + ":" + ";".join(rows)


def _trim_payload(payload: str) -> Optional[str]:
    """Drop the last row of a board entry; None once it has no rows left.

    A ``section`` entry's payload is its heading (plus, for level 2, the ``l=`` row).  Trimming it would
    either lose the heading or silently downgrade the level, so it is dropped whole instead.
    """
    kind, sep, body = payload.partition(":")
    if kind == "section":
        return None
    rows = body.split(";")
    if len(rows) > 1:
        return kind + sep + ";".join(rows[:-1])
    return None


def to_board_directive(specs: List[Dict[str, Any]]) -> Optional[str]:
    """Every spec as one ``::viz{k="board" d="…"}`` paragraph, entries joined with ``~``.

    The board encoding carries the kind and its rows only — a per-widget ``title``, ``unit`` and
    ``palette`` have no slot and are not carried.  Entries and rows drop from the tail until the
    paragraph fits the cap, so one board is never a clipped directive.
    """
    payloads: List[str] = []
    for spec in specs or []:
        if not isinstance(spec, dict):
            continue
        payload = _widget_payload(spec)
        if payload:
            payloads.append(payload)
    if not payloads:
        return None

    while True:
        line = '::viz{k="board" d="%s"}' % "~".join(payloads)
        if len(line) <= MAX_DIRECTIVE_CHARS:
            return line
        if payloads:
            trimmed = _trim_payload(payloads[-1])
            if trimmed:
                payloads[-1] = trimmed
            else:
                payloads.pop()
            continue
        return None


# ------------------------------------------------------------------------------------------------
# Mermaid

#: AGENTS.md: an `<img>`-hosted SVG cannot resolve `var()`, so the palette is literal by necessity.
#: Values follow the app's own surfaces (SPEC.md names its dark defaults `#1f2020` fill / `#ccc` stroke;
#: `apps/desktop/src/styles.css` gives light `#17171a` / `#f8faff` and dark `#161618` / `#0d0d0e`).
_PALETTES = {
    "dark": {
        "background": "transparent",
        "primaryColor": "#1f2020",
        "primaryTextColor": "#e6e6e6",
        "primaryBorderColor": "#3d3d40",
        "lineColor": "#8a8a8f",
        "secondaryColor": "#161618",
        "tertiaryColor": "#0d0d0e",
    },
    "light": {
        "background": "transparent",
        "primaryColor": "#f6f7f9",
        "primaryTextColor": "#17171a",
        "primaryBorderColor": "#d5d8de",
        "lineColor": "#8b8f96",
        "secondaryColor": "#eef1f6",
        "tertiaryColor": "#f8faff",
    },
}

#: The diagram keyword each Mermaid kind opens with.
MERMAID_HEADERS = {
    "flowchart": "flowchart TD",
    "sequence": "sequenceDiagram",
    "state": "stateDiagram-v2",
    "class": "classDiagram",
    "er": "erDiagram",
    "gantt": "gantt",
    "pie": "pie",
    "journey": "journey",
    "gitgraph": "gitgraph",
    "timeline": "timeline",
    "quadrant": "quadrantChart",
    "sankey": "sankey-beta",
    "treemap": "treemap-beta",
    "radar": "radar-beta",
    "xychart": "xychart-beta",
    "mindmap": "mindmap",
    "block": "block-beta",
}


def _init_header(palette: str) -> Optional[str]:
    values = _PALETTES.get(str(palette or "").strip().lower())
    if not values:
        return None  # "mermaid" (and anything unknown) leaves Mermaid's own adaptation alone
    body = ",".join("'%s':'%s'" % (key, values[key]) for key in sorted(values))
    # Mermaid's directive needs the doubled percent signs, so this is concatenation, not %-formatting.
    return "%%{init:{'theme':'base','themeVariables':{" + body + "}}}%%"


def _body_lines(spec: Dict[str, Any]) -> List[str]:
    body = spec.get("body")
    if body is None:
        body = spec.get("code")
    if body is None:
        return []
    if isinstance(body, str):
        return body.splitlines()
    return [str(line) for line in body]


def mermaid_fence(kind: Any, spec: Dict[str, Any], palette: str = "mermaid") -> str:
    """A ```mermaid fence for ``kind``, with the baked palette header unless ``palette`` is `mermaid`.

    The diagram keyword comes from ``kind`` (``MERMAID_HEADERS``); ``spec["body"]`` holds the diagram
    body, as a string or a list of lines.
    """
    lines = ["```mermaid"]
    header = _init_header(palette)
    if header:
        lines.append(header)
    keyword = MERMAID_HEADERS.get(clean_kind(kind))
    if keyword:
        lines.append(keyword)
    lines.extend(_body_lines(spec))
    lines.append("```")
    return "\n".join(lines)
