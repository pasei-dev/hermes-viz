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

# round 5 — the Mermaid shapes the derivation may emit. Each matcher recognises only a shape the text
# already states, so a kind whose body would have to be invented never fires. A single `A -> B`
# transition (the state diagram's unit) is distinct from the flow matcher's chain by construction:
# `_FLOW_RE` needs two arrows, `_STATE_RE` exactly one, and `_SEQUENCE_RE` an arrow *and* a message.
_ARROW_RE = re.compile(r"-->|->|=>|→")
_STATE_RE = re.compile(
    r"^[ \t]*(?P<a>[A-Za-z][A-Za-z0-9_.-]*)[ \t]*(?:-->|->|=>|→)[ \t]*"
    r"(?P<b>[A-Za-z][A-Za-z0-9_.-]*)[ \t]*$"
)
_SEQUENCE_RE = re.compile(
    r"^[ \t]*(?P<a>[A-Za-z][A-Za-z0-9_.-]*)[ \t]*(?:-->|->|=>|→)[ \t]*"
    r"(?P<b>[A-Za-z][A-Za-z0-9_.-]*)[ \t]*[:—–][ \t]*(?P<msg>.+?)[ \t]*$"
)
# a dated span: `2026-01-04 .. 2026-01-09` — the schedule a gantt states
_SPAN_RE = re.compile(
    r"^(?P<start>\d{4}[-/]\d{1,2}[-/]\d{1,2})[ \t]*(?:\.\.|->|→|–|—|to)[ \t]*"
    r"(?P<end>\d{4}[-/]\d{1,2}[-/]\d{1,2})$"
)
# a share of a whole: `42%`
_SHARE_RE = re.compile(r"^(?P<value>\d{1,3}(?:\.\d+)?)[ \t]*%$")

# round 6 — the last three kinds. Each matcher recognises only the shape the text states, so a phrase
# that merely *resembles* one emits nothing.
#
# A bracket is **rounds** of pairings: `R16: Arsenal>Chelsea, Brentford>Leeds`, one round per line.
# A single pairing (`R16: Arsenal>Chelsea`) is not a bracket — the rule's `min` of two rounds is what
# rules it out, and the matcher never sees a lone pairing as a run of one.
_BRACKET_SIDE = r"[^,>=;|~\\]+"
_BRACKET_VALUE_RE = re.compile(
    r"^%(side)s[ \t]*>[ \t]*%(side)s(?:[ \t]*,[ \t]*%(side)s[ \t]*>[ \t]*%(side)s)*$"
    % {"side": _BRACKET_SIDE}
)
# A gloss is one line carrying a source phrase and its gloss (and optionally a note), the `=` cells
# mirroring the payload: `der Hund bellt=the dog barks=PRS.3SG`.  Only a word-aligned pair *is* a gloss;
# a `word: meaning` definition is `facts`/`words`, and an `=`-row whose two sides disagree word-for-word
# is left alone (the renderer's unaligned path is for explicit directives, not for us to invent).
_GLOSS_CELLS = (2, 3)

# A forms grid is a labelled paradigm — a markdown table whose header names grammatical categories
# (`h=person|singular|plural`), not the ref/qty a BOM carries.  Two recognised labels are required, so
# a plain two-column list (`Word | Meaning`) is not a paradigm.
_FORMS_AXES = {
    "person", "case", "tense", "number", "gender", "mood", "voice",
    "declension", "conjugation", "degree", "aspect", "pronoun",
    "article", "noun", "verb", "adjective",
}
_FORMS_CATEGORIES = {
    "singular", "plural", "dual", "first", "second", "third", "1st", "2nd", "3rd",
    "nominative", "accusative", "dative", "genitive", "vocative", "ablative",
    "locative", "instrumental", "present", "past", "future", "preterite", "perfect",
    "imperfect", "pluperfect", "subjunctive", "indicative", "imperative",
    "conditional", "infinitive", "participle", "masculine", "feminine", "neuter",
    "common", "positive", "comparative", "superlative", "informal", "formal",
    "polite", "form", "ending", "suffix",
}
_FORMS_LABELS = _FORMS_AXES | _FORMS_CATEGORIES

