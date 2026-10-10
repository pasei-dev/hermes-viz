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
    from .python.shape import drawing_count, shape
    from .python.viz_dsl import (
        MERMAID_HEADERS,
        board_entry,
        demote_directives,
        mermaid_fence,
        to_board_directive,
    )
except ImportError:  # loaded as a plain top-level module (tests, scripts)
    from python.derive import derive, load_rules, structure
    from python.shape import drawing_count, shape
    from python.viz_dsl import (
        MERMAID_HEADERS,
        board_entry,
        demote_directives,
        mermaid_fence,
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
    "guide_kinds",
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
#: The declared ceiling for the guide's section.  It must NOT exceed what the host accepts:
#: `MAX_SYSTEM_PROMPT_SECTION_CHARS` (`hermes_cli/plugins_dispatch.py`) is 4000, and
#: `register_system_prompt_section` RAISES above it.  A declared 4800 therefore failed validation, the
#: bare `except` around the call in `register()` swallowed it, and the guide silently never reached the
#: prompt — a plugin that looks installed and asks the model for nothing.  Keep this at or below the
#: host's limit; `tests/test_format_guide.py` enforces the host's ceiling on registration.
FORMAT_GUIDE_MAX_CHARS = 4000

#: The opt-in format guide: the model's only channel to the drawing core, and the plugin's whole claim on
#: the answer's shape — the structuring mandate, scaled to what this app can draw.
#:
#: **The kind block is composed from the rule table, never written out.**  A kind rides on the groups whose
#: rules can produce it, so a group turned off takes its kinds out of the prompt altogether: a disabled
#: feature leaves the prompt, it is not annotated in it.  The mandate above the block is the same for every
#: configuration — headings, lists and tables are the app's markdown, not plugin kinds.
#:
#: It is a prompt on every request: its cost is stated in `README.md`, `dashboard/settings.json` and the
#: badge in `dashboard/dist/index.js`, and all three move in the same commit as the text.
GUIDE_HEAD = """\
**Answer format.** The shape carries meaning: structure it, and show what can be shown.

- Sections are `##`, and the answer opens with one; `###` divides a section, `#` titles a whole document,
  never a reply. Never skip a level.
- `**Bold**` only the key term of a sentence.
- Steps are a list, one per line; comparisons a table.
- No decorative separator (`---`, `***`); headings and blank lines are enough.
- One drawing per idea, in its own section; an explanation carries several. Never twice, and only the answer's own names and numbers: never invented filler.
- A note, tip or warning is a callout (`> [!NOTE]`), never a quote.
- Math is `$…$` inline, `$$…$$` on its own line.

**Say less.** The first line is the answer — the fact, the number, the command, the decision. No
announcement, never the question again, no closing offer, no justification. One
idea per line; a widget, a table or a list replaces the prose beside it.
The prose beside a widget carries the reason and the caveat, never its numbers again.

**Widgets.** A `::viz{...}` directive alone in its own paragraph — one line, <=1200 chars, `k=` kind, `d=`
data, `t=` title, `u=` unit, `n=` a hover note, no braces in the attrs:

    ::viz{k="table" d="h=Board|Runs;Alpha|42;Delta|17"}

In `d`: rows on `;`, cells on `|`, key from value on `=`, a leading `h=` row is a header; a value
carries no `;`, `|`, `=` or `~`. A value may be a call on the payload's own rows — `sum(A, B)`,
`share(A, B)`, `diff(A, B)` — so a total is computed, never your own arithmetic. A cell that is wholly a URL or an
absolute path is a reference the reader can open.
`n=` only when the widget cannot print what the reader needs.

A diagram is a ```mermaid fence instead, first line the type: flowchart, sequence, state, class, er,
gantt, pie, journey, gitgraph, timeline, quadrant, sankey, treemap, radar, xychart, mindmap, block.

Kinds, by payload:
"""

#: The kind block as data: `(lead, items)` per line — *lead* is the payload its kinds share (empty for a
#: run that needs no label), each item `(kind, note)` with the payload syntax that trails it.  A gated kind
#: takes its note with it; a line left with nothing disappears.
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
        ("forms", ""), ("bracket", " (`w>l,…`)"), ("wireframe", " (`lbl=btn:2`)"),
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
    ("", (
        ("tags", " (chips)"), ("calendar", " (`date=label`)"), ("area", " (`line`, filled)"),
        ("tabs", " (`Label:kind:payload` panels)"), ("followup", " (`label=prompt`, sends on click)"),
    )),
)

