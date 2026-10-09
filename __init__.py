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
#: `changes` is the ONE off group: the host draws its own changed-files list, so the plugin's copy of it
#: stays out of the way. The rule and the renderer are kept, and a user can turn the group on.
DEFAULT_RULE_GROUPS = "structure,numbers,tables,steps,checklist,outline,facts,files,parts,settings,timeline,ranges,metrics,array,heatmap,wireframe,candlestick,records,grid,events,groups,bracket,gloss,forms,funnel,scatter,waterfall,flow,mermaid"
#: The groups the plugin ships OFF, and the only ones `DEFAULT_RULE_GROUPS` may omit.
DEFAULT_RULE_GROUPS_OFF = ("changes",)
#: The format guide is a prompt on every request, and it ships ON: `plugin.yaml` states the cost, which
#: is a deliberate trade this profile makes, and an off setting still adds nothing, byte for byte.
DEFAULT_FORMAT_GUIDE = True

#: The system-prompt section id the guide registers under (Hermes renders it as `## Plugin Context: …`).
FORMAT_GUIDE_SECTION_ID = "hermes-viz-format"
FORMAT_GUIDE_MAX_CHARS = 4800

#: The opt-in format guide, and the plugin's whole claim on the answer's shape.  A port of the host app's
#: answer-structuring mandate (`FORMAT_GUIDE`, chat.js), scaled to what this app can draw: headings for
#: sections, lists for steps, tables for comparisons, no decorative separators, and the strong one —
#: whenever something can be shown, show it, in the section it belongs to, one drawing per idea, several
#: in an explanation.  That is the door past the zero-token design's ceiling: the transform can only
#: annotate structure the answer already has, it cannot decide an idea deserves a drawing.
#:
#: **The kind block is generated from the rule table, never written out.**  A kind rides on the groups
#: whose rules can produce it, so a group a user turned OFF takes its kinds out of the prompt altogether:
#: the guide names what the live groups can draw and nothing else.  A prompt that says "`changes` is off"
#: is a prompt paying tokens to describe a kind the model may not write — a disabled feature leaves the
#: prompt the way it leaves the rule table.  `tests/test_format_guide.py` walks both directions: every
#: kind the core draws is named once its groups are on, and no gated kind is named once they are off.
#: It is a prompt on every request, so it stays as tight as it can while carrying the whole mandate; the
#: character/word/token counts live in `README.md`, `dashboard/settings.json` and the badge in
#: `dashboard/dist/index.js`, all of which must move in the same commit as this text.
#:
#: The mandate prose above the kind block is the same for every configuration: headings, lists, tables,
#: callouts and math are the app's own markdown, not plugin kinds, so turning a rule group off never
#: means the answer may not use a table.
GUIDE_HEAD = """\
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

**Say less.** The answer the reader came for, and nothing around it:

- The first line IS the answer — the fact, the number, the command, the decision. Never an announcement
  of what you are about to do, never the question again, never a recap of what is on screen.
- One idea per line. A paragraph over three lines is a wall the reader skips.
- Say a thing once: a widget, a table or a list replaces the prose beside it rather than repeating it.
  Cut justification, hedges, and any section nobody asked for.
- No closing line that offers more ("let me know if…"). A next step only when there is one.

**Widgets.** A widget is a `::viz{...}` directive alone on its own paragraph — one line, <=1200 chars,
`k=` kind, `d=` data, `t=` title, `u=` unit, `n=` a hover note, and no `{` or `}` in the attrs:

    ::viz{k="table" d="h=Board|Runs;291e|42;223e|17"}

In `d` rows split on `;`, cells on `|`, key from value on `=`; a leading `h=` row is a header, and a
value carries no `;`, `|`, `=` or `~`.

A cell whose whole value is an `http(s)://` URL, or an absolute path (`/Users/...`), is drawn as a
reference the reader can open — the link opens, the path reveals in the file manager — so give those
cells the whole value and nothing else.

`n=` is the widget's only hover note, and it is opt-in: add it when the widget cannot print something the
reader needs, and leave it out otherwise — a note that repeats the widget is worse than none.

A diagram is a ```mermaid fence instead, first line the type: flowchart, sequence, state, class, er,
gantt, pie, journey, gitgraph, timeline, quadrant, sankey, treemap, radar, xychart, mindmap, block.

Kinds, by payload:
"""

