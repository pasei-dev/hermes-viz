"""hermes-viz — the agent half.

A ``transform_llm_output`` hook reads the answer the model already wrote and appends the widget
directives the rule table (``rules.yaml``) asks for.  Nothing here talks to the model: the picture
costs zero tokens.
"""

from pathlib import Path
import re
from collections.abc import Mapping
from typing import Any, Callable

try:  # loaded as a plugin package (Hermes sets __path__)
    from .python.derive import derive, load_rules, structure
    from .python.viz_dsl import (
        MERMAID_HEADERS,
        board_entry,
        mermaid_fence,
        strip_directives,
        to_board_directive,
    )
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from python.derive import derive, load_rules, structure
    from python.viz_dsl import (
        MERMAID_HEADERS,
        board_entry,
        mermaid_fence,
        strip_directives,
        to_board_directive,
    )

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
FORMAT_GUIDE_MAX_CHARS = 4000

#: The opt-in format guide, and the plugin's whole claim on the answer's shape.  A port of the host app's
#: answer-structuring mandate (`FORMAT_GUIDE`, chat.js), scaled to what this app can draw: headings for
#: sections, lists for steps, tables for comparisons, no decorative separators, and the strong one —
#: whenever something can be shown, show it, in the section it belongs to, one drawing per idea, several
#: in an explanation.  That is the door past the zero-token design's ceiling: the transform can only
#: annotate structure the answer already has, it cannot decide an idea deserves a drawing.  The guide
#: names **every** kind the drawing core has, with its payload, so the model can reach the ones no rule
#: derives — a guide that lists only the derived kinds leaves the rest unreachable, and the model has no
#: other channel to learn them.  `tests/test_format_guide.py` fails when the two lists drift apart.
#: It is a prompt on every request, so it stays as tight as it can while carrying the whole mandate; the
#: character/word/token counts live in `README.md`, `dashboard/settings.json` and the badge in
#: `dashboard/dist/index.js`, all of which must move in the same commit as this text.
FORMAT_GUIDE = """\
**Answer format.** Let the shape of the answer carry meaning: structure it, and show what can be shown.

- Give each section a `##` or `###` heading, short and plain. Never a bare bold line as a heading.
- `**Bold**` the key term in a sentence, and only the term.
- Give steps a list, one step per line. Give comparisons a table.
- Never draw a decorative separator (`---`, `***`); headings and blank lines are enough.
- When something can be shown, show it — in the section it belongs to. A text-only answer where
  something could be drawn is a dry answer.
- One drawing per idea, in the section that idea lives in. An explanation carries several: the whole as
  a scheme, the comparisons it turns on as charts, its key numbers as metrics. Never draw the same
  thing twice, and draw only the answer's own names and numbers — never invented filler.
- A note, tip or warning is a callout: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]` — not a plain quote.
- Math is `$…$` inline and `$$…$$` alone on its line.

**Widgets.** A widget is a `::viz{...}` directive alone on its own paragraph — one line, <=1200 chars,
`k=` kind, `d=` data, `t=` title, `u=` unit, and no `{` or `}` in the attrs:

    ::viz{k="table" d="h=Board|Runs;291e|42;223e|17"}

In `d` rows split on `;`, cells on `|`, key from value on `=`; a leading `h=` row is a header, and a
value carries no `;`, `|`, `=` or `~`.

A diagram is a ```mermaid fence instead, first line the type: flowchart, sequence, state, class, er,
gantt, pie, journey, gitgraph, timeline, quadrant, sankey, treemap, radar, xychart, mindmap, block.

Kinds, by payload:

- label=value — `kpi` `facts` `records` `progress` `heatmap` `settings` (`on|off`) `files` (`path=meta`)
  `words` `nutrition` (`value of target`); `metrics` adds `=delta`
- a numeric run — `bars` `line` `donut` `series` `sparkline` (bare numbers) `ranges` (`lo..hi`)
  `scatter` (`x=y`) `candlestick` (`o:h:l:c`) `waterfall` (`+n`)
- a `h=` header row — `table` `grid` `array` `parts` `recipe` (`!` warns) `forms` `bracket` (`w>l,…`)
  `wireframe` (`lbl=btn:2,text:3`)
- `checklist` `steps` (`done|doing|todo|blocked`) `outline` (`1=Title;1.1=Sub`) `changes` (`path=+a=-d`)
  `gloss` `matches` `groups`
- `timeline` `route` `events` (`when=label=detail`) `funnel` `stages` `pairs`
- `section` (`t=`, `l=1|2`) heads a section; `board` holds several widgets in one directive (entries
  split on `~`)

**What deserves a drawing.** Numbers to compare, a trend, shares of a whole, a budget, a value against a
norm, a process, a procedure, a schedule, a structure, a history, a hierarchy, a document, a file list —
each wants a drawing, not a paragraph. By what the reader needs: a few key numbers are `metrics`, a
ranking `bars`, a change over time `line`, a share `donut` or `pie`, steps `steps`, a status list
`checklist`, what changed `changes`, what a thing is at a glance `facts`, a build `parts`, a device's
settings `settings`, files `files`, a trip `route`, a language `words` `gloss` `forms`, a dish `recipe`
`nutrition`, fixtures `matches`, an interface `wireframe`.

**Before you answer.** Check the reply against these rules: a text-only answer where a chart, a diagram
or a widget fits is a worse answer. Draw it in this reply, unprompted, and keep the words around it
short — the widget replaces the prose, it never invents it.
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


def format_guide_section(enabled: Any) -> (str) | None:
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



def _is_mermaid(spec: dict[str, Any]) -> bool:
    """A spec is a diagram only when it carries a body — a ``timeline``/``pie`` *widget* still boards."""
    kind = spec.get("kind")
    return kind in MERMAID_HEADERS and (
        spec.get("body") is not None or spec.get("code") is not None
    )


def _segments(lines: list[str], sections: list[dict[str, Any]]):
    """``(start, end, section)`` for each section anchor and the widgets that follow it.

    A section runs from its anchor to the next one (or the end), so deriving each segment in turn pairs
    every section with its own widgets — heading, then its data, then the next heading.  With no anchors the
    whole answer is one sectionless segment, which is the single board the plugin had before.  The anchor
    itself is **never drawn**: it is the answer's own heading (or the one the layer inserted), and a second
    band carrying the same words under it is the same title twice.
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


