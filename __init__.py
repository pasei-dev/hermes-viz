"""hermes-viz — the agent half.

A ``transform_llm_output`` hook reads the answer the model already wrote and appends the widget
directives the rule table (``rules.yaml``) asks for.  Nothing here talks to the model: the picture
costs zero tokens.
"""

from pathlib import Path
import re
from typing import Mapping, Any, Callable, Dict, List, Optional

try:  # loaded as a plugin package (Hermes sets __path__)
    from .python.derive import derive, load_rules, structure
    from .python.viz_dsl import MERMAID_HEADERS, board_entry, mermaid_fence, to_board_directive
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from python.derive import derive, load_rules, structure
    from python.viz_dsl import MERMAID_HEADERS, board_entry, mermaid_fence, to_board_directive

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


# ------------------------------------------------------------------------------------------------
# the losslessness rule — a widget may replace its source lines only when it carries them all

#: The encoding reserves these characters and ``clean_value`` squashes them to a space, so a source
#: line carrying one is not carried faithfully and is never replaced.  `;` `~` `\` `"` `{` `}` are
#: never separators — unlike `=` and `|`, which the encodings use and are therefore allowed.
_SOURCE_UNSAFE = (";", "~", "\\", '"', "{", "}")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
#: A line's own list/checkbox marker — formatting the widget replays, not content it must carry.
_MARKER_RE = re.compile(r"^[ \t]*(?:[-*+][ \t]+(?:\[[ xX/~!\\-]\][ \t]+)?|\d{1,3}[.)][ \t]+)+")


def _source_tokens(lines: List[str]) -> set:
    """Every word/number a source line carries, with its list marker stripped."""
    tokens = set()
    for line in lines:
        text = _MARKER_RE.sub("", line.strip()).strip("* \t")
        tokens.update(_TOKEN_RE.findall(text))
    return tokens


def _drawn_text(spec: Dict[str, Any], palette: str) -> str:
    """The text an emitted widget actually carries — a board entry, or a Mermaid fence's body."""
    if _is_mermaid(spec):
        return mermaid_fence(spec.get("kind"), spec, palette)
    return board_entry(spec) or ""


def _covers(source: List[str], drawn: str) -> bool:
    """True when *drawn* carries every token *source* carried, and *source* holds no reserved char.

    A reserved character is silently squashed to a space by the emitter, so a line carrying one is not
    carried faithfully; a token missing from the drawn text means the widget would drop detail.  Either
    way the prose stays and no widget is emitted — a duplicate is worse than no widget, and a silent
    loss of the answer's own words is worse than both.
    """
    if not drawn or not source:
        return False
    for line in source:
        if any(char in line for char in _SOURCE_UNSAFE):
            return False
    return _source_tokens(source) <= set(_TOKEN_RE.findall(drawn))


def _splice(
    lines: List[str],
    sections: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
    groups: Optional[str],
    max_widgets: Optional[int],
    palette: str,
) -> List[str]:
    """Each covered run replaced by its widget, in place; every uncovered line left alone.

    Deriving one segment at a time keeps a section band riding with the widgets that follow it in one
    board, but the board now lands where the first of its source runs was, so a section reads heading,
    widget, next heading.  A widget that does not carry its source is dropped and its lines stay.
    """
    budget = None
    if max_widgets is not None:
        try:
            budget = max(0, int(max_widgets))
        except (TypeError, ValueError):
            budget = None

    insertions: Dict[int, List[str]] = {}
    removed = set()
    used = 0

    for start, end, section in _segments(lines, sections):
        specs = derive("\n".join(lines[start:end]), rules, groups, None)
        covered: List[Any] = []
        for spec in specs:
            at = spec.get("at")
            span = spec.get("lines")
            if at is None or span is None:
                continue  # the matcher could not report its span honestly — never guess
            absolute = start + at
            if _covers(lines[absolute : absolute + span], _drawn_text(spec, palette)):
                covered.append((absolute, span, spec))

        if budget is not None:
            covered = covered[: max(0, budget - used)]
            used += len(covered)

        # One board per contiguous group of runs, so a widget lands where its own source was rather
        # than being dragged to another run's position.
        runs: List[Dict[str, Any]] = []
        for absolute, span, spec in sorted(covered, key=lambda item: item[0]):
            if runs and absolute <= runs[-1]["end"]:
                runs[-1]["end"] = max(runs[-1]["end"], absolute + span)
                runs[-1]["items"].append((absolute, span, spec))
            else:
                runs.append({"end": absolute + span, "items": [(absolute, span, spec)]})

        band = _section_band(section) if section is not None else None
        placed_band = False
        for run in runs:
            items = run["items"]
            anchors = [absolute for absolute, _, spec in items if not _is_mermaid(spec)]
            board_specs: List[Dict[str, Any]] = []
            if band is not None and anchors and not placed_band:
                board_specs.append(band)
                placed_band = True
            board_specs.extend(spec for _, _, spec in items if not _is_mermaid(spec))
            board = to_board_directive(board_specs)
            if board:
                insertions.setdefault(min(anchors) if anchors else start + 1, []).append(board)
            for absolute, _, spec in items:
                if _is_mermaid(spec):
                    insertions.setdefault(absolute, []).append(
                        mermaid_fence(spec.get("kind"), spec, palette)
                    )
            for absolute, span, _ in items:
                removed.update(range(absolute, absolute + span))

        if band is not None and not placed_band:
            # a section with no covered widget still gets its band, right under its heading
            board = to_board_directive([band])
            if board:
                insertions.setdefault(start + 1, []).append(board)

    out: List[str] = []
    for index, line in enumerate(lines):
        out.extend(insertions.get(index, ()))
        if index in removed:
            continue
        out.append(line)
    out.extend(insertions.get(len(lines), ()))
    return out