#: Lines that are prose, not a run of kinds: no rule emits `section` or `board`, so no group gates them.
KIND_LINES_LITERAL = (
    "- `section` (`t=`, `l=1|2`) heads a section; `board` packs widgets, entries split on `~`",
)

#: The interaction templates the guide names, as data: `(template, the kinds it can operate)`.  The
#: `x=` line names each template and the shapes it belongs to (SPEC rounds 11 and 13) — but a template
#: whose kinds are all gated drops out, like a kind, so a disabled feature is absent from the prompt.
#: `pick` and `step` share one row of value kinds, so they share one clause.
KIND_TEMPLATES = (
    ("`toggle`", ("steps", "checklist", "outline")),
    ("`pick`/`step`", ("facts", "kpi", "settings", "files", "metrics", "records")),
)

#: Which shape deserves which drawing, as data: `(phrase, kinds)` per clause, clauses grouped into their
#: bullets.  A gated clause drops out, and a bullet with no clauses left goes with it.
KIND_CHOICES = (
    (("one number per labelled row", ("bars",)), ("a part of a whole", ("donut",)),
     ("over time", ("line",))),
    (("a few headline figures", ("metrics",)), ("a fact sheet", ("facts",))),
    (("a matrix", ("table",)), ("a ranking", ("bars",)), ("a procedure", ("steps",))),
    (("a done/todo run", ("checklist",)), ("dates", ("timeline",)), ("a nested list", ("outline",)),
     ("a trip", ("route",))),
    (("a path with a count", ("files",)), ("parts", ("parts",)), ("flags", ("settings",)),
     ("a device", ("wireframe",))),
    (("a language", ("words", "gloss", "forms")), ("a dish", ("recipe", "nutrition")),
     ("fixtures", ("matches",))),
)

GUIDE_CHOICES_LEAD = """

**What deserves a drawing, and which one.** Choose by the SHAPE of what the answer wrote — a drawing
beats a paragraph:
"""

#: The close, and the one figure in the guide taken from a setting rather than the rule table: the model
#: is told the same budget the post-pass enforces, so an answer over the cap is the model's own overflow
#: instead of a drop it could not see coming.  A budget of ``None`` — no cap — drops the clause.
def _guide_close(max_widgets: Any = DEFAULT_MAX_WIDGETS) -> str:
    budget = ""
    if isinstance(max_widgets, int) and max_widgets > 0:
        budget = "; at most %d drawings" % max_widgets
    return (
        "\n\n**Before you answer.** A question about numbers gets its chart or its tiles in the FIRST "
        "response — a table alone is not an answer to it. Where a drawing fits, a text-only answer is a "
        "worse one: draw it in this reply, unprompted."
        "\n\n**Before you send,** walk it once: each drawing "
        "follows the sentence that names it, and nothing is announced and then absent; no number is "
        "printed twice%s.\n" % budget
    )


#: The close at the shipped budget, for the reference text and any reader of the constant.
GUIDE_CLOSE = _guide_close()


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
    """One kind as the guide prints it.  A note starting `"; "` opens a clause of its own, so a payload
    that adds to the run before it (`metrics` adds `=delta`) reads as written."""
    if note.startswith("; "):
        return "; `%s`%s" % (kind, note[1:])
    return "`%s`%s" % (kind, note)


