"""Computed cells — a value the widget's own rows already determine.

SPEC.md, round 12.  A cell may be a **call on the payload's own rows**:

    Total=sum(Firmware, DSP, Web)
    Web share=share(Web, Total)
    Refunds=diff(Start, Net)

so a total is computed by the halves rather than by the model doing arithmetic in its head and
getting it wrong, or by the reader doing it by eye.  Brace-free by construction — parens and
commas are not reserved by the encoding, so a call travels inside `d` untouched and the app's
parser never sees a character it refuses.

**Pure and total.**  Nothing here raises, and a call that cannot be resolved — an unknown name,
a non-numeric row, a cycle, a division by zero — is left *exactly as written*: the core prints
it and `viz_dsl.is_drawable` refuses the directive, which is the one place a bad cell is caught
before a reader sees it.
"""

import re
from math import floor
from typing import Any, NamedTuple

__all__ = [
    "CALL_RE",
    "MAX_DEPTH",
    "is_call",
    "resolve_payload",
    "unresolved_calls",
    "number",
]

#: The whole value, never part of one: `sum(A, B)`, `share(A, B)`, `diff(A, B)`.  `[^()]*` keeps
#: the grammar flat — no call inside a call — so the resolver is a two-level walk, not a parser.
CALL_RE = re.compile(r"^(sum|share|diff)\(([^()]*)\)$")

#: How many rows a chain of calls may run through before it counts as unresolved.  A cycle is what
#: this exists for; the number is arbitrary and only has to be finite.
MAX_DEPTH = 8

#: How many arguments each function takes; `None` is "one or more".
ARITY = {"sum": None, "share": 2, "diff": 2}

#: The first number a text carries, signed, with a decimal point either side optional.
_NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")

#: A text that is *only* a number — the narrower rule a unit suffix is appended by.
PLAIN_NUMBER_RE = re.compile(r"^[-+]?(?:\d+\.?\d*|\.\d+)$")


class Resolved(NamedTuple):
    """A payload with its calls computed, and the calls that could not be."""

    payload: str
    unresolved: tuple


def number(text: Any) -> (float) | None:
    """The first number *text* carries, or ``None`` — the rule a named row's value is read by.

    Deliberately not "the whole text is a number": a row reads `1850 of 2200` (`nutrition`), `12 ms`
    or `42%`, and the amount is the leading number in every one of those.
    """
    match = _NUMBER_RE.search(str(text if text is not None else ""))
    return float(match.group(0)) if match else None


def is_call(text: Any) -> bool:
    """True when the whole of *text* is a call."""
    return bool(CALL_RE.match(str(text if text is not None else "").strip()))


def _format(value: float) -> str:
    """A computed number as text: an integer when it is one, else up to two decimals.

    The rounding is **half away from zero**, spelled out in integers, and the drawing core spells out
    the same one: a tie is exactly where two implementations diverge (`%.2f` rounds a tie to even,
    JavaScript's `toFixed` away from zero), and a total that reads `0.13` on the desktop and `0.12`
    everywhere else is the drift `tests/cells.json` exists to catch.  So the rule is arithmetic both
    halves can run identically, not a library's default.
    """
    scaled = value * 100
    cents = int(floor(abs(scaled) + 0.5))
    whole, frac = divmod(cents, 100)
    text = "%d" % whole
    if frac:
        text += "." + ("%02d" % frac).rstrip("0")
    return "-" + text if cents and scaled < 0 else text


def _cells(row: str) -> list:
    return row.split("|")


def _name(row: str) -> str:
    """The name a row answers to: its first cell's label."""
    return _cells(row)[0].split("=", 1)[0].strip()


def _value_of(cell: str) -> str:
    """The value half of a cell — everything past the first `=`, or the whole cell."""
    return cell.split("=", 1)[1] if "=" in cell else cell


class _Numbers:
    """Name -> number, resolved on demand, with a cycle guard and a memo."""

    def __init__(self, rows):
        self.rows: dict = {}
        for header, row in rows:
            if header:
                continue  # a header names a column; it is not a value to sum
            name = _name(row)
            if name and name not in self.rows:
                self.rows[name] = row
        self.memo: dict = {}
        self.busy: set = set()

    def get(self, name: str, depth: int = 0):
        if name in self.memo:
            return self.memo[name]
        if depth > MAX_DEPTH or name in self.busy:
            return None
        row = self.rows.get(name)
        if row is None:
            return None
        self.busy.add(name)
        try:
            value = self._from_row(row, depth)
        finally:
            self.busy.discard(name)
        if value is not None:
            self.memo[name] = value
        return value

    def _from_row(self, row: str, depth: int):
        """The first number the row carries — through a call when the cell is one."""
        for cell in _cells(row):
            raw = _value_of(cell).strip()
            call = CALL_RE.match(raw)
            if call:
                value = self.call(call.group(1), call.group(2), depth + 1)
                if value is not None:
                    return value
                continue
            found = number(raw)
            if found is not None:
                return found
        return None

    def call(self, name: str, args: str, depth: int = 0):
        """One call's value, or ``None`` when it cannot be resolved."""
        if name not in ARITY:
            return None
        names = [part.strip() for part in args.split(",")]
        names = [part for part in names if part]
        want = ARITY[name]
        if not names or (want is not None and len(names) != want):
            return None
        values = [self.get(part, depth) for part in names]
        if any(value is None for value in values):
            return None
        if name == "sum":
            return sum(values)
        if name == "diff":
            return values[0] - values[1]
        return values[0] / values[1] * 100 if values[1] else None


def _rows(payload: Any) -> list:
    """``(is_header, row)`` for every non-empty row of a payload, in order."""
    out = []
    for row in str(payload if payload is not None else "").split(";"):
        if not row.strip():
            continue
        out.append((row[:2].lower() == "h=", row[2:] if row[:2].lower() == "h=" else row))
    return out


def _put(cell: str, text: str) -> str:
    """*cell* with its value replaced, keeping the label as it was written."""
    if "=" not in cell:
        return text
    return cell.split("=", 1)[0] + "=" + text


def resolve_payload(payload: Any) -> Resolved:
    """*payload* with every resolvable call replaced by its number, and the ones that were not.

    Rows and cells are rebuilt as they were written — only a cell that *is* a call changes, so a
    payload without one comes back byte-identical.
    """
    rows = _rows(payload)
    numbers = _Numbers(rows)
    out: list = []
    unresolved: list = []

    for header, row in rows:
        cells = []
        for cell in _cells(row):
            call = CALL_RE.match(_value_of(cell).strip())
            if not call:
                cells.append(cell)
                continue
            value = numbers.call(call.group(1), call.group(2), 1)
            if value is None:
                unresolved.append(call.group(0))
                cells.append(cell)
                continue
            cells.append(_put(cell, _format(value)))
        out.append(("h=" if header else "") + "|".join(cells))

    return Resolved(";".join(out), tuple(unresolved))


def unresolved_calls(payload: Any) -> tuple:
    """The calls a payload carries that its own rows cannot compute."""
    return resolve_payload(payload).unresolved
