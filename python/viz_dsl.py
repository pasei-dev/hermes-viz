"""The ``::viz{...}`` encoder, the Mermaid fence emitter, and the demotion a surface that cannot
draw is owed.

The app's parser (``lib/transcript-directives.ts``) takes one paragraph, one line, and no braces
inside the attrs — so a value may not carry ``;``, ``|``, ``=``, ``~``, a quote, a brace, a backslash
or a newline, and the whole directive has to stay inside the 1200-char cap.  A ``board`` packs several
widget specs into one paragraph, its entries joined by ``~``.

Round 12: a value may be a **computed cell** (`python/viz_expr.py`), and a directive that reaches a
surface which cannot draw one is **demoted to the markdown it would have drawn** rather than removed.
"""

import re
from typing import Any

try:  # loaded as part of the plugin package
    from .viz_expr import resolve_payload, unresolved_calls
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from viz_expr import resolve_payload, unresolved_calls

__all__ = [
    "MAX_DIRECTIVE_CHARS",
    "MERMAID_HEADERS",
    "KNOWN_KINDS",
    "to_directive",
    "to_board_directive",
    "board_entry",
    "mermaid_fence",
    "clean_value",
    "is_drawable",
    "demote_directives",
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

#: Kinds whose cells form a grid rather than label=value pairs: the table, the BOM, the raw array, the
#: paradigm grid and the generic `grid` shape (a header row plus equal-width cells).
_PIPE_KINDS = frozenset({"table", "parts", "array", "recipe", "forms", "grid"})


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


def _row(separator: str, cells: list[Any]) -> str:
    return separator.join(clean_value(cell) for cell in cells)


def _render(
    kind: str,
    rows: list[str],
    title: (str) | None,
    unit: (str) | None,
    palette: (str) | None = None,
    level: (int) | None = None,
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


def to_directive(spec: dict[str, Any]) -> (str) | None:
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

    rows: list[str] = []
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


def _widget_payload(spec: dict[str, Any]) -> (str) | None:
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
    rows: list[str] = []
    if spec.get("header"):
        rows.append("h=" + _row("|", list(spec["header"])))
    rows.extend(_row(separator, list(row)) for row in spec.get("rows") or [])
    return kind + ":" + ";".join(rows)


def board_entry(spec: dict[str, Any]) -> (str) | None:
    """The ``kind:payload`` text one board entry carries — what a board actually draws for this spec.

    Exposed so the transform can ask whether a widget carries everything its source said before it
    deletes the source lines: the answer must be the *emitted* text, not the raw cells, because the
    board drops a per-widget title and unit and the emitter strips reserved characters.
    """
    return _widget_payload(spec)


def _trim_payload(payload: str) -> (str) | None:
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


def to_board_directive(specs: list[dict[str, Any]]) -> (str) | None:
    """Every spec as one ``::viz{k="board" d="…"}`` paragraph, entries joined with ``~``.

    The board encoding carries the kind and its rows only — a per-widget ``title``, ``unit`` and
    ``palette`` have no slot and are not carried.  Entries and rows drop from the tail until the
    paragraph fits the cap, so one board is never a clipped directive.
    """
    payloads: list[str] = []
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


def _init_header(palette: str) -> (str) | None:
    values = _PALETTES.get(str(palette or "").strip().lower())
    if not values:
        return None  # "mermaid" (and anything unknown) leaves Mermaid's own adaptation alone
    body = ",".join("'%s':'%s'" % (key, values[key]) for key in sorted(values))
    # Mermaid's directive needs the doubled percent signs, so this is concatenation, not %-formatting.
    return "%%{init:{'theme':'base','themeVariables':{" + body + "}}}%%"


def _body_lines(spec: dict[str, Any]) -> list[str]:
    body = spec.get("body")
    if body is None:
        body = spec.get("code")
    if body is None:
        return []
    if isinstance(body, str):
        return body.splitlines()
    return [str(line) for line in body]


def mermaid_fence(kind: Any, spec: dict[str, Any], palette: str = "mermaid") -> str:
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


# ------------------------------------------------------------------------------------------------
# A surface that cannot draw gets the data, not the grammar.
#
# A directive a surface cannot render used to be *taken out*, which took its data with it.  It is
# now **demoted**: the payload becomes the markdown it would have drawn — a table when the payload
# carries a header row, a list otherwise — its computed cells are resolved so the numbers are the
# numbers, and only a directive with nothing left to carry leaves no line behind.  The reader of a
# surface that cannot draw therefore keeps every value the desktop reader is shown.

#: The kinds a directive may name: exactly what the drawing core draws (`KINDS` in
#: `desktop/render/core.mjs`, plus `board`, which is dispatched before that list is consulted).
#: `tests/test_demote.py` pins this to the core's own list, so a kind the core cannot draw is a
#: kind this reader demotes.
KNOWN_KINDS = frozenset({
    "kpi", "bars", "line", "donut", "steps", "table", "progress", "sparkline", "section",
    "checklist", "changes", "outline", "facts", "files", "parts", "settings", "timeline",
    "ranges", "metrics", "array", "heatmap", "wireframe", "candlestick", "words", "recipe",
    "route", "nutrition", "matches", "bracket", "gloss", "forms", "funnel", "scatter",
    "waterfall", "records", "pairs", "series", "stages", "grid", "groups", "events", "board",
})

#: A line that opens or closes a fenced block, so a reader being *shown* the grammar keeps it.
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

#: `::viz` starting a word — the app's own rule, so `std::vector` is never a directive.
_MARK_RE = re.compile(r"(?:^|\s)::viz")

#: `key="value"` — the app's attr grammar.  Read leniently: what is left over is what makes a
#: directive one the app itself refuses, which is the first thing `is_drawable` looks at.
_ATTR_RE = re.compile(r'([A-Za-z]+)\s*=\s*"([^"]*)"')

#: A cell that is only a number — the cell a unit suffix belongs on, and the only one.
_PLAIN_NUMBER_RE = re.compile(r"^[-+]?(?:\d+\.?\d*|\.\d+)$")


def _mentions(line: str) -> list:
    """``(start, end, attrs_text, whole)`` for each `::viz` on one line.

    The app takes a brace-free group bounded by its cap.  This reader is deliberately looser,
    because the directives it has to rescue are exactly the ones the app refuses: a group runs to
    the last `}` before the next `::viz` on the line, or to the end of the line when the braces do
    not close at all.
    """
    marks = list(_MARK_RE.finditer(line))
    spans = []
    for index, mark in enumerate(marks):
        limit = marks[index + 1].start() if index + 1 < len(marks) else len(line)
        lead = 1 if line[mark.start()] in " \t" else 0
        start, at = mark.start() + lead, mark.end()
        gap = at
        while gap < limit and line[gap] in " \t":
            gap += 1
        if gap < limit and line[gap] == "{":
            close = line.rfind("}", gap, limit)
            if close >= gap:
                spans.append((start, close + 1, line[gap + 1 : close], line[start : close + 1]))
                continue
            spans.append((start, limit, line[gap + 1 : limit], line[start:limit]))
            continue
        # A bare name is a directive the app recognises (a card with no data) — but only as a word: a
        # name that runs straight into more characters (`::viz-less`) is text, exactly as `std::vector`
        # is.
        if at >= len(line) or line[at] in " \t":
            spans.append((start, at, "", line[start:at]))
    return spans


def _attrs(text: str) -> tuple:
    """``(attrs, leftover)`` — the `key="value"` pairs, and whatever was not one of them."""
    return (
        {match.group(1).lower(): match.group(2) for match in _ATTR_RE.finditer(text)},
        _ATTR_RE.sub(" ", text).strip(),
    )


def _entry_drawable(entry: str) -> bool:
    """One board entry, ``kind:payload``, as `is_drawable` reads a whole directive.

    The board's own rule decides this, and it is round 2's: **one bad entry degrades to prose for that
    cell alone while the rest of the board still renders** (SPEC.md).  So an entry is not a reason to
    demote a board the app would draw — not an unknown kind, not a missing kind.  Two things still are:
    an entry with no payload at all (the core's drawing for that cell is the raw ``kind:`` text), and a
    computed cell the entry's own rows cannot compute (the reader would read a formula as a value).
    """
    kind, sep, body = str(entry).partition(":")
    if not sep:
        return True
    if not body.strip():
        return False
    return not unresolved_calls(body)


def is_drawable(attrs_text: str) -> bool:
    """True when the app's parser and the drawing core both take this directive as written.

    The fence is deliberately narrow — only what can be *proved* undrawable counts, so a directive
    this cannot see through is left exactly as the model wrote it.  Five things are provable: a
    group past the app's cap, a brace inside the attrs, attrs that are not `key="value"`, a kind
    the core does not draw, and a computed cell the payload's own rows cannot compute.
    """
    text = str(attrs_text or "")
    if len(text) > MAX_DIRECTIVE_CHARS or "{" in text or "}" in text:
        return False
    attrs, leftover = _attrs(text)
    if leftover:
        return False
    kind = str(attrs.get("k") or "").strip().lower()
    if kind not in KNOWN_KINDS or not (attrs.get("d") or attrs.get("t")):
        return False
    if kind == "board":
        entries = [entry for entry in str(attrs.get("d") or "").split("~") if entry.strip()]
        return bool(entries) and all(_entry_drawable(entry) for entry in entries)
    return not unresolved_calls(attrs.get("d") or "")


def _body_rows(payload: str) -> list:
    """A payload's rows, with its computed cells already resolved."""
    resolved, _unresolved = resolve_payload(payload)
    return [row for row in resolved.split(";") if row.strip()]


def _split_cell(cell: str) -> tuple:
    """``label=value=extra``, split the way the core's own `parseCell` splits it."""
    if "=" not in cell:
        return cell.strip(), "", ""
    parts = cell.split("=")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip(), ""
    return parts[0].strip(), "".join(parts[1:-1]).strip(), parts[-1].strip()


def _unit(text: str, unit: str) -> str:
    """The directive's unit on a cell that is only a number — what `u=` named on the drawing."""
    text = str(text).strip()
    return text + unit if unit and _PLAIN_NUMBER_RE.match(text) else text


def _item(row: str, unit: str) -> str:
    """One row as one line: a label is the reader's key term, the values follow it."""
    cells = [cell.strip() for cell in str(row).split("|")]
    if len(cells) > 1:
        parts = ["**%s**" % _unit(cells[0], unit)] if cells[0] else []
        parts += [_unit(cell, unit) for cell in cells[1:]]
        return " — ".join(part for part in parts if part)

    cell = cells[0]
    if "=" not in cell:
        return _unit(cell, unit)  # a bare item is not a label — there is nothing to bold

    label, value, extra = _split_cell(cell)
    parts = ["**%s**" % label] if label else []
    parts += [_unit(part, unit) for part in (value, extra) if part]
    return " — ".join(parts)


def _inline(attrs: dict) -> str:
    """A directive written mid-sentence: no title and no columns fit inside a sentence."""
    unit = str(attrs.get("u") or "").strip()
    kind = str(attrs.get("k") or "").strip().lower()
    if kind == "board":
        return "; ".join(
            _inline({"k": kind_of, "d": body}) for kind_of, body in _entries(str(attrs.get("d") or ""))
        )
    rows = [row for row in _body_rows(str(attrs.get("d") or "")) if row[:2].lower() != "h="]
    return "; ".join(_item(row, unit) for row in rows)


def _list(rows: list, unit: str) -> str:
    """A run of rows, one line each — a bare numeric run is one line, not a column of bullets."""
    if rows and all(len(str(row).split("|")) == 1 and _PLAIN_NUMBER_RE.match(str(row).strip()) for row in rows):
        return ", ".join(_unit(row, unit) for row in rows)
    return "\n".join("- " + _item(row, unit) for row in rows)


def _table(header: str, rows: list, unit: str) -> str:
    """A markdown table: the payload carried a header row, so it has columns to fill."""
    columns = max(len(str(text).split("|")) for text in [header] + list(rows))

    def line(cells: list) -> str:
        cells = [str(cell).strip() for cell in cells]
        cells += [""] * (columns - len(cells))
        return "| " + " | ".join(cells) + " |"

    out = [line(str(header).split("|")), "|" + " --- |" * columns]
    out += [line([_unit(cell, unit) for cell in str(row).split("|")]) for row in rows]
    return "\n".join(out)


def _block(attrs: dict) -> str:
    """The markdown a directive becomes: its title, then its data in the shape the payload has."""
    kind = str(attrs.get("k") or "").strip().lower()
    payload = str(attrs.get("d") or "")
    unit = str(attrs.get("u") or "").strip()
    title = str(attrs.get("t") or "").strip()

    if kind == "board":
        # A board's own title and unit are the WIDGET's, so they ride the whole block: the entries
        # carry neither (SPEC.md's board encoding), and dropping them would drop what the caption
        # said and what every number was in.  The core threads both into each entry the same way.
        blocks = [_block({"k": name, "d": body, "u": unit}) for name, body in _entries(payload)]
        head = "**%s**\n" % title if title else ""
        return head + "\n\n".join(block for block in blocks if block)

    if kind == "section":
        rows = [_item(row, unit) for row in _body_rows(payload)]
        heading = title or (rows.pop(0) if rows else "")
        lead = "; ".join(item for item in rows if item != heading)
        return "\n".join(part for part in ("**%s**" % heading if heading else "", lead) if part)

    rows = _body_rows(payload)
    head = "**%s**\n" % title if title else ""
    header = next((row for row in rows if row[:2].lower() == "h="), None)
    if header is None:
        return head + _list(rows, unit)
    return head + _table(header[2:], [row for row in rows if row[:2].lower() != "h="], unit)


def _entries(payload: str) -> list:
    """A board payload's ``kind:body`` entries, as ``(kind, body)``."""
    out = []
    for entry in str(payload).split("~"):
        if not entry.strip():
            continue
        kind, sep, body = entry.partition(":")
        out.append((kind.strip() if sep else "", body if sep else entry))
    return out


def _alone(line: str, spans: list) -> bool:
    """True when the line holds nothing but its directives — the app's own rule for one."""
    rest = line
    for start, end, _attrs_text, _whole in reversed(spans):
        rest = rest[:start] + rest[end:]
    return not rest.strip()


def demote_directives(text: str, only_invalid: bool = False) -> str:
    """Every ``::viz`` in *text* replaced by the markdown it would have drawn — or by nothing.

    A directive is grammar to a surface that does not parse one, and the answer's data must not go
    with it: a model *can* write one anywhere — a session resumed from the desktop app carries
    directives in its own history, and a model imitates what it can see — and on the CLI, the TUI, a
    gateway or the dashboard the reader is owed the values, not the encoding.

    ``only_invalid`` is the desktop's own pass: a directive the app and the core would both draw is
    left **exactly as written**, and only one they would refuse — or whose computed cell the payload
    cannot compute — is demoted.  A directive that owned its paragraph takes its line with it, or
    becomes the block; one written mid-sentence leaves the sentence, with its rows inline.  A fenced
    code block is left alone: a reader being *shown* the grammar is not a reader being shown a widget.
    """
    # This runs on every answer bound for a surface that cannot draw, and the overwhelming majority
    # carry no directive at all.  A substring test is O(n) once; the scan below is a split plus a
    # walk per line.  Returning `text` unchanged is byte-for-byte what the no-op case already
    # returns, so a directive-free answer costs one pass and nothing else.
    if "::viz" not in text:
        return text

    lines: list[str] = []
    changed = False
    fenced = False

    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            fenced = not fenced
            lines.append(line)
            continue
        if fenced:
            lines.append(line)
            continue

        spans = _mentions(line)
        if not spans:
            lines.append(line)
            continue

        parts = []  # (the directive as written, attrs) — attrs is None when it is left alone
        replaced = False
        for _start, _end, attrs_text, whole in spans:
            if only_invalid and is_drawable(attrs_text):
                parts.append((whole, None))
                continue
            replaced = True
            parts.append((whole, _attrs(attrs_text)[0]))

        if not replaced:
            lines.append(line)
            continue

        changed = True
        if _alone(line, spans):
            for whole, attrs in parts:
                lines.extend((whole if attrs is None else _block(attrs)).split("\n"))
            continue

        pieces: list[str] = []
        cursor = 0
        for (start, end, _attrs_text, _whole), (whole, attrs) in zip(spans, parts):
            pieces.append(line[cursor:start])
            pieces.append(whole if attrs is None else _inline(attrs))
            cursor = end
        pieces.append(line[cursor:])
        lines.append(_SPACE_RE.sub(" ", "".join(pieces)).strip())

    if not changed:
        return text

    # The demoted block takes the line's place, so the paragraph rhythm that reaches the reader is
    # the one the model wrote — never a double gap where a directive stood.
    out: list[str] = []
    for line in lines:
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)

    return "\n".join(out)