def _source_tokens(lines: list[str]) -> set:
    """Every word/number a source line carries, with its list marker stripped."""
    tokens = set()
    for line in lines:
        text = _MARKER_RE.sub("", line.strip()).strip("* \t")
        tokens.update(_TOKEN_RE.findall(text))
    return tokens


def _drawn_text(spec: dict[str, Any], palette: str) -> str:
    """The text an emitted widget actually carries — a board entry, or a Mermaid fence's body."""
    if _is_mermaid(spec):
        return mermaid_fence(spec.get("kind"), spec, palette)
    return board_entry(spec) or ""


def _covers(source: list[str], drawn: str) -> bool:
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
    lines: list[str],
    sections: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    groups: (str) | None,
    max_widgets: (int) | None,
    palette: str,
) -> list[str]:
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

    insertions: dict[int, list[str]] = {}
    removed = set()
    used = 0

    for start, end, _section in _segments(lines, sections):
        specs = derive("\n".join(lines[start:end]), rules, groups, None)
        covered: list[Any] = []
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
        runs: list[dict[str, Any]] = []
        for absolute, span, spec in sorted(covered, key=lambda item: item[0]):
            if runs and absolute <= runs[-1]["end"]:
                runs[-1]["end"] = max(runs[-1]["end"], absolute + span)
                runs[-1]["items"].append((absolute, span, spec))
            else:
                runs.append({"end": absolute + span, "items": [(absolute, span, spec)]})

        for run in runs:
            items = run["items"]
            anchors = [absolute for absolute, _, spec in items if not _is_mermaid(spec)]
            board_specs = [spec for _, _, spec in items if not _is_mermaid(spec)]
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

    out: list[str] = []
    for index, line in enumerate(lines):
        out.extend(insertions.get(index, ()))
        if index in removed:
            continue
        out.append(line)
    out.extend(insertions.get(len(lines), ()))
    return out


def transform(
    response_text: str,
    rules: list[dict[str, Any]],
    groups: (str) | None = None,
    max_widgets: (int) | None = DEFAULT_MAX_WIDGETS,
    palette: str = DEFAULT_PALETTE,
) -> (str) | None:
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


#: The surfaces that render a `::viz` directive.  The desktop app is the only one: everywhere else — the
#: CLI, the TUI, a chat gateway, the dashboard, an API client — the directive is not parsed, so it would
#: reach the reader as its own literal text (`::viz{k="board" d="…"}`) instead of a drawing.  The answer
#: is therefore left exactly as the model wrote it on every other platform, and an unknown platform is
#: treated the same way: no widget is a smaller failure than a line of raw grammar in the transcript.
DRAWING_PLATFORMS = frozenset({"desktop"})


def _draws_here(platform: Any) -> bool:
    """True when *platform* is a surface that can draw a directive."""
    return str(platform or "").strip().lower() in DRAWING_PLATFORMS


def make_hook(
    rules: list[dict[str, Any]],
    groups: (str) | None = DEFAULT_RULE_GROUPS,
    max_widgets: (int) | None = DEFAULT_MAX_WIDGETS,
    palette: str = DEFAULT_PALETTE,
) -> Callable[..., (str) | None]:
    """The hook callback itself, closed over one config snapshot."""

    def hook(
        response_text: str,
        session_id: str = "",
        model: str = "",
        platform: str = "",
        **kwargs
    ) -> (str) | None:
        # A delegated child's answer is read by the orchestrator, not by a person: leave it alone.
        if _is_child_session():
            return None
        # Only the surface that parses the directive may be given one — see DRAWING_PLATFORMS.  The other
        # half of that rule: a directive the model wrote itself is taken back out, because on a surface that
        # cannot draw it is raw grammar in front of the reader, not a drawing.  No directive found means the
        # answer is returned untouched, so the no-op case stays byte-identical.
        if not _draws_here(platform):
            stripped = strip_directives(response_text)
            return None if stripped == response_text else stripped
        return transform(response_text, rules, groups, max_widgets, palette)

    return hook


def _read_config(ctx) -> dict[str, Any]:
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
            # Same two gates as the hook: a child's answer goes to the orchestrator, and only a surface
            # that parses a directive should be asked to write one.
            if _is_child_session(session_info):
                return ""
            platform = session_info.get("platform") if isinstance(session_info, Mapping) else ""
            return guide if _draws_here(platform) else ""

        try:
            register_section(FORMAT_GUIDE_SECTION_ID, guide_for_session, max_chars=FORMAT_GUIDE_MAX_CHARS)
        except Exception:
            pass  # an older Hermes without system-prompt sections still gets the transform hook