def _template_line(gated: frozenset) -> (str) | None:
    """The `x=` line: each template with the shapes it belongs to, its gated kinds left out.  A template
    whose kinds are all gated drops out, so a template the prompt does not name is one nobody writes."""
    parts = []
    for name, kinds in KIND_TEMPLATES:
        live = [kind for kind in kinds if kind not in gated]
        if live:
            parts.append("%s (%s)" % (name, "/".join("`%s`" % kind for kind in live)))
    return "- `x=` operates it: " + ", ".join(parts) if parts else None


def _compose_guide(
    gated: frozenset = frozenset(), max_widgets: Any = DEFAULT_MAX_WIDGETS
) -> str:
    """The guide with every kind in *gated* left out: the kinds whose every rule group is off."""
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
    literal: list[str] = list(KIND_LINES_LITERAL)
    templates = _template_line(gated)
    if templates:
        literal.append(templates)
    return (
        GUIDE_HEAD
        + "\n".join(lines + literal)
        + GUIDE_CHOICES_LEAD
        + "\n".join(bullets)
        + _guide_close(max_widgets)
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
    """The kinds every group that emits them is off for.  A kind no rule emits (`line`, `table`, the named
    subjects) is never gated: it arrives through an explicit `::viz`, which no group governs."""
    enabled = _split_groups(groups)
    owners: dict[str, set] = {}
    for rule in rules or []:
        kind, group = rule.get("kind"), rule.get("group")
        if kind and group:
            owners.setdefault(str(kind), set()).add(str(group))
    return frozenset(kind for kind, groups_of in owners.items() if not (groups_of & enabled))


def format_guide_section(
    enabled: Any,
    groups: Any = DEFAULT_RULE_GROUPS,
    rules=None,
    max_widgets: Any = DEFAULT_MAX_WIDGETS,
) -> (str) | None:
    """The format-guide prompt section text for *groups*, or ``None`` when the setting is off.

    ``None`` is what makes an off setting measurably free: with no text there is no section to register, so
    the rendered prompt is byte-identical to one from a plugin that has no guide at all.
    """
    if not _enabled(enabled):
        return None
    gated = _gated_kinds(groups, _loaded_rules(rules))
    if not gated and max_widgets == DEFAULT_MAX_WIDGETS:
        return FORMAT_GUIDE
    return _compose_guide(gated, max_widgets)


def guide_kinds(groups: Any = DEFAULT_RULE_GROUPS, rules=None) -> list[str]:
    """The kinds the guide names for *groups*, in the order it names them — the prompt's own list."""
    gated = _gated_kinds(groups, _loaded_rules(rules))
    items = [item for _lead, line in KIND_LINES for item in line]
    # the literal line names these two whatever the groups are: no rule emits them
    items += [("section", ""), ("board", "")]
    items += [(kind, "") for clause in KIND_CHOICES for _phrase, kinds in clause for kind in kinds]
    named: list[str] = []
    for kind, _note in items:
        if kind not in named and (kind in ("section", "board") or kind not in gated):
            named.append(kind)
    return named


def _loaded_rules(rules=None):
    """The rule table, read from `rules.yaml` when the caller has not already loaded it."""
    if rules is not None:
        return rules
    try:
        return load_rules(RULES_PATH)
    except Exception:
        return []


def format_guide_prompt(
    base_prompt: str,
    enabled: Any,
    groups: Any = DEFAULT_RULE_GROUPS,
    rules=None,
    max_widgets: Any = DEFAULT_MAX_WIDGETS,
) -> str:
    """*base_prompt* with the guide appended when it is on — byte-identical when it is off.

    Hermes core owns the real append (it renders the registered section once per session); this is the
    same composition, spelled out so "identical when off" and "exactly one copy when on" are checkable
    without a live session.
    """
    guide = format_guide_section(enabled, groups, rules, max_widgets)
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

    The structure layer runs first: an answer that already behaves like a section gets its level's marker
    (``## `` for a section, ``### `` inside one) in front of the anchor.  From there each derived widget
    *replaces* the lines it was derived from — in place, so a section reads heading, widget, next
    heading, and the answer is never longer than the prose it already had.  A widget whose source carried
    more than the widget draws is dropped and the prose stays; a Mermaid *diagram* (a spec with a body)
    replaces its source with its own fence.  An
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
    config: (Callable[[], dict[str, Any]]) | None = None,
) -> Callable[..., (str) | None]:
    """The hook callback.  *config*, when given, is read again on every call, so a group switched in the
    settings page takes effect on the next answer instead of at the next restart."""

    def settings() -> dict[str, Any]:
        if config is None:
            return {"rule_groups": groups, "max_widgets": max_widgets, "palette": palette}
        return config()

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
        # Only the surface that parses the directive may be given one — see DRAWING_PLATFORMS.  The
        # other half of that rule: a directive reaching a surface that cannot draw is **demoted** to
        # the markdown it would have drawn, so the reader is owed the data and never the grammar.
        # No directive found means the answer is returned untouched, so the no-op case stays
        # byte-identical.
        if not _draws_here(platform):
            demoted = demote_directives(response_text)
            return None if demoted == response_text else demoted
        # The desktop's own pass: a directive the app and the core would both draw is left **exactly
        # as the model wrote it**, and one they would refuse — a group past the cap, a brace in the
        # attrs, a kind the core does not draw, a computed cell its own rows cannot compute — is
        # demoted instead of reaching the reader as grammar or as an empty frame.
        demoted = demote_directives(response_text, only_invalid=True)
        live = settings()
        max_widgets = live.get("max_widgets")
        # The answering-format post-pass: the model's own drawings are repaired — a repeat dropped,
        # an extra past `max_widgets` dropped — and never invented.  It runs on demoted text too, so
        # a valid directive sitting beside a refused one is still bounded.
        authored = shape(demoted if demoted != response_text else response_text, max_widgets)
        if demoted != response_text:
            # A demotion already means the answer drew its own data: the derivation stands down.
            return None if authored == response_text else authored
        # The cap counts what the answer draws, derived and authored alike: the drawings the answer
        # already carries spend from the one budget, so the deriver is handed the remainder.  And
        # either way the answer has drawn its own data, so the derivation stands down when a
        # directive is present: one hand on the numbers, never two — `transform` returns None where
        # a directive is present, which is what makes a second pass a no-op.
        remaining = max_widgets
        if max_widgets is not None:
            try:
                remaining = max(0, int(max_widgets) - drawing_count(authored))
            except (TypeError, ValueError):
                remaining = None
        derived = transform(
            authored,
            rules,
            live.get("rule_groups"),
            remaining,
            live.get("palette") or DEFAULT_PALETTE,
        )
        finished = authored if derived is None else derived
        return None if finished == response_text else finished

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
    ctx.register_hook("transform_llm_output", make_hook(rules, config=lambda: _read_config(ctx)))

    register_section = getattr(ctx, "register_system_prompt_section", None)
    if _enabled(config["format_guide"]) and callable(register_section):
        def guide_for_session(session_info=None) -> str:
            # Same two gates as the hook: a child's answer goes to the orchestrator, and only a surface
            # that parses a directive should be asked to write one.  The settings are read again here, so
            # the groups a session is handed are the groups as they stand when it starts.
            if _is_child_session(session_info):
                return ""
            platform = session_info.get("platform") if isinstance(session_info, Mapping) else ""
            if not _draws_here(platform):
                return ""
            live = _read_config(ctx)
            return (
                format_guide_section(
                    live["format_guide"], live["rule_groups"], rules, live["max_widgets"]
                )
                or ""
            )

        try:
            register_section(FORMAT_GUIDE_SECTION_ID, guide_for_session, max_chars=FORMAT_GUIDE_MAX_CHARS)
        except Exception:
            pass  # an older Hermes without system-prompt sections still gets the transform hook
