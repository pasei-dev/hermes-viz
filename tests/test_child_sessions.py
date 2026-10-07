"""A delegate_task child's answer goes to the orchestrator, never to a reader.

So it must not be structured and it must not be drawn on: a heading there buys nothing and inflates the
report the parent has to read. The gate is `is_delegated_child_context()` — the contextvar Hermes sets
while a child runs — with a session-info mapping as the second signal.
"""

from _agent import RULES, agent


def test_a_delegated_child_is_left_untouched():
    hook = agent.make_hook(RULES, groups="structure,numbers,tables", max_widgets=8, palette="dark")
    answer = "**Flash report**\n\nBuild: 42\nTest: 18\n"

    assert hook(answer) is not None, "a main session is transformed"

    # the session-info signal, which is always testable
    assert agent._is_child_session({"subagent_id": "sa-0-abc"}) is True
    assert agent._is_child_session({"parent_session_id": "20260101_000000_a"}) is True
    assert agent._is_child_session(None) is False
    assert agent._is_child_session({}) is False

    # and the authoritative contextvar, when this Hermes has one
    try:
        from agent.delegation_context import delegated_child_context
    except Exception:
        return  # older Hermes: the contextvar cannot be exercised from here

    with delegated_child_context("20260101_000000_child"):
        assert agent._is_child_session() is True
        assert hook(answer) is None, "a delegated child's answer is left untouched"

    assert hook(answer) is not None, "the parent is unaffected afterwards"
