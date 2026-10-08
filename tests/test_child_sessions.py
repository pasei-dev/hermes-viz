"""A delegate_task child's answer goes to the orchestrator, never to a reader.

So it must not be structured and it must not be drawn on: a heading there buys nothing and inflates the
report the parent has to read. The gate is `is_delegated_child_context()` — the contextvar Hermes sets
while a child runs — with a session-info mapping as the second signal.
"""

import importlib
import os
import sys

from _agent import RULES, agent


def test_a_delegated_child_is_left_untouched():
    hook = agent.make_hook(RULES, groups="structure,numbers,tables", max_widgets=8, palette="dark")
    answer = "**Flash report**\n\nBuild: 42\nTest: 18\n"

    assert hook(answer, platform="desktop") is not None, "a main session is transformed"

    # the session-info signal, which is always testable
    assert agent._is_child_session({"subagent_id": "sa-0-abc"}) is True
    assert agent._is_child_session({"parent_session_id": "20260101_000000_a"}) is True
    assert agent._is_child_session(None) is False
    assert agent._is_child_session({}) is False

    # And the authoritative contextvar. The plugin's own tests do not put Hermes on sys.path (the hook
    # at runtime does), so add it rather than skip — a branch that silently returns tests nothing.
    try:
        # importlib, not `import agent…`: a plain import binds the name `agent` locally and would shadow
        # the plugin module this test calls.
        importlib.import_module("agent.delegation_context")
    except Exception:
        for cand in (os.environ.get("HERMES_ROOT"), os.path.expanduser("~/.hermes/hermes-agent")):
            if cand and os.path.isdir(os.path.join(cand, "agent")):
                sys.path.insert(0, cand)
                break
    try:
        from agent.delegation_context import delegated_child_context
    except Exception:
        return  # an older Hermes genuinely has no such module

    # The plugin's floor is 3.10 — the same as Hermes itself — so the contextvar is exercised on every
    # interpreter this suite can run on. No version branch here: one that silently returned would test
    # nothing while reading as a pass.

    with delegated_child_context("20260101_000000_child"):
        assert agent._is_child_session() is True
        assert hook(answer, platform="desktop") is None, "a delegated child's answer is left untouched"

    assert hook(answer, platform="desktop") is not None, "the parent is unaffected afterwards"