# round 7 — the last three, and the hardest to tell apart from ordinary data, so each matcher fires
# only on the one property that *is* the shape; a run that lacks it stays `bars`.
#
# A scatter is a run of `x=y` pairs with a **number on each side** (`1=2.4`), so a point's coordinates
# are stated rather than inferred.  A `label=value` run (`Firmware=42`) has a word on the left and is
# `bars`; a two-column table is `array`.  Requiring `=` (not `:`) keeps the pairing explicit.
_SCATTER_RE = re.compile(
    r"^[ \t]*(?P<x>[-+]?\d[\d,]*(?:\.\d+)?)[ \t]*=[ \t]*"
    r"(?P<y>[-+]?\d[\d,]*(?:\.\d+)?)[ \t]*$"
)
# A waterfall's whole signal is the **sign**: `Start=+120`, `Refunds=-30`.  An unsigned amount is a
# `bars` value, and a signed run that only ever rises (or only falls) is still `bars` — a waterfall
# steps *both* ways around its running total, so the matcher requires at least one of each sign.
_WATERFALL_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?P<label>[^:—–=]{1,60}?)[ \t]*[:—–=][ \t]*"
    r"(?P<sign>[-+])(?P<num>\d[\d,]*(?:\.\d+)?)[ \t]*(?P<unit>%|[A-Za-z][A-Za-z/]{0,9})?[ \t]*$"
)
# A funnel is a run of labelled counts that *narrows* — every stage smaller than the one before — whose
# labels name successive stages of one process (`Visited` → `Signed up` → `Activated` → `Paid`).  A
# plain descending list (`Build: 42` / `Test: 18` / `Package: 7`) narrows too, so the stage vocabulary
# is the line: at least two labels must read as stages.  A label counts as a stage when any of its
# words (lower-cased, split on non-alphanumerics, so `Signed up` reaches `signed`) is one of these.
_FUNNEL_STAGES = frozenset({
    "visit", "visited", "visits", "view", "viewed", "views", "viewing", "landing",
    "signup", "signups", "signed", "register", "registered", "registration", "registers",
    "activate", "activated", "activation", "activations", "engage", "engaged", "engagement",
    "start", "started", "starts", "begin", "began", "begun", "onboard", "onboarded", "onboarding",
    "trial", "trials", "lead", "leads", "prospect", "prospects", "qualified",
    "add", "added", "cart", "checkout", "checkouts", "purchase", "purchased", "buy", "bought",
    "pay", "paid", "payment", "payments", "convert", "converted", "conversion", "conversions",
    "subscribe", "subscribed", "subscription", "subscriptions", "upgrade", "upgraded",
    "download", "downloaded", "downloads", "install", "installed", "installs",
    "open", "opened", "opens", "click", "clicked", "clicks", "invite", "invited", "invites",
    "referral", "referrals", "complete", "completed", "completion", "completions",
    "finish", "finished", "retain", "retained", "retention", "active", "reach", "reached",
    "apply", "applied", "application", "applications", "book", "booked", "booking", "bookings",
    "request", "requested", "requests", "respond", "responded", "response", "responses",
    "attend", "attended", "enroll", "enrolled", "graduate", "graduated", "passed", "survived",
    "dropped", "churned", "cancel", "cancelled", "unsubscribed", "abandoned", "bounce", "bounced",
})


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
        # a message exchange (`A -> B: text`) and a dated span (`2026-01-04 .. 2026-01-09`) are the
        # sequence and gantt shapes — facts stands down so one dataset is emitted once
        if _ARROW_RE.search(label) or _SPAN_RE.match(value):
            return None
        # a round of pairings (`R16: A>B, C>D`) is the bracket shape — facts stands down for the same reason
        if _BRACKET_VALUE_RE.match(value):
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
    if "=" in text:
        return None  # an `=`-separated row is a `records`/`groups` shape, never a dated event
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


def match_state(lines: List[str]) -> List[Dict[str, Any]]:
    """A run of named states with transitions — ``Idle -> Running``, one transition per line.

    A single-arrow line only: the flow matcher's chain needs two arrows, so the two shapes never
    compete for the same line, and a lone transition (one row) is below the rule's ``min`` and never
    fires.  The ``body`` is the ``stateDiagram-v2`` the text itself states.
    """

    def hit_one(line: str):
        hit = _STATE_RE.match(line)
        if not hit:
            return None
        return [hit.group("a"), hit.group("b")]

    found = _run(lines, hit_one)
    for run in found:
        run["body"] = ["%s --> %s" % (row[0], row[1]) for row in run["rows"]]
    return found