#: The kind block as data: one entry per line, `(lead, items)`.  *lead* opens the line — the payload its
#: kinds share, empty for a run of kinds that needs no label — and each item is `(kind, note)`, the note
#: being whatever trails the kind: its payload's own syntax, or the separator that starts a new clause.
#: A kind gated off takes its note with it, and a line with nothing left disappears, because a lead with
#: no kinds under it is a heading for something the model cannot ask for.
KIND_LINES = (
    ("label=value —", (
        ("kpi", ""), ("facts", ""), ("records", ""), ("progress", ""), ("heatmap", ""),
        ("settings", " (`on|off`)"), ("files", " (`path=meta`)"), ("words", ""),
        ("nutrition", " (`value of target`)"), ("metrics", "; adds `=delta`"),
    )),
    ("a numeric run —", (
        ("bars", ""), ("line", ""), ("donut", ""), ("series", ""), ("sparkline", " (bare numbers)"),
        ("ranges", " (`lo..hi`)"), ("scatter", " (`x=y`)"), ("candlestick", " (`o:h:l:c`)"),
        ("waterfall", " (`+n`)"),
    )),
    ("a `h=` header row —", (
        ("table", ""), ("grid", ""), ("array", ""), ("parts", ""), ("recipe", " (`!` warns)"),
        ("forms", ""), ("bracket", " (`w>l,…`)"), ("wireframe", " (`lbl=btn:2,text:3`)"),
    )),
    ("", (
        ("checklist", " (`done|doing|todo|blocked`)"), ("steps", ""), ("outline", " (`1=Title;1.1=Sub`)"),
        ("gloss", ""), ("matches", ""), ("groups", ""),
    )),
    ("", (
        ("timeline", ""), ("route", ""), ("events", " (`when=label=detail`)"), ("funnel", ""),
        ("stages", ""), ("pairs", ""),
    )),
    ("", (("changes", " (`path=+a=-d`)"),)),
)

#: Kind block lines that are prose rather than a run of kinds: no rule emits `section` or `board`, so no
#: group can gate them, and the guide is the only place the model can learn either exists.
KIND_LINES_LITERAL = (
    "- `section` (`t=`, `l=1|2`) heads a section; `board` holds several widgets in one directive (entries\n"
    "  split on `~`)",
)

#: What deserves which drawing, as data, for the same reason: `(phrase, kinds)` per clause, the clauses
#: grouped into the bullets they print in.  A clause whose kinds are all gated off drops out, and a bullet
#: left with no clauses drops out with it.
KIND_CHOICES = (
    (("one number per labelled row", ("bars",)), ("a part of a whole", ("donut",)),
     ("over time", ("line",))),
    (("a few headline figures", ("metrics",)), ("a fact sheet, a spec, a name→value list", ("facts",))),
    (("a matrix, rows sharing several columns", ("table",)), ("a ranking", ("bars",)),
     ("a procedure", ("steps",))),
    (("a done/todo run", ("checklist",)), ("dates", ("timeline",)), ("a nested list", ("outline",)),
     ("a trip", ("route",))),
    (("a path with a count", ("files",)), ("parts and quantities", ("parts",)), ("flags", ("settings",)),
     ("a board, a device, an interface", ("wireframe",))),
    (("a language", ("words", "gloss", "forms")), ("a dish", ("recipe", "nutrition")),
     ("fixtures", ("matches",))),
)

GUIDE_CHOICES_LEAD = """

**What deserves a drawing, and which one.** Numbers to compare, a trend, a share, a process, a schedule, a
structure, a history, a list — each wants a drawing, not a paragraph. Choose by the SHAPE of what the answer
already wrote:
"""

