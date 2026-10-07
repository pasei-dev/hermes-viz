"""hermes-viz — the agent half.

A ``transform_llm_output`` hook reads the answer the model already wrote and appends the widget
directives the rule table (``rules.yaml``) asks for.  Nothing here talks to the model: the picture
costs zero tokens.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:  # loaded as a plugin package (Hermes sets __path__)
    from .python.derive import derive, load_rules, structure
    from .python.viz_dsl import MERMAID_HEADERS, mermaid_fence, to_board_directive
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from python.derive import derive, load_rules, structure
    from python.viz_dsl import MERMAID_HEADERS, mermaid_fence, to_board_directive

__all__ = ["register", "transform", "make_hook", "RULES_PATH"]

RULES_PATH = Path(__file__).with_name("rules.yaml")

DEFAULT_PALETTE = "dark"
DEFAULT_MAX_WIDGETS = 3
#: `structure` is on by default — structuring the answer is the point of the plugin, not a widget.
DEFAULT_RULE_GROUPS = "numbers,tables,steps,structure"


def _is_mermaid(spec: Dict[str, Any]) -> bool:
    """A spec is a diagram only when it carries a body — a ``timeline``/``pie`` *widget* still boards."""
    kind = spec.get("kind")
    return kind in MERMAID_HEADERS and (
        spec.get("body") is not None or spec.get("code") is not None
    )


def _section_band(section: Dict[str, Any]) -> Dict[str, Any]:
    """A structure spec without its position — the band the board draws at the head of a section."""
    return {key: value for key, value in section.items() if key != "at"}


def _segments(lines: List[str], sections: List[Dict[str, Any]]):
    """``(start, end, section)`` for each section band and the widgets that follow it.

    A section runs from its anchor to the next one (or the end), so deriving each segment in turn pairs
    every band with its own widgets — heading, then its data, then the next heading.  With no anchors the
    whole answer is one sectionless segment, which is the single board the plugin had before.
    """
    bounds = [
        (int(section["at"]), section)
        for section in sections or []
        if isinstance(section, dict) and isinstance(section.get("at"), int)
    ]
    bounds.sort(key=lambda pair: pair[0])
    if not bounds:
        return [(0, len(lines), None)]

    segments = []
    if bounds[0][0] > 0:
        segments.append((0, bounds[0][0], None))
    for position, (start, section) in enumerate(bounds):
        end = bounds[position + 1][0] if position + 1 < len(bounds) else len(lines)
        segments.append((start, end, section))
    return segments


def _boards(
    structured: str,
    sections: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    groups: Optional[str],
    max_widgets: Optional[int],
    palette: str,
) -> List[str]:
    budget = None
    if max_widgets is not None:
        try:
            budget = max(0, int(max_widgets))
        except (TypeError, ValueError):
            budget = None

    lines = structured.splitlines()
    blocks: List[str] = []
    used = 0
    for start, end, section in _segments(lines, sections):
        specs = derive("\n".join(lines[start:end]), rules, groups, None)
        if budget is not None:
            specs = specs[: max(0, budget - used)]
            used += len(specs)

        board_specs: List[Dict[str, Any]] = []
        if section is not None:
            board_specs.append(_section_band(section))
        board_specs.extend(spec for spec in specs if not _is_mermaid(spec))

        board = to_board_directive(board_specs)
        if board:
            blocks.append(board)
        for spec in specs:
            if _is_mermaid(spec):
                blocks.append(mermaid_fence(spec.get("kind"), spec, palette))
    return blocks


def transform(
    response_text: str,
    rules: List[Dict[str, Any]],
    groups: Optional[str] = None,
    max_widgets: Optional[int] = DEFAULT_MAX_WIDGETS,
    palette: str = DEFAULT_PALETTE,
) -> Optional[str]:
    """The answer with its headings inserted and its widgets appended, or None when nothing changes.

    The structure layer runs first: an answer that already behaves like a section gets a ``### `` marker
    in front of the anchor.  From there the answer is read one section at a time, so each band and the
    widgets that follow it land in the *same* ``board`` paragraph — heading, its own data, next heading.
    A Mermaid *diagram* (a spec with a body) still gets its own fence.  An answer that already carries a
    ``::viz{`` directive is left alone — an explicit override wins wherever it appears, and that guard
    makes a second pass a no-op.
    """
    if not isinstance(response_text, str) or not response_text.strip():
        return None
    if "::viz{" in response_text:
        return None

    try:
        structured, sections = structure(response_text, rules, groups)
        blocks = _boards(structured, sections, rules, groups, max_widgets, palette)
    except Exception:
        return None  # never take the answer down with us; Hermes logs the failure

    output = structured.rstrip()
    if blocks:
        output += "\n\n" + "\n\n".join(blocks)
    if output == response_text.rstrip():
        return None
    return output + "\n"


def make_hook(
    rules: List[Dict[str, Any]],
    groups: Optional[str] = DEFAULT_RULE_GROUPS,
    max_widgets: Optional[int] = DEFAULT_MAX_WIDGETS,
    palette: str = DEFAULT_PALETTE,
) -> Callable[..., Optional[str]]:
    """The hook callback itself, closed over one config snapshot."""

    def hook(
        response_text: str,
        session_id: str = "",
        model: str = "",
        platform: str = "",
        **kwargs
    ) -> Optional[str]:
        return transform(response_text, rules, groups, max_widgets, palette)

    return hook


def _read_config(ctx) -> Dict[str, Any]:
    """The three settings ``plugin.yaml`` declares, with their declared defaults."""
    getter = getattr(ctx, "get_config", None)
    read = {}

    for key, default in (
        ("palette", DEFAULT_PALETTE),
        ("max_widgets", DEFAULT_MAX_WIDGETS),
        ("rule_groups", DEFAULT_RULE_GROUPS),
    ):
        value = None
        if callable(getter):
            try:
                value = getter(key, default)
            except Exception:
                value = None
        read[key] = default if value is None else value

    try:
        read["max_widgets"] = int(read["max_widgets"])
    except (TypeError, ValueError):
        read["max_widgets"] = DEFAULT_MAX_WIDGETS
    read["rule_groups"] = str(read["rule_groups"])
    read["palette"] = str(read["palette"])
    return read


def register(ctx) -> None:
    """Read the config, load the rule table, register the transform hook."""
    config = _read_config(ctx)
    try:
        rules = load_rules(RULES_PATH)
    except Exception:
        rules = []
    ctx.register_hook(
        "transform_llm_output",
        make_hook(
            rules,
            groups=config["rule_groups"],
            max_widgets=config["max_widgets"],
            palette=config["palette"],
        ),
    )