def match_sequence(lines: List[str]) -> List[Dict[str, Any]]:
    """An exchange of messages — ``Client -> Server: GET /build``, one message per line."""

    def hit_one(line: str):
        hit = _SEQUENCE_RE.match(line)
        if not hit:
            return None
        return [hit.group("a"), hit.group("b"), hit.group("msg").strip()]

    found = _run(lines, hit_one)
    for run in found:
        run["body"] = ["%s->>%s: %s" % (row[0], row[1], row[2]) for row in run["rows"]]
    return found


def match_gantt(lines: List[str]) -> List[Dict[str, Any]]:
    """A schedule with dates — ``Build: 2026-01-04 .. 2026-01-09``, one dated span per line."""

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        span = _SPAN_RE.match(hit.group("value").strip())
        if not label or not span:
            return None
        return [label, span.group("start"), span.group("end")]

    found = _run(lines, hit_one)
    for run in found:
        run["body"] = ["dateFormat YYYY-MM-DD"] + [
            "%s :%s, %s" % (row[0], row[1], row[2]) for row in run["rows"]
        ]
    return found


def match_pie(lines: List[str]) -> List[Dict[str, Any]]:
    """Shares of one whole — a ``Label: 42%`` run whose values add up to 100 (the whole).

    The sum is the check that makes it one whole rather than a bar chart of percentages: a run that
    does not add up to ~100 is not a pie and is left to ``bars``.
    """

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        share = _SHARE_RE.match(hit.group("value").strip())
        if not label or not share:
            return None
        return [label, share.group("value")]

    found = []
    for run in _run(lines, hit_one):
        total = sum(float(row[1]) for row in run["rows"])
        if not (99.0 <= total <= 101.0):
            continue
        run["body"] = ['"%s" : %s' % (row[0], row[1]) for row in run["rows"]]
        found.append(run)
    return found


def match_dated_events(lines: List[str]) -> List[Dict[str, Any]]:
    """Dated events as a Mermaid ``timeline`` — the same run the ``timeline`` widget reads.

    The widget rule emits these rows as a board; this rule emits the same rows as a fence.  Only one
    of the two groups is on at a time, and the widget's rule comes first, so a dataset is emitted once.
    """
    found = match_timeline(lines)
    for run in found:
        run["body"] = [
            " : ".join(part for part in row if part) for row in run["rows"]
        ]
    return found


def match_bracket(lines: List[str]) -> List[Dict[str, Any]]:
    """Rounds of pairings — ``R16: Arsenal>Chelsea, Brentford>Leeds``, one round per line.

    The value is a comma-separated list of ``winner>loser`` pairings; the label is the round.  A line
    that is not a *list* of pairings (a sentence with a dash, a two-column list, a lone pairing) is not
    a bracket, and the rule's ``min`` of two rounds rules out a single pairing on its own.
    """

    def hit_one(line: str):
        hit = _LABEL_VALUE_RE.match(line)
        if not hit:
            return None
        label = hit.group("label").strip()
        value = hit.group("value").strip()
        if not label or not _BRACKET_VALUE_RE.match(value):
            return None
        pairings = []
        for part in value.split(","):
            winner, _, loser = part.strip().partition(">")
            winner, loser = winner.strip(), loser.strip()
            if not winner or not loser:
                return None
            pairings.append("%s>%s" % (winner, loser))
        return [label, ",".join(pairings)]

    return _run(lines, hit_one)


def _words(text: str) -> List[str]:
    return [word for word in re.split(r"\s+", text.strip()) if word]


def match_gloss(lines: List[str]) -> List[Dict[str, Any]]:
    """A sourced gloss — ``der Hund bellt=the dog barks[=PRS.3SG]``, one gloss per line.

    The ``=`` cells mirror the payload (``source``/``gloss``/``note``).  It is a gloss only when there
    is a source form *and* a gloss *and* the two are word-aligned: the same word count, at least two
    words on the source.  A ``word: meaning`` definition is ``facts``/``words`` (a colon line, one word
    a side), and a pair whose counts disagree is refused rather than squeezed into a false alignment.
    """

    def hit_one(line: str):
        stripped = line.strip()
        if "=" not in stripped:
            return None
        cells = [cell.strip() for cell in stripped.split("=")]
        if len(cells) not in _GLOSS_CELLS or not all(cells):
            return None
        source = _words(cells[0])
        gloss = _words(cells[1])
        if len(source) < 2 or len(source) != len(gloss):
            return None
        return cells

    return _run(lines, hit_one)


