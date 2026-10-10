"""Computed cells: a widget's own rows determine a value the model must not do arithmetic for.

SPEC.md, round 12.  The rule is one table (`tests/cells.json`) read by **both** halves — this file for
the agent half, `tests/desktop.test.mjs` for the drawing core — because the same call has to resolve to
the same number wherever it is drawn or printed.  A rule that drifts fails here rather than in an
answer nobody can see was wrong.
"""

import json

from _agent import agent
from python.viz_expr import CALL_RE, is_call, number, resolve_payload, unresolved_calls

VECTORS = json.loads((agent.RULES_PATH.parent / "tests" / "cells.json").read_text(encoding="utf-8"))["vectors"]


def test_the_vectors_all_resolve_where_they_should():
    for vector in VECTORS:
        payload, expected = vector["payload"], vector["resolved"]
        got, unresolved = resolve_payload(payload)
        assert got == expected, "%s\n  %r -> %r" % (vector["why"], payload, got)
        assert list(unresolved) == vector["unresolved"], "%s → %r" % (vector["why"], unresolved)


def test_a_payload_with_no_call_is_returned_byte_identical():
    """The pass must never rewrite an answer's own encoding: no call, no change at all."""
    for payload in ("A=1;B=2", "", "h=Board|Runs;Alpha|42", "  spaced = 1 ; b = 2 ", "12;18;9"):
        assert resolve_payload(payload).payload == payload


def test_the_call_is_the_whole_value_and_never_part_of_one():
    assert is_call("sum(A, B)") and is_call(" sum(A,B) ")
    for text in ("about sum(A, B)", "sum(A, B) ms", "Sum(A, B)", "sum(A)(B)", "sum2(A, B)", ""):
        assert not is_call(text), text
    # `[^()]*` keeps the grammar flat: a call inside a call is not a call either
    assert CALL_RE.match("sum(A, B)") is not None
    assert CALL_RE.match("sum(share(A, B), C)") is None


def test_a_named_row_is_read_by_the_first_number_it_carries():
    """Not "the whole text is a number": `1850 of 2200`, `12 ms` and `42%` all carry an amount."""
    assert number("1850 of 2200") == 1850.0
    assert number("12 ms") == 12.0
    assert number("42%") == 42.0
    assert number("-45") == -45.0
    assert number("nothing here") is None


def test_the_three_functions_and_their_arity():
    assert resolve_payload("A=2;B=3;T=sum(A, B)").payload.endswith("T=5")
    assert resolve_payload("A=2;B=3;T=diff(A, B)").payload.endswith("T=-1")
    assert resolve_payload("A=2;B=4;T=share(A, B)").payload.endswith("T=50")
    # `sum` takes one or more names, `share` and `diff` exactly two
    assert resolve_payload("A=2;T=sum(A)").payload.endswith("T=2")
    assert unresolved_calls("A=2;B=4;T=share(A)") == ("share(A)",)
    assert unresolved_calls("A=2;B=4;T=share(A, B, A)") == ("share(A, B, A)",)
    assert unresolved_calls("A=2;B=4;T=sum()") == ("sum()",)


def test_a_computed_value_is_a_number_a_renderer_can_plot():
    """The point of the tier: a widget that carries a total draws it, it does not print a formula."""
    payload, unresolved = resolve_payload("Firmware=42;DSP=28;Web=18;Total=sum(Firmware, DSP, Web)")
    assert not unresolved
    assert payload.endswith("Total=88")
    assert "sum(" not in payload


def test_the_evaluator_never_raises_and_never_invents():
    for payload in (None, 0, [], "sum(", "A=sum(B, C", "A=1;T=sum(A, ", ";;;", "=sum()"):
        resolved = resolve_payload(payload)
        assert isinstance(resolved.payload, str)
        assert "nan" not in resolved.payload.lower()


def test_the_agent_half_and_the_drawing_core_read_the_same_table():
    """`tests/cells.json` is the one contract; the core's own suite reads it too, from node."""
    core = (agent.RULES_PATH.parent / "tests" / "desktop.test.mjs").read_text(encoding="utf-8")
    assert "cells.json" in core, "the drawing core does not read the shared vectors"
    assert "resolveCells" in core, "the core's suite does not exercise the resolver"