def transform(
    response_text: str,
    rules: List[Dict[str, Any]],
    groups: Optional[str] = None,
    max_widgets: Optional[int] = DEFAULT_MAX_WIDGETS,
    palette: str = DEFAULT_PALETTE,
) -> Optional[str]:
    """The answer with its headings inserted and each covered run replaced by its widget, or None.

    The structure layer runs first: an answer that already behaves like a section gets a ``### `` marker
    in front of the anchor.  From there each derived widget *replaces* the lines it was derived from —
    in place, so a section reads heading, widget, next heading, and the answer is never longer than the
    prose it already had.  A widget whose source carried more than the widget draws is dropped and the
    prose stays; a Mermaid *diagram* (a spec with a body) replaces its source with its own fence.  An
    answer that already carries a ``::viz{`` directive is left alone, which makes a second pass a no-op.
    """
    if not isinstance(response_text, str) or not response_text.strip():
        return None
    if "::viz{" in response_text:
        return None

    try:
        structured, sections = structure(response_text, rules, groups)
        output_lines = _splice(
            structured.splitlines(), sections, rules, groups, max_widgets, palette
        )
    except Exception:
        return None  # never take the answer down with us; Hermes logs the failure

    output = "\n".join(output_lines).rstrip()
    if output == response_text.rstrip():
        return None
    return output + "\n"


def _is_child_session(session_info=None) -> bool:
    """True when the answer belongs to a delegate_task child, not a main session.

    A child's text is read by the orchestrator, never by a person, so a heading or a widget there is
    waste twice over: it buys nothing, and it inflates the report the parent has to read. Two signals,
    exact one first:

    - ``is_delegated_child_context()`` — the contextvar Hermes sets while running a delegate_task child.
      It is the authoritative answer, and it is in this process, so it costs a lazy import.
    - a session-info mapping that names a parent. The prompt-section callable receives one; the
      transform hook does not, so this branch only ever fires for the guide.

    An older Hermes without ``agent.delegation_context`` cannot be asked, and then we transform: an
    unknown session is assumed to be a person's, which is the safe direction to fail in.
    """
    try:
        from agent.delegation_context import is_delegated_child_context

        if is_delegated_child_context():
            return True
    except Exception:
        pass
    if isinstance(session_info, Mapping):
        for key in ("subagent_id", "parent_session_id", "parent_subagent_id", "is_subagent", "delegated"):
            try:
                if session_info.get(key):
                    return True
            except Exception:
                pass
    return False


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
        # A delegated child's answer is read by the orchestrator, not by a person: leave it alone.
        if _is_child_session():
            return None
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
        def guide_for_session(session_info=None) -> str:
            # Same rule as the hook: a child gets no guide, because its answer goes to the orchestrator.
            return "" if _is_child_session(session_info) else guide

        try:
            register_section(FORMAT_GUIDE_SECTION_ID, guide_for_session, max_chars=FORMAT_GUIDE_MAX_CHARS)
        except Exception:
            pass  # an older Hermes without system-prompt sections still gets the transform hook