def match_forms(lines: List[str]) -> List[Dict[str, Any]]:
    """A labelled paradigm — a markdown table whose header names grammatical categories.

    ``h=person|singular|plural`` / ``1st|habe|haben``.  Two recognised grammatical labels in the header
    are required, so a plain two-column list is not a paradigm; a mostly-numeric body is a chart, not a
    conjugation, and is left to ``bars``.
    """
    found = []
    for table in _tables(lines):
        header = [cell.strip().lower() for cell in table["header"]]
        if len(header) < 2 or not table["rows"]:
            continue
        if sum(1 for cell in header if cell in _FORMS_LABELS) < 2:
            continue
        cells = [cell for row in table["rows"] for cell in row if cell.strip()]
        if not cells:
            continue
        if sum(1 for cell in cells if _is_number(cell)) * 2 >= len(cells):
            continue
        found.append(
            {
                "rows": table["rows"],
                "header": table["header"],
                "unit": None,
                "title": table["title"],
            }
        )
    return found


def _stage_label(label: str) -> bool:
    """A label reads as a funnel stage when any of its words names one."""
    return any(word in _FUNNEL_STAGES for word in re.split(r"[^a-z0-9]+", label.strip().lower()))


def _strictly_decreasing(rows: List[List[str]]) -> bool:
    values = []
    for row in rows:
        try:
            values.append(float(str(row[1]).replace(",", "")))
        except (TypeError, ValueError):
            return False
    return len(values) >= 2 and all(b < a for a, b in zip(values, values[1:]))


def match_funnel(lines: List[str]) -> List[Dict[str, Any]]:
    """A staged funnel — a strictly decreasing labelled-count run whose labels name stages.

    ``bars`` draws any number run, so what makes a funnel is the *narrowing* run whose labels read as
    successive stages of one process (``Visited`` → ``Signed up`` → ``Activated`` → ``Paid``).  A plain
    descending list of unrelated counts (``Build: 42`` / ``Test: 18`` / ``Package: 7``) narrows too but
    names no stage, so it stays ``bars``: at least two stage labels *and* a strict decrease are both
    required, so neither a labelled drop nor a stage word on its own is enough.
    """
    found = []
    for run in match_number_run(lines):
        rows = run["rows"]
        if len(rows) < 3 or not _strictly_decreasing(rows):
            continue
        if sum(1 for row in rows if _stage_label(row[0])) < 2:
            continue
        found.append(run)
    return found


def match_scatter(lines: List[str]) -> List[Dict[str, Any]]:
    """Points on two axes — ``1=2.4``, one ``x=y`` pair per line with a number on *each* side.

    A ``label=value`` run (``Firmware=42``) has a word on the left and is ``bars``; a two-column table
    is ``array``.  Both are refused here because the left side must itself be a number: that is what
    makes a pair a coordinate rather than a labelled count.
    """

    def hit_one(line: str):
        hit = _SCATTER_RE.match(line)
        if not hit:
            return None
        return [hit.group("x"), hit.group("y")]

    return _run(lines, hit_one)


def match_waterfall(lines: List[str]) -> List[Dict[str, Any]]:
    """A running total — signed amounts (``+120``, ``-30``) that step both up and down from a baseline.

    The sign is the whole signal: an unsigned amount is a ``bars`` value, and a signed run that only
    ever rises (or only falls) is still ``bars`` — a waterfall steps *both* ways around its total, so at
    least one positive and one negative are required.
    """

    def hit_one(line: str):
        hit = _WATERFALL_RE.match(line)
        if not hit:
            return None
        return [hit.group("label").strip(" *-"), hit.group("sign") + hit.group("num")]

    found = []
    for run in _run(lines, hit_one):
        if len(run["rows"]) < 3:
            continue
        if {row[1][0] for row in run["rows"]} != {"+", "-"}:
            continue
        found.append(run)
    return found


# ------------------------------------------------------------------------------------------------
# round 8 — the shapes.  A kind per subject does not scale (SPEC.md, "Shapes, not subjects"): these
# four read the *shape* of the data and let the shape's generic renderer draw it, so a new subject
# needs no new rule at all.  Each is the general case of a shape a specific kind may also claim, and
# stands down where that kind takes the rows (see `_stand_down`).

#: A `label=value` record carries two to four cells — a third is a secondary column, a fourth a gloss.
_RECORD_CELLS = frozenset({2, 3, 4})