GUIDE_CLOSE = """

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


def _kind_item(kind: str, note: str) -> str:
    """One kind as the guide prints it: ``\`kind\``` plus its note.

    A note beginning `"; "` opens a clause of its own rather than trailing the kind, so a payload that
    adds to the run before it (`metrics` adds `=delta`) reads as written.
    """
    if note.startswith("; "):
        return "; `%s`%s" % (kind, note[1:])
    return "`%s`%s" % (kind, note)


def _compose_guide(gated: frozenset = frozenset()) -> str:
    """The whole guide with every kind in *gated* left out — one shape for the text and the data.

    *gated* holds the kinds whose every rule group is off.  A kind carries its own note, so dropping the
    kind drops the note with it; a line or a clause left with nothing goes as well.
    """
    lines = [
        "- " + (lead + " " if lead else "") + " ".join(
            _kind_item(kind, note) for kind, note in items if kind not in gated
        ).replace(" ;", ";")
        for lead, items in KIND_LINES
        if any(kind not in gated for kind, _ in items)
    ]
    bullets = [
        "- " + "; ".join(
            "%s → %s" % (phrase, " ".join("`%s`" % k for k in kinds if k not in gated))
            for phrase, kinds in clause
            if any(k not in gated for k in kinds)
        ) + "."
        for clause in KIND_CHOICES
        if any(any(k not in gated for k in kinds) for _, kinds in clause)
    ]
    return (
        GUIDE_HEAD
        + "\n".join(lines + list(KIND_LINES_LITERAL))
        + GUIDE_CHOICES_LEAD
        + "\n".join(bullets)
        + GUIDE_CLOSE
    )


#: The guide with every kind named: what a configuration with every group on receives, and the text
#: `tests/test_format_guide.py` reads its kind list out of.
FORMAT_GUIDE = _compose_guide()


def _split_groups(groups: Any) -> set:
    """The enabled groups, from the comma-separated setting or any iterable of names."""
    if isinstance(groups, str):
        parts = groups.split(",")
    else:
        parts = list(groups or [])
    return {str(part).strip() for part in parts if str(part).strip()}


def _gated_kinds(groups: Any, rules) -> frozenset:
    """The kinds the *groups* configuration cannot produce — every group that emits them is off.

    A kind no rule emits (`line`, `table`, the named subjects) is never gated: it arrives through an
    explicit `::viz`, which no group governs.
    """
    enabled = _split_groups(groups)
    owners: dict[str, set] = {}
    for rule in rules or []:
        kind, group = rule.get("kind"), rule.get("group")
        if kind and group:
            owners.setdefault(str(kind), set()).add(str(group))
    return frozenset(kind for kind, groups_of in owners.items() if not (groups_of & enabled))


def format_guide_section(
    enabled: Any, groups: Any = DEFAULT_RULE_GROUPS, rules=None
) -> (str) | None:
    """The format-guide prompt section text, or ``None`` when the setting is off.

    ``None`` is what makes an off setting measurably free: with no text there is no section to register,
    so the rendered prompt is byte-identical to one from a plugin that has no guide at all.  The text
    itself is built from *groups*: a group that is off takes its kinds out of the prompt entirely.
    """
    if not _enabled(enabled):
        return None
    if rules is None:
        try:
            rules = load_rules(RULES_PATH)
        except Exception:
            rules = []
    gated = _gated_kinds(groups, rules)
    return FORMAT_GUIDE if not gated else _compose_guide(gated)


def format_guide_prompt(
    base_prompt: str, enabled: Any, groups: Any = DEFAULT_RULE_GROUPS, rules=None
) -> str:
    """*base_prompt* with the guide appended when it is on — byte-identical when it is off.

    Hermes core owns the real append (it renders the registered section once per session); this is the
    same composition, spelled out so "identical when off" and "exactly one copy when on" are checkable
    without a live session.
    """
    guide = format_guide_section(enabled, groups, rules)
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
    setting off nothing at all reaches the prompt — the guide's whole cost is opt-in.  Its kind block is
    built from the enabled rule groups, so a group that is off is absent from the prompt, not annotated.
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

    guide = format_guide_section(config["format_guide"], config["rule_groups"], rules)
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
