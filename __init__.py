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

__all__ = [
    "register",
    "transform",
    "make_hook",
    "RULES_PATH",
    "FORMAT_GUIDE",
    "format_guide_section",
    "format_guide_prompt",
]

RULES_PATH = Path(__file__).with_name("rules.yaml")

DEFAULT_PALETTE = "dark"
DEFAULT_MAX_WIDGETS = 3
#: `structure` is on by default — structuring the answer is the point of the plugin, not a widget.
DEFAULT_RULE_GROUPS = "structure,numbers,tables,steps,checklist,changes,outline,facts,files,parts,settings,timeline,ranges,metrics,array,heatmap,wireframe,candlestick,records,grid,events,groups,bracket,gloss,forms,funnel,scatter,waterfall,flow,mermaid"
#: The format guide is a prompt on every request, and it ships ON: `plugin.yaml` states the cost, which
#: is a deliberate trade this profile makes, and an off setting still adds nothing, byte for byte.
DEFAULT_FORMAT_GUIDE = True

#: The system-prompt section id the guide registers under (Hermes renders it as `## Plugin Context: …`).
FORMAT_GUIDE_SECTION_ID = "hermes-viz-format"
FORMAT_GUIDE_MAX_CHARS = 2000

#: The opt-in format guide, and the plugin's whole claim on
#: the answer's shape: headings for sections, lists for steps, tables for comparisons, no decorative separators,
#: and the strong one: whenever something can be drawn, draw it, in the section it belongs to.  That is
#: the door past the zero-token design's ceiling: the transform can only annotate structure the answer
#: already has, it cannot decide an idea deserves a drawing.  Kept small on purpose — it is a prompt on
#: every request, so every character is paid for.
FORMAT_GUIDE = """\
**Answer format.** Let the shape of the answer carry meaning:

- Give each section a `##`/`###` heading. Never use a bare bold line as a heading.
- Give steps a list, one step per line.
- Give comparisons a table.
- Never draw a decorative separator (`---`, `***`); headings and blank lines are enough.
- When something can be shown, show it — in the section it belongs to. A text-only answer where
  something could be shown is a dry answer.

Show a widget with a `::viz{...}` directive alone on its own paragraph — one line, <=1200 chars, with no
`{` or `}` anywhere inside the attributes:

    ::viz{k="bars" d="Firmware=42;DSP=28;Web=18" u="%"}
    ::viz{k="kpi" d="Builds=128=+12;Fails=3=-1"}
    ::viz{k="table" d="h=Board|Runs;291e|42;223e|17"}
    ::viz{k="steps" d="Read the archive;Patch the entry;Flash over EC3"}

Rows split on `;`, cells on `|`, label from value on `=`. Kinds: `kpi` `bars` `line` `donut` `steps`
`table` `progress` `sparkline`. A diagram is a ```mermaid fence (flowchart, sequence, state, pie, gantt,
timeline, mindmap).
"""


def _enabled(value: Any) -> bool:
    """A settings flag, read generously: a bool, a zero/one, or a 'true'/'on'/'yes' string."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def format_guide_section(enabled: Any) -> Optional[str]:
    """The format-guide prompt section text, or ``None`` when the setting is off.

    ``None`` is what makes an off setting measurably free: with no text there is no section to register,
    so the rendered prompt is byte-identical to one from a plugin that has no guide at all.
    """
    return FORMAT_GUIDE if _enabled(enabled) else None


def format_guide_prompt(base_prompt: str, enabled: Any) -> str:
    """*base_prompt* with the guide appended when it is on — byte-identical when it is off.

    Hermes core owns the real append (it renders the registered section once per session); this is the
    same composition, spelled out so "identical when off" and "exactly one copy when on" are checkable
    without a live session.
    """
    guide = format_guide_section(enabled)
    if not guide:
        return base_prompt
    if guide in base_prompt:  # never stack a second copy
        return base_prompt
    if base_prompt.endswith("\n\n"):
        separator = ""
    elif base_prompt.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    return base_prompt + separator + guide



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
    """The settings ``plugin.yaml`` declares, with their declared defaults."""
    getter = getattr(ctx, "get_config", None)
    read = {}

    for key, default in (
        ("palette", DEFAULT_PALETTE),
        ("max_widgets", DEFAULT_MAX_WIDGETS),
        ("rule_groups", DEFAULT_RULE_GROUPS),
        ("format_guide", DEFAULT_FORMAT_GUIDE),
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
    """Read the config, load the rule table, register the transform hook and the format guide.

    The format guide is a system-prompt section registered only when its setting is on, so with the
    setting off nothing at all reaches the prompt — the guide's whole cost is opt-in.
    """
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

    guide = format_guide_section(config["format_guide"])
    register_section = getattr(ctx, "register_system_prompt_section", None)
    if guide and callable(register_section):
        try:
            register_section(FORMAT_GUIDE_SECTION_ID, guide, max_chars=FORMAT_GUIDE_MAX_CHARS)
        except Exception:
            pass  # an older Hermes without system-prompt sections still gets the transform hook