def _record_row(line: str) -> Optional[List[str]]:
    """A `label=value[=cell…]` row: the `=` shape, its first cell a label rather than a number."""
    text = line.strip()
    if "=" not in text:
        return None
    cells = [cell.strip() for cell in text.split("=")]
    if len(cells) not in _RECORD_CELLS or not all(cells):
        return None
    if _is_number(cells[0]):
        return None  # a number on both sides is a point (`scatter`), not a labelled record
    return cells


def match_records(lines: List[str]) -> List[Dict[str, Any]]:
    """A run of `label=value` rows — the record shape, whatever the subject.

    `nutrition` is a record whose third cell is a target and `words` is a record with four cells; both
    draw through the one shape, so unfamiliar data never has to degrade to text.
    """
    return _run(lines, _record_row)


def match_groups(lines: List[str]) -> List[Dict[str, Any]]:
    """A record run whose cells repeat down a column — rows grouped under a sub-heading.

    A match is `when=teams=group` with the competition repeating (`matches` is `groups`): the shared
    cell is the grouping and each row is one entry in it.
    """
    found = []
    for run in match_records(lines):
        rows = run["rows"]
        if len(rows) < 2:
            continue
        width = min(len(row) for row in rows)
        if any(len({row[column] for row in rows}) < len(rows) for column in range(1, width)):
            found.append(run)
    return found


def match_grid(lines: List[str]) -> List[Dict[str, Any]]:
    """A header row plus equal-width body rows — a matrix of no particular subject.

    A recipe and a form are both grids; the header and the cells are all the shape carries.
    """
    found = []
    for table in _tables(lines):
        header, rows = table["header"], table["rows"]
        if not header or not rows:
            continue
        if len({len(header)} | {len(row) for row in rows}) != 1:
            continue  # a ragged table is not a grid
        found.append({"rows": rows, "header": header, "unit": None, "title": table["title"]})
    return found


def match_events(lines: List[str]) -> List[Dict[str, Any]]:
    """A time or date plus a label — the generic timeline shape, rows and all (`route` is `events`)."""
    return match_timeline(lines)


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
    "state-transitions": match_state,
    "sequence-messages": match_sequence,
    "gantt-schedule": match_gantt,
    "pie-shares": match_pie,
    "dated-events": match_dated_events,
    "bracket": match_bracket,
    "gloss": match_gloss,
    "forms": match_forms,
    "funnel": match_funnel,
    "scatter": match_scatter,
    "waterfall": match_waterfall,
    "records": match_records,
    "grid": match_grid,
    "events": match_events,
    "groups": match_groups,
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
                          "header": None, "unit": None, "role": "division"})
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
                      "header": None, "unit": None, "role": "nested"})
    return found


def match_section_markdown(lines: List[str]) -> List[Dict[str, Any]]:
    """A markdown heading the answer **already** carries — never one the layer would insert.

    ``#`` and ``##`` are the answer's own division (level 1) and are left byte-identical: the words
    already read as a heading, so the layer only emits the band.  ``###`` and below are a
    sub-division, but only *within* a level-1 heading — a lone ``###`` (for instance the ``### `` the
    layer itself inserted last time) is not an anchor, which is what keeps a second pass a no-op.
    """
    found = []
    for index, line in enumerate(lines):
        hit = _HEADING_RE.match(line)
        if not hit:
            continue
        title = hit.group(1).strip()
        if not title:
            continue
        hashes = line.lstrip().split(None, 1)[0].count("#") or 1
        role = "nested" if hashes >= 3 else "division"
        found.append({"at": index, "title": title, "rows": [[title]],
                      "header": None, "unit": None, "role": role})
    return found


STRUCTURE_MATCHERS = {
    "section-bold": match_section_bold,
    "section-heading": match_section_heading,
    "section-markdown": match_section_markdown,
}

# Fallback roles for the matchers that do not set one per line.  An all-bold line *is* one of the
# answer's own divisions (level 1); a caption directly above a list or table, a `###` nested under a
# `##`, and an all-bold line inside a section a `##` has already opened, are divisions *within* one
# (level 2).  The renderer ranks by type size, not colour.
_SECTION_ROLES = {"section-bold": "division", "section-heading": "nested"}


def structure(text: str, rules, groups=None):
    """Return ``(structured_text, section_specs)``.

    Every anchor an active ``section`` rule matches — an all-bold line, a markdown heading the answer
    already carries, or a short heading-like line directly above a list or table — becomes a ``section``
    spec whose title is the anchor's own words, plus ``at`` (the anchor's line index, so the transform
    can pair it with the widgets that follow) and ``level``.  A bare caption (and, inside a ``##``
    section, a ``###`` heading) is promoted to level 2, and **only** where a level-1 band is already
    open in the same pass: a lone level 2 is impossible.  The words themselves are never reworded,
    deleted or reordered.  The one text edit is a ``### `` marker inserted in front of a caption, and
    the outer ``**`` coming off a promoted all-bold line (the heading supplies the emphasis); a markdown
    heading the answer already carries, and a ``**bold**`` phrase inside a sentence, are left untouched.
    Already-promoted text matches nothing, so a second pass changes nothing.
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
        role = _SECTION_ROLES.get(when)
        anchors.extend(
            (hit["at"], hit["title"], hit.get("role") or role or "division", when) for hit in hits
        )

    if not anchors:
        return text, []

    source = str(text).splitlines()
    seen = set()
    specs: List[Dict[str, Any]] = []
    open_level1 = False
    open_markdown = False
    for index, title, role, when in sorted(anchors):
        if index in seen or not (0 <= index < len(source)):
            continue
        seen.add(index)
        if when == "section-bold" and role == "division" and open_markdown:
            # an all-bold line *inside* a `##` the answer already carries sub-divides that section: it
            # is a level-2 band, not the answer's own division.  At the top level (no markdown heading
            # open) it is still a level 1, exactly as it was before.
            role = "nested"
        if role == "nested" and not open_level1:
            if when == "section-markdown":
                # a `###` outside any `##` is not a sub-division — not an anchor at all (and never the
                # layer's own `### ` marker on a second pass)
                continue
            # a lone level 2 is impossible: with no level-1 band open this is the answer's own division
            role = "division"
        level = 2 if role == "nested" else 1
        if level == 1:
            open_level1 = True
        if when == "section-markdown":
            if level == 1:
                open_markdown = True
            # the line already *is* a heading — emit the band, never touch the words
            specs.append({"kind": "section", "title": title, "rows": [], "at": index, "level": level})
            continue
        line = source[index]
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        # An all-bold line promoted to a heading would read ``### **Title**`` — a heading that is also
        # bold.  The marker supplies the emphasis, so the outer ``**`` pair comes off; the words do not
        # change.  This is the only edit the layer makes to a line's own text, and it touches no other
        # line: a non-bold caption keeps its bytes, only gaining the `### ` in front.
        body = title if when == "section-bold" else stripped
        source[index] = indent + "### " + body
        specs.append({"kind": "section", "title": title, "rows": [], "at": index, "level": level})
    if not specs:
        return text, []
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
                specs = _stand_down(specs)
                return specs

    return _stand_down(specs)


def _rows_key(spec: Dict[str, Any]):
    return tuple(tuple(row) for row in spec.get("rows") or ())


#: SPEC.md: where two kinds claim the same rows the more specific shape wins, so the loser stands
#: down.  `records`/`grid`/`events`/`groups` are the generic shapes and each stands down for every kind
#: that reads the same rows more specifically; a funnel is never also a heatmap, at any length.
_SHAPE_STANDS_DOWN = {
    "bars": ("heatmap", "pie", "funnel", "scatter", "waterfall"),
    "heatmap": ("funnel", "pie"),
    "records": (
        "gloss", "scatter", "waterfall", "groups", "events", "bars", "kpi", "funnel", "heatmap", "pie",
    ),
    "grid": ("bars", "parts", "forms"),
    "events": ("timeline", "dated-events", "groups"),
    "groups": ("gloss",),
}


def _stand_down(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Where two kinds claim the same rows, the more specific shape keeps them and the other stands down.

    ``heatmap``/``pie``/``funnel``/``scatter``/``waterfall`` all match the numeric run ``bars`` does, and
    the generic shapes (``records``, ``grid``, ``events``, ``groups``) match rows a specific kind may
    also claim — a funnel is never also a heatmap, and a record never doubles a gloss.  One dataset is
    emitted once.  With the specific groups off there is no such spec and the general shape keeps the
    rows.
    """
    claims: Dict[Any, set] = {}
    for spec in specs:
        claims.setdefault(_rows_key(spec), set()).add(spec.get("kind"))
    kept = []
    for spec in specs:
        kind = str(spec.get("kind") or "")
        others = claims.get(_rows_key(spec), set()) - {kind}
        if any(winner in _SHAPE_STANDS_DOWN.get(kind, ()) for winner in others):
            continue
        kept.append(spec)
    return kept
