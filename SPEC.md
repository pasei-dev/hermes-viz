# SPEC — the contract both halves build against

Read-only for both halves. Change it deliberately, never in passing: it is the only thing keeping the
agent half and the desktop half from drifting apart.

## The directive

`::viz{...}` alone on its own paragraph. The app's parser (`lib/transcript-directives.ts`) allows: one
line, the whole paragraph, <=1200 chars, attrs as `key="value"`, and **no `{` or `}` anywhere inside the
attrs**. Nothing else in the paragraph, ever.

**The directive belongs to one surface.** Only the desktop app parses it; the CLI, the TUI, a chat
gateway, the dashboard and an API client render it as its own literal text. So the agent half emits a
directive — and the guide asks the model for one — **only when the platform is `desktop`**, and treats an
unknown platform as one that cannot draw. A widget nobody can see is a smaller failure than a line of raw
grammar in the transcript.

**And a directive already written reaches a surface that cannot draw it as DATA.** A model writes one
without being asked: a session resumed from the desktop app carries directives in its own history, and a
model imitates what it can see. On a surface that cannot draw, that is a line of raw grammar — so the
hook **demotes** it: the payload becomes the markdown it would have drawn, its computed cells resolved,
and the reader keeps every value the desktop reader is shown (round 12). It returns the answer untouched
when it finds no directive, and a directive that owned its paragraph has its block take the line's place;
one written mid-sentence leaves the sentence, with its rows inline. A fenced code block is left alone,
because a reader being *shown* the grammar is not a reader being shown a widget, and only `::viz` is
touched — `::preview{...}` and the app's other directives belong to the app.

| attr | required | meaning |
|---|---|---|
| `k` | yes | the kind, `[a-z][a-z0-9-]*` |
| `d` | yes | the data, in the encoding below; a value may be a **computed cell** (round 12) |
| `t` | no | title |
| `u` | no | unit suffix for the values |
| `p` | no | palette for a Mermaid kind: `dark` \| `light` \| `mermaid` (default: the plugin setting) |
| `x` | no | the interaction template the mount may perform: `toggle` \| `pick` (round 11) \| `step` (round 13). Absent, the widget is static |
| `n` | no | one hover note for the whole widget (round 9) |

## The data encoding

Brace-free, newline-free, one attribute value. **Rows split on `;`, cells on `|`, key from value on `=`**,
and a row beginning `h=` is a header. `~` separates the widget entries inside a `board` (below). Values
must not contain `;`, `|`, `=`, `~` or `\` — the emitter strips them, and that stripping is the emitter's
responsibility, not the renderer's. A value that is **exactly** a call on the payload's own rows —
`sum(A, B)`, `share(A, B)`, `diff(A, B)` — is a **computed cell**: the halves compute it, so it costs the
encoding nothing (round 12).

```
::viz{k="bars" d="Firmware=42;DSP=28;Web=18" u="%"}
::viz{k="kpi" d="Builds=128=+12;Fails=3=-1"}
::viz{k="table" d="h=Board|Runs;Alpha|42;Delta|17"}
::viz{k="steps" d="Read the archive;Patch the entry;Flash the board"}
::viz{k="metrics" d="Prose=43;Bullets=42.2;Read line by line=sum(Prose, Bullets)" u="%"}
```

## Kinds

**Mermaid kinds — the plugin emits a fence, the app draws it.** All 20+ arrive for free this way:

`flowchart` `sequence` `state` `class` `er` `gantt` `pie` `journey` `gitgraph` `timeline` `quadrant`
`sankey` `treemap` `radar` `xychart` `mindmap` `block`

A Mermaid emission is a ` ```mermaid ` fence whose **first line** is the palette header when the setting
is `dark` or `light`, and absent when the setting is `mermaid`:

```
%%{init:{'theme':'base','themeVariables':{'primaryColor':…,'primaryTextColor':…}}}%%
```

Verified: this header overrides the app's own `initialize({theme:'dark'})` — node fill `#1f2020` becomes
ours, stroke `#ccc` becomes ours, and `background:'transparent'` adds no background rect. CSS cannot do
this: the app renders the SVG into an `<img>`, an isolated document.

**Our kinds — the plugin draws them.** Mermaid cannot express these:

`kpi` `bars` `line` `donut` `steps` `table` `progress` `sparkline` `board`

**`board` is the multi-widget form, and the one the derivation emits.** `d` carries N entries separated by
`~`, each `kind:payload` with the payload in the encoding above. It lays them out in
`repeat(auto-fit, minmax(24rem, 1fr))` — measured, not assumed: **3 columns at a 1400px pane, 2 at 900px,
1 at 500px**, three entries, no horizontal overflow at any of the three. One bad entry degrades to prose
for that entry alone; the rest of the board still renders.

Why it exists: a directive is a leaf and cannot see its siblings, so several `::viz` paragraphs stack
instead of sitting side by side. One board is how a wide pane shows more widgets.

A board entry carries `kind:payload` only — no title and no unit slot. A single-widget directive keeps
both. That is deliberate: the derived path does not need them, the explicit path does.

## The palette — multicolour, and where it comes from

The **surface** is themed by the app's tokens. **Data** is coloured by the plugin's own palette: six
custom properties declared once, at the top of the CSS, as `--hv-1` … `--hv-6`. Categories take a hue in
first-seen order, deterministically — the same payload always paints the same colours.

- `--hv-1` **is** `--dt-primary`, so a one-series widget still reads as the theme's accent.
- The other five sit beside it on a near-black surface and stay separable at ≥4.5:1 against it.
- **Colour never carries meaning alone.** Every coloured element keeps its label or its value; the palette
  ranks and separates, it does not encode.

Test rule: the surface may use only app tokens, and the palette is the six `--hv-*` properties declared in
that one block and nowhere else. A literal colour anywhere outside it is still a bug.

## Width, padding and measure

A widget fills its grid cell and reflows — but the **content inside it** is capped by `--hv-measure`
(42rem), so a two-value sparkline cannot become a 580:1 slab on a 1400px pane, and a table's columns are
sized by content instead of stretched to fill. This replaces the earlier "no `max-width` anywhere" rule:
no fixed pixel size, no clamp on the widget, a measure on the content.

Inside the app that cap is the **standalone fallback**: the body style's measure sits on `.aui-md`, one
column wide, and every widget is mounted inside it, so a drawing is exactly as wide as the prose it
replaces. The two numbers never have to agree, and a board reflows *within* the column.

**A measure is centred, never left flush.** Every rule that caps content carries `margin-inline: auto`
beside its `max-width` — `.hv-grid`, `.hv-title`, `.hv-caption`, `.hv-section` here, and the answer's own
block in the body style. A capped block pinned left is the asymmetry the reader actually sees: text
stopping short of the right edge with nothing on the other side. Centred, the pane's leftover is split
evenly, and a pane narrower than the measure has no leftover at all — the app's own 24px gutter is then
the margin, which is the dynamic behaviour asked for.

**The body's measure goes on the block, not on each element** (round 10). A `ch` length resolves against
the element's *own* font size, so `h1…h6` capped at their larger type measured wider than the paragraph
beside them: measured at a 1600px pane, `<p>` came out 567px and `<h2>` 851px. One `max-width` on
`.aui-md` holds the prose, the headings, the lists, the code and the widgets in the same column. Measured
on a faithful mock (app tokens, the real core CSS, a real widget, mounted as the app mounts it): block,
`<p>`, `<h2>`, `<ul>` and the widget's mount all sit 515px from each edge at a 1600px pane, 215px at
1000px, and 24px at 520px — one column, equal on both sides, shrinking with the pane.

Padding is one value on all four sides and it follows the **widget's own width** — `--hv-pad: min(1rem,
2.4%)` — so a narrow pane gets a smaller gutter and a wide one never grows a slab of margin. A media query
would read the window instead, and the pane is what the reader actually widened. (Replaced the earlier
14px/16px base with a 20px/24px step at 48rem: two values, and the wrong axis.) Nothing may touch the
widget's own edge.

## Kinds, round 2 — the answer-shaped cards

Gap analysis against a 43-kind widget set. Everything structural it has that
Mermaid expresses — `flowchart` `sequence` `state` `class` `er` `gantt` `pie` `journey` `gitgraph`
`timeline` `quadrant` `sankey` `treemap` `radar` `xychart` `mindmap` — **already arrives** through our
Mermaid fence path. What Mermaid cannot express, and we lack, is the answer-shaped card:

| kind | payload | what it draws |
|---|---|---|
| `checklist` | `label=state`, state ∈ `done\|doing\|todo\|blocked` | rows with a state glyph; done struck through |
| `changes` | `path=+adds=-dels` | a diff summary: one row per file with its own name, type glyph and `+a`/`-b`, and a footer with the count and the totals — **shipped off**, see below |
| `outline` | `1=Title;1.1=Sub` | a contents list, depth from the dotted prefix |
| `facts` | `label=value` | a definition card: muted label above a strong value |
| `files` | `path=meta` | a file listing with a kind glyph and a muted meta column |
| `parts` | `h=Ref\|Part\|Qty;U1\|MCU-1\|1` | a bill of materials, quantities right-aligned |
| `settings` | `label=on\|off` | toggle rows, state as a pill |
| `timeline` | `when=label=detail` | a vertical timeline on a rail |
| `ranges` | `label=lo..hi` | a span chart on one shared scale |
| `metrics` | `label=value=delta` | a metric grid with captions |
| `array` | `a\|b\|c` | a bordered cell grid — a matrix, not a table |
| `heatmap` | `label=value` | cells on a 0…max ramp |

Deliberate backlog, not this round: `bracket` `words` `gloss` `forms` `recipe` `route` `nutrition`
`matches` `wireframe` `candlestick`.

## The structure layer — headings and sections

New kind `section`: `t` is the heading, `d` an optional lead line. It draws a header band — heading type,
an optional palette key beside it, and no rule of any kind.

**The derived path never emits a band.** It used to: each section rode as a `section:` entry inside its
board while the same words also stood on the page as a heading, so `## Builds` — or an inserted
`## Builds` — was drawn twice. The rule is now one line: **a heading the answer renders is never also
drawn as a widget.** The layer inserts the level's own marker — `## ` for a section, `### ` for a division
inside one — where the answer behaves like a heading but is not one, and that marker *is* the section's
heading; `section` remains for an explicit `::viz`, where the model asked for a band itself.

**One heading vocabulary, prompt and layer.** The prompt tells the model a section is `##` and a division
inside one is `###`; the marker the layer writes is the same two, so a section the layer created and a
section the model wrote are the same height on the page. `#` is the answer's own title — the layer never
writes one and never invents a parent for a `###` the answer skipped.

The derivation may **insert** a heading where the answer already behaves like one (an all-bold line, or a
run of parallel items) and may group the widgets under it into one board. It **never** rewords, deletes or
reorders the model's own words: structure is added around them, never substituted for them.

## Section levels, and one board per section

`section` gains `l=1|2` (default 1). Level 1 is the answer's own division; level 2 is a division *within*
one — one step down in type, a muted rule, no key. A board may mix them, and **the hierarchy must be
legible from type size alone**, with no colour needed to read it.

**One board per section.** Where the derivation inserts a heading it emits that section's widgets under
it in their own board, so a reader gets heading, then its data, then the next heading. Sections never
collect at the top of a board ahead of the widgets they head. A section with no widget gets its heading
and nothing else — never a band of its own.

**How the level travels.** In the derived path the level is the marker the layer inserts: a section is a
`##`, a division within one is a `###` under the `##` that opened it. For an explicit directive it rides as
the `l` attr (`l="2"`), or inside a board as a cell of the entry payload — `section:Board runs;l=2` — where
the first non-`l=` cell is the heading and level 1 omits it entirely. This paragraph exists because round 3
left it open, and the two lanes duly chose differently (`section:2:Heading` against `;l=2`): an interface
with two valid readings is the SPEC's error, and it fails silently in the app while both suites stay green.

## Kinds, round 3

| kind | payload | what it draws |
|---|---|---|
| `wireframe` | `label=block:count,block:count` | a UI mock: rows of proportional labelled blocks |
| `candlestick` | `when=open:high:low:close` | OHLC candles on one shared scale, close as a line |

- `wireframe` — blocks ∈ `btn` `field` `text` `img` `item` `card` `chart` `circle`; the count repeats the
  block. `d="Toolbar=btn:3,field:1;Sidebar=item:6"`. Blocks are proportional, never real pixels, and the
  row's label is always visible: a mock that needs a legend to read is not a mock.
- `candlestick` — `d="Mon=12:18:9:16;Tue=16:21:14:20"`, one shared price scale with a hi/lo axis and the
  close drawn as a line. A doji (`open == close`) must still draw a visible body.

## Semantics: a value with something to measure it against

`bars` and `metrics` gain the `of` form. A row value may read `<value> of <target>` — `1850 of 2200` —
drawn with the target as the track end and the share named. This is the one thing our bars genuinely lacked:
a number with a reference, rather than a number alone. `u=<unit>` already names what the amounts are.

## No decorative separators

A section band carries **no rule of its own**, and neither does a widget caption: the caption is set
apart by case, weight and colour, which is enough. Hierarchy is carried by type size and weight alone, which is
already tested with colour switched off. A hairline under every band is a decorative separator, and
separators are noise: the answer is structured without being ruled off. Level 1 may keep its muted key dot;
nothing else, and never a full-width line.

## Board layout: no orphan entry

A board chooses its column count from its **entry count** — 1, 2 or 3 — so the last row is never a single
orphan where a smaller column count would have balanced it. Four entries at three columns leave the fourth
alone, which reads as a mistake; two columns of two read as a composition. The board still never clamps and
still reflows to the pane: only the *count* is chosen, never a width.

## Level 2, from the answer as it stands

The derivation promotes to level 2 only where the answer **already** holds a sub-division: a `###` heading
nested under a `##` one, or a caption immediately followed by a list or table while a level-1 heading is
already open. It never invents a level, and a level-2 band is emitted only when its parent level-1 band has
already been emitted in the same answer — a lone level 2 must be impossible. (Round 3's one-board-per-band
rule stands: a band and its own widgets share a board, which means a child band cannot share its parent's.)

## Mermaid kinds the derivation may emit

The transform may emit a Mermaid fence where the text **already states the shape**, using kinds the app
renders: `stateDiagram-v2` for named states with transitions, `sequenceDiagram` for an exchange of messages,
`gantt` for a schedule with dates, `pie` for shares of one whole, `timeline` for dated events. The fence
carries only what the text says — a kind whose body would have to be invented is not emitted at all.

## Kinds, round 5 — the subject kinds

| kind | payload | what it draws |
|---|---|---|
| `words` | `word=[say]=meaning=example` | vocabulary rows: word, pronunciation, meaning, example |
| `recipe` | `h=Ingredient\|amount\|note;…` | ingredients, then steps; a step may be flagged a warning |
| `route` | `stop=time=detail` | an itinerary on a rail |
| `nutrition` | `label=value of target` | macros against their targets, using the `of` form |
| `matches` | `when=home away=tournament` | fixtures and results |

- `words` — `d="der Hund=[deːɐ hʊnt]=the dog=Der Hund bellt."`; a row without an `=` group is a heading.
- `recipe` — like `parts`: `h=` names the columns; a row whose first cell starts with `!` is a warning.
- `route` — `d="09:40=Depot 1=Check in;11:10=Gate B=Board"`, stops on one rail with their times.
- `nutrition` — `d="Calories=1850 of 2200;Protein=132 g of 150"`, each macro against its target.
- `matches` — `d="18:00=Arsenal 2-1 Chelsea=League Cup;20:45=Brentford 0-0 Leeds=League Cup"`.

## Kinds, round 6 — the last three

| kind | payload | what it draws |
|---|---|---|
| `bracket` | `round=winner>loser,winner>loser` | a knockout bracket: rounds as columns, winners carried forward |
| `gloss` | `source=gloss=note` | interlinear glossing: a source line with its word-by-word gloss under it |
| `forms` | `h=person\|singular\|plural;…` | a paradigm grid: a conjugation or declension |

- `bracket` — `d="R16=Arsenal>Chelsea,Brentford>Leeds;QF=Arsenal>Brentford"`. A round is one row; the winner
  advances and the next round must name it, so a bracket that contradicts itself is visible rather than
  silently drawn. Cells part on `,`, a pairing on `>`.
- `gloss` — `d="der Hund bellt=the dog barks=PRS.3SG"`; the source line sits above its gloss, aligned word
  by word where the counts allow, and a row whose gloss has a different word count is shown unaligned rather
  than squeezed into a false alignment.
- `forms` — like `parts`: `h=person|singular|plural;1st|habe|haben;2nd|hast|habt`, a grid, not a table.

## Kinds, round 7 — the actual last three

These three each have a scene of their own in a wider registry, and Mermaid expresses none of them.
Round 6 was mislabelled "the last three"; the real
remainder is here.

| kind | payload | what it draws |
|---|---|---|
| `funnel` | `label=value` | a staged funnel: each stage narrower, the drop-off named |
| `scatter` | `x=y` | points on two axes, both ranges named |
| `waterfall` | `label=+n` or `label=-n` | a running total: bars that step up and down from a baseline |

- `funnel` — `d="Visited=1200;Signed up=340;Activated=180;Paid=64"`. Stages keep their order and the share
  **lost** between stages is named, because the drop is the point of the kind.
- `scatter` — `d="1=2.4;2=3.1;3=2.9"`. Both axes carry a range and ticks; a point's coordinates are
  readable without hovering.
- `waterfall` — `d="Start=+120;Refunds=-30;Costs=-45;Net=+45"`. Bars step from the running total and a
  bar's sign is legible **without colour**: the direction carries it.

## Shapes, not subjects — the end of per-subject kinds

A kind per subject does not scale: nutrition today, plumbing tomorrow, every one a hardcoded rule. Render by
the **shape of the data**, not by what it is about, so a new subject needs no new kind.

| shape | what it is | generic drawing |
|---|---|---|
| `records` | rows of `label=value` (optionally a third cell) | a labelled value list; a third cell is a secondary column |
| `pairs` | `a=b` where both sides are numbers | points on two axes |
| `series` | one ordered numeric run | a line, or bars when the labels are unordered |
| `stages` | an ordered run of decreasing counts | a funnel, drop named |
| `steps` | an ordered run carrying done-ness | a checklist |
| `grid` | a header row plus equal-width cells | a matrix |
| `groups` | a label that repeats across rows | grouped rows under a sub-heading |
| `events` | a time or date plus a label | a timeline |

**A subject kind is a skin over a shape, never a new engine.** `nutrition` is `records` whose third cell is a
target; `words` is `records` with four cells; `forms` is `grid`; `route` is `events`; `matches` is `groups`.
When no specific kind claims the data, the **shape's generic renderer** draws it — so unfamiliar data renders
well instead of degrading to text. Every drawn kind declares its shape, and a rule may emit a bare
`k="records"` with no subject rule at all.

## Round 9 — the widget is alive: glyphs, motion, interaction, body text

Four additions, all of them in the desktop half. Each one is **decoration or affordance**: the widget is
complete, correct and readable with every one of them switched off, and every value it shows is still
there as text.

### One glyph vocabulary, and no character that can be drawn as an emoji

Every glyph the core draws comes from one fixed set, and each keeps its text label — a glyph never carries
meaning alone.

| meaning | glyph | code point |
|---|---|---|
| done | `✓` | U+2713 |
| doing | `●` | U+25CF |
| todo | `○` | U+25CB |
| blocked / failed | `✕` | U+2715 |
| up, gained | `▲` | U+25B2 |
| down, lost | `▼` | U+25BC |
| next, a step | `▸` | U+25B8 |
| a document | `▤` | U+25A4 |
| code | `◈` | U+25C8 |
| unknown file | `□` | U+25A1 |

**`⚠` (U+26A0) is banned**, and so is every code point in U+2B00–U+2BFF, U+1F000–U+1FAFF, and anything
carrying an emoji presentation: a host that substitutes an emoji font then draws a coloured symbol inside
a widget that is otherwise monochrome text, which is the "wrong symbol" a reader notices. The warning a
`recipe` row carries is `▲` — the same mark the deployment's own vocabulary uses for *mind this*.

A test walks the core's own glyph constants and fails on any one outside the table; a second pass scans the
whole core source for the banned ranges, so a mark spelled inline cannot slip past the constants.

### Motion: the index rides in the markup, and the cap comes off

The stagger is a custom property the core writes per element — `--d` on a row, `--k` on a bar — so the
delay is `calc(var(--d, 0) * 34ms)` / `calc(var(--k, 0) * 45ms)` and the list can be any length. The six
`:nth-child` delay rules this replaces stopped at the sixth row, which is a silent cliff: a ten-row
checklist animated as six rows and four that had already arrived.

All motion sits inside `@media (prefers-reduced-motion: no-preference)`, so the still rendering is the
default and the guard cannot be forgotten. Motion is transforms and opacity only, never a size: a widget
must not reflow while it arrives.

### Interaction: the core declares, the mount behaves

**The core stays pure.** It emits affordances as attributes and nothing else — `data-hv-row` on a row a
pointer or the keyboard can land on, `data-hv-note` and one note slot on a widget the answer gave a note,
`tabindex="0"` on a row a reader can focus. No handler, no `addEventListener`, no DOM read.

**The dim is the only per-row affordance.** `data-hv-row` is on every row that reads as a row: the hovered
or focused one stays at full strength while its siblings dim. Pure CSS, with the same treatment for
`:focus-visible` as for `:hover`, so the keyboard is not a second-class reader.

**A hover note is the answer's, never the core's.** The core derives no label — not a rank, not a share, not
a remainder. A label the plugin invents is chrome over a number the reader can already see, and the drawing
already shows what it can, so the ONE label a widget carries is the one the answer asked for with `n=`: on
the widget root as `data-hv-note`, with one empty `<span class="hv-note" data-hv-note-slot>` in the caption.

| | |
|---|---|
| `n="100 runs across both"` | one note for the whole widget, revealed while the pointer or the keyboard is on it |
| no `n=` | no attribute, no slot, and no CSS for a label nobody wrote |

**No note by default, on any kind.** Every renderer prints every number it draws, and none of them computes
a second one for a tooltip. What this replaced was seven renderers deriving a label per row — a rank, a
share, a remainder, a shortfall — which doubled the drawing instead of explaining it. Where a widget cannot
print something the reader needs, the *answer* says so with `n=`, and only the answer can know that.

**The mount owns the behaviour.** The React component reads `data-hv-note` off its `.hv-mount` element and
reveals it in the slot on `pointerenter` / `focusin`, hiding it again on `pointerleave` / `focusout` — **one**
listener per widget, installed on the element React already owns, so nothing runs inside the core and
nothing survives a re-render. A widget with no note installs no listener at all.

- **The note is a convenience, never the only home of a number.** Every value the widget has is printed in
  the widget; with the listener absent the widget is still complete.
- Keyboard: a focusable row is reachable and readable with no pointer at all, and the note arrives on focus.

### References — a cell the reader can open

A cell whose whole value is an `http(s)://` URL, or an absolute path (`/…` with a second slash and no
whitespace), is not text: it is the host's own kind of reference, and the reader can act on it. The core
draws it as `<button class="ref hv-ref" data-ref="url|file" data-hv-link="…" data-hv-value="…">` with the
host's glyph for that kind — the same 24×24 outline the host leads its inline references with — and the
visible text unchanged.

- **The kind and the colour are the host's.** `data-ref` is the host's attribute and `--ref-color` its
  property, taken inline (`style="color:var(--ref-color,currentColor)"`) because a widget cell's own colour
  is a more specific selector than the host's `.ref`. The plugin declares no colour of its own, and a host
  without the property falls back to the text colour.
- **Only unambiguous shapes qualify** — a full URL, or a rooted path. A date, a fraction, `src/main.py`, a
  bare `/usr` stay text. A `~/…` path cannot arrive: the payload grammar strips `~`.
- **A header stays text**: a header names a column, it is not a value.
- **The core declares the click, the mount performs it.** `data-hv-link` says what a click means;
  `VizWidget` owns one delegated `click` listener that routes `url` to the host bridge's `openExternal` and
  `file` to its `revealPath` (which checks the path on disk and hands it to the OS file manager). Neither
  is in the plugin SDK, so both are feature-detected — a host with neither leaves the button inert.
- **A button, not an anchor**: a widget cannot rely on the host's navigation guards, so the click is
  handled rather than navigated, and a button is reachable by keyboard too. Its visible text is never
  shortened — the plugin shows the value the answer gave it.

### A changed-files list is the host's — so the `changes` group ships OFF

The host already renders that card (`components/assistant-ui/thread/changed-files-card.tsx`): basename, type
glyph, `+a`/`-b`, the path in the row's tooltip, the row itself the control. A widget drawing the same data
differently makes one thing look like two, and a widget drawing it *the same way* is a copy that drifts from
the card it copies. **The plugin's own card is the host's, and it is kept**: the kind, the renderer and the
rule all still exist — so a diff summary in an answer is drawn the same way wherever it appears, and the
shape is there for anyone who wants the widget — but the group is **off by default**, so a fresh install
leaves the list to the host.

`DEFAULT_RULE_GROUPS_OFF` in `__init__.py` names the off groups, and it is the only way a group may be
missing from `DEFAULT_RULE_GROUPS`: `tests/test_format_guide.py` fails if a group is off without being
declared there, so a group cannot go quiet by accident. A user turns it on in the settings page like any
other.

**The rule is a rule, not one kind**: the plugin draws what the host does not. A changed file, a tool call,
a running to-do list — anything the host already renders is left to the host, however tempting the widget.

### Body text — a measure and a heading colour, on by default

Setting `body_style`, default **on**. Off, the injected stylesheet is byte-identical to the base sheet.

The app already owns the transcript's typography — its line-height token, its paragraph gap, its heading
sizes, margins and weight, its marker and strong colours. Restating any of it is how a plugin ends up
fighting the app it draws inside, so this adds **two** things, and only two:

- **A measure, and one column**: `--hv-body-measure: 68ch` on `.aui-md` itself, centred with
  `margin-inline: auto` — see *Width, padding and measure*. The app's markdown root is `max-w-none`, so
  without it a line of prose runs the width of a wide window. On the block and not on each element,
  because a `ch` in a heading's larger type measures wider: the prose, the headings and the widgets'
  mount then share one column instead of the heading stepping out on both sides.
- **A heading colour**: `h1`–`h3` take `--dt-primary`. The app paints headings the same colour as the body
  (`prose-headings:text-foreground`), so structure reads only as size until a colour carries it.

Both rules are scoped under `.aui-md` — the app's own transcript root — so nothing reaches another surface,
and the colour rule is written `:where(...)`: one class of weight, so the app's own utilities still win a
tie. Nothing sets a font size or a line-height, and the only colour is the app's own token. **CI cannot
verify the pixels**, so the settings description says so.

## Round 11 — interaction: a template is data, the core declares, the mount performs

The widget may be **operated**, and the model pays nothing for it. The payload keeps exactly the bytes a
static widget costs: the model writes no expression, no handler and no formula, and nothing it writes is ever
executed. The interaction is bought with plugin code, not with prompt or answer tokens.

**`x=` names a template, and a template belongs to a SHAPE.** `toggle` ticks a `steps` row (`steps`,
`checklist`, `outline`); `pick` chooses a `records` row (`facts`, `kpi`, `settings`, `files`, `metrics`, …).
A template named for a shape that cannot carry it is **not** an error to report: the widget then draws
exactly as it would with no `x=` at all — no attribute, no affordance, no cursor, nothing to explain.

**A template is a pure function in the core, so it is testable without the app.**
`applyTemplate(template, kind, rows, state) -> rows`: the same parsed rows with the state applied, never
throwing, returning its input untouched for an unknown template or a kind that cannot carry it. `parseSpec`
returns the template as `spec.template`; `renderKind` draws whatever rows it is handed; the state reaches the
markup only as the attributes below.

**What the core declares** — attributes only, exactly as `data-hv-note` and `data-hv-link` work:

| attribute | where | meaning |
|---|---|---|
| `data-hv-x="toggle\|pick"` | the widget root | this widget is operable, and how |
| `data-hv-i="3"` | each row the template acts on | the row's index in the parsed row list |
| `data-hv-picked="3"` | the picked row | drawn from `opts.picked`, the one piece of state the core is told |

`data-hv-picked` is the single exception to "the state stays in the mount": a pick has to be *visible*, and
how a chosen row is drawn is the core's business. It is drawn from an option, never inferred from the data.

**What the mount performs.** `VizWidget` holds the state (`useState`), re-derives rows with
`applyTemplate`, and re-renders through `renderWidget(attrs, rows)` — one **optional second argument**, the
parsed rows, so the mount never re-parses and the pure entry point keeps its shape. One delegated `click`
listener on the element React already owns maps `[data-hv-i]` to a row. Nothing else moves: a widget that
asked for no `x=` installs no listener, gains no attribute and draws byte-identically to round 10.

**Only `pick` sends, it sends once, and it sends hidden.** A pick that cannot send still marks — the state is
local and the send is an action *on* it, never the carrier of it. The turn is
`host.request('prompt.submit', { session_id, text, display_kind: 'hidden' })`: the app's own submit forwards
`display_kind` and the gateway persists exactly `hidden` as a row no client paints, so the reader sees the
answer and not a bubble they did not type. The text is **derived from the payload**, never authored by the
model — `Picked <row label>`, with the widget's `t=` when it has one. The session resolves
`focusedSessionId` → `focusedStoredSessionId` → `activeSessionId`; **a pick with no resolvable session does
not send at all**, because a widget must never address whichever chat happens to be mounted. One send in
flight per widget: a second pick while the first is unanswered is dropped, never queued.

**The guide names `x=`, each template and the shapes they belong to**, in one line and in the guide's own
vocabulary. A template the prompt does not name is a template nobody writes, and
`tests/test_format_guide.py` is what keeps the two lists in step.

## Round 12 — a cell the payload computes, and what a surface that cannot draw is owed

Two rules about one thing: the answer composes itself, and nothing about it is lost on a surface that
cannot draw it. The model composes — a widget carries the data, the prose carries what the drawing
cannot — and a widget's value may be **computed from the widget's own rows**, so a total is arithmetic
the halves do, never the model's and never the reader's by eye.

### Computed cells

A value cell may be a call on the payload's own rows:

| call | meaning |
|---|---|
| `sum(A, B, …)` | the total of the named rows, one or more names |
| `share(A, B)` | A as a percentage of B |
| `diff(A, B)` | A minus B |

`::viz{k="metrics" d="Prose=43;Bullets=42.2;Read line by line=sum(Prose, Bullets)" u="%"}`

- **Brace-free by construction.** Parens and commas are not reserved by the encoding, so a call travels
  inside `d` untouched — the tier costs the app's parser nothing, and the model pays one word for it.
- **The call is the whole value.** `Total=sum(A, B)` is a call; `about sum(A, B)` is text.
- **A name is a row's own first cell label**, and a header row is never a name: a header names a column,
  it is not a value. **A named row's number is the first number it carries** — `1850 of 2200` sums as
  1850, `42%` as 42, `12 ms` as 12.
- **A computed number prints as an integer when it is one**, else to two decimals with the tail trimmed,
  **rounded half away from zero** — spelled out in integer arithmetic in both halves, not left to a
  library: `%.2f` rounds a tie to even and JavaScript's `toFixed` rounds it away from zero, so a total
  of `0.125` would read `0.12` on the desktop and `0.12`/`0.13` elsewhere. `85.2`, `33.33`, `88`.
- **Both halves implement the evaluator**, because both have to: the core draws a directive the model
  wrote, and the agent half demotes one on a surface that cannot. `tests/cells.json` is the one table
  both suites read, so a rule that drifts fails in CI instead of in an answer nobody can check.
- **It is data, never code.** Three functions, a fixed arity, and no expression that reaches anything
  outside the payload. Nothing in `d` is ever executed.

**Unresolved is visible, not hidden.** A call whose names do not resolve — an unknown row, a non-numeric
row, a cycle, a division by zero, the wrong number of arguments — is left **exactly as written**, so the
drawing prints `sum(A, B)` rather than inventing a number for it. The validator below is what refuses
such a directive before a reader meets it.

### The validator — only what can be proved undrawable

`viz_dsl.is_drawable(attrs)`: five provable failures, and nothing else.

| failure | why it is provable |
|---|---|
| the attrs group is past the 1200-char cap | the app's parser refuses the group, so the reader gets grammar |
| a brace inside the attrs | the same refusal, by the same rule |
| the attrs are not `key="value"` pairs | the app reads pairs; whatever is left is not one |
| the kind is not one the core draws | `renderKind` falls back to prose for it |
| a computed cell the payload cannot compute | the drawing would print the formula |

**Anything else is left alone.** `KNOWN_KINDS` is pinned to the core's own `KINDS` by a test, and an attr
the app does not read is not a failure — `x=` (round 11) is a real attr, and a fence that ate it would
break the feature it was added for. Demoting a widget the app would have drawn is the worse error, so
the fence is drawn where the two halves of it are.

**A board is judged by the core's own rule for its entries**, which round 2 already fixed: *one bad
entry degrades to prose for that cell alone while the rest of the board still renders*. So an entry is
not a refusal — not an unknown kind, not a missing one — and the only two entry failures that demote a
board are an entry with no payload at all (the cell's drawing would be the raw `kind:` text) and a
computed cell that entry cannot compute (a formula the reader would read as a value).

### A surface that cannot draw is owed the data

The take-it-back-out rule is replaced. A `::viz` reaching a surface that does not parse one is
**demoted to the markdown it would have drawn**, its computed cells resolved:

- a title becomes a bold caption line, above its block — **including a board's**, whose entries carry no
  title of their own;
- a payload with a header row becomes a markdown table — **only** from a header row: a markdown table
  needs one, and inventing column names writes words the answer never had;
- any other payload becomes a list, one row per line, a row's label bold;
- a run of bare numbers becomes one line, because three bullets for three numbers is a column of noise;
- `u=` rides on the cells that are only numbers, and on no other cell — on the bare run too;
- a directive that owned its paragraph leaves its block where it stood; one written mid-sentence leaves
  the sentence, with its rows inline; a fenced block keeps its grammar; a directive with nothing to
  carry leaves no line.

**The same pass runs on the desktop** for a directive the validator refuses: grammar or an empty frame
in front of a reader is exactly the failure the platform gate exists to avoid. A directive that draws is
left **byte-identical**, so a widget the model wrote is the widget it wrote.

### The derivation stands down where the answer drew

**One hand on the numbers, never two.** An answer that carries a `::viz` at all has drawn its own data,
so the derivation stands down for the whole answer: it does not re-derive the same run beside the
model's own widget, which is one thing looking like two — the reason `changes` ships off, applied to the
whole answer. The derivation's job is the answer that did not draw; the guide's job is the answer that
does.

**The guide names the tier**, in its own vocabulary: the composition rule (the widget carries its
numbers, the prose carries the reason, the caveat and what the drawing left out) and the three calls.
A call is not a kind, so no group gates it, and `tests/test_format_guide.py` fails when the guide and
`tests/cells.json` drift.

## Round 13 — the operable value, the five shapes still missing, and the licence to repair an answer

Round 11 made a widget operable with two templates and named no third. Round 13 adds the third
template, the five shapes this plugin did not draw, and the one narrow licence the agent
half has to act on an answer's own directives. **No new attribute is introduced:** the five kinds are
new `k` values on the existing encoding, and `step` is a third `x=` value, so the app's parser, the
1200-char cap and the brace-free rule are untouched.

### `x="step"` — the reader's own value

`step` belongs to the shapes that carry a value per row: `facts`, `kpi`, `records`, `metrics`, `files`.
It draws a minus and a plus control on each row and **one send control** at the widget's foot.

| attribute | where | meaning |
|---|---|---|
| `data-hv-x="step"` | the widget root | this widget's rows are stepped |
| `data-hv-i="3"` | each stepped row | the row's index in the parsed row list |
| `data-hv-d="1"` / `"-1"` | each control | what one click adds to that row |
| `data-hv-send` | the send control | sends the accumulated delta, once |

A control click **never** sends: it moves the row by `data-hv-d` — `±1`, and a row never goes below 0 —
and the mount re-renders. The send control sends **once**, carries the delta and never the whole state,
and is disabled while nothing has moved and while its send is in flight. Its text is derived from the
payload, never authored by the model — `<label> +2, <label> +1` — prefixed by the widget's `t=` when it
has one. The session resolves exactly as a `pick`'s does (`focusedSessionId` → `focusedStoredSessionId`
→ `activeSessionId`), and a widget with no resolvable session does not send.

**A computed cell recomputes over the stepped rows.** `applyTemplate` applies the state to the parsed
rows first and `sum(A, B)` and its siblings then resolve over *those* rows, so a total the model wrote
follows the reader's hand. A widget with no `t=` and no moved row draws byte-identically to a static one.

### The five shapes

Each is a new `k` value on the existing encoding (`;` rows, `|` cells, `=` key from value, `~` between
entries), and each is reachable through an explicit `::viz`: **no rule in `rules.yaml` derives one**, so
no group gates one and the guide names all five unconditionally.

| kind | payload | draws |
|---|---|---|
| `tags` | `d="alpha;beta=7"` | one chip a row; `label=value` prints the value inside the chip. A chip keeps its label — colour ranks, it never encodes. |
| `calendar` | `d="2026-10-04=release;2026-10-09=review"` | one month, taken from the first row's date, its marked days labelled; `t=` names the widget. |
| `area` | `line`'s payload | the same series as `line`, its region filled in the series' own hue under the stroke. |
| `tabs` | `d="Firmware:bars=x=1;y=2~Cost:table=h=Item\|k"` | one panel a tab; an entry is `label:kind:payload`, the first `:` delimits the label, and `:` is reserved at that level. A panel draws what a single-widget directive of that kind draws. |
| `followup` | `d="Round both halves=Make the tie round the same way in both halves"` | one button a row; the label is the button and the prompt is what it sends. |

A row that cannot be drawn is never quietly dropped: an unparseable date, an entry with no kind and a
`followup` with an empty prompt are printed as labelled text under the drawing, so the reader keeps every
value. A `followup` sends on a click, once, by `pick`'s rules — including "no resolvable session, no
send". `tabs` keeps its chosen panel for the turn, as a `pick` keeps its row.

### The licence to repair an answer the model wrote

The agent half may act on an answer's own directives on a surface that draws, and **only** on these
three, each provable without reading meaning:

1. A directive the app and the core would refuse — **demoted** to the markdown it held (round 12).
2. The **same kind with the same payload** already drawn in this answer — the repeat is dropped.
3. More drawings than `max_widgets` — the extras are dropped, keeping the first `max_widgets` in the
   answer's own order. The cap counts what the answer draws, derived and authored alike.

Nothing else moves. Prose, headings, tables, code fences and `::preview` are never touched, an answer
that violates nothing comes back **byte-identical**, and the pass never invents a directive. Rewriting
the answer's words to the format is not this pass's job and not a future one either: the prompt asks,
and the pass repairs only what cannot be drawn.

## Levels, groups and the guide — the shipped defaults

- Every rule group ships **on**, except `changes` — the one group off by default, because the host draws its
  own changed-files list. A user turns either way in the settings page.
- The format guide ships **on**, and so does the body styling.
- **Both settings pages state the guide's live cost.** The API recomposes the guide for the toggled groups
  on every read *and* every write, so a switch moves the chip in the same round trip — neither the app's
  page (`desktop/plugin.js`) nor the web bundle holds a number of its own. The README is the one place the
  cost is written down, and a test pins that figure to the shipped groups' text.
- **A setting's description is at most two lines, and never states a default in prose.** "On by default"
  is the toggle's position, which the page already draws; where a value can be measured (the prompt cost,
  the char and kind counts) the page shows the live figure instead of a number that goes stale.
- **The guide names the kinds the enabled groups can draw, and no others.** Its kind block is composed from
  `rules.yaml` against `rule_groups`, so a group that is off leaves the prompt the way it leaves the table:
  absent, not annotated. There is no "`changes` is OFF" line, because a disabled feature named in a prompt
  is tokens spent on a kind the model may not write. A kind no rule emits (`line`, `table`, the named
  subjects) has no group to gate it and stays reachable through an explicit `::viz` either way.
- Level 2 fires wherever a level-1 band is open and the content sub-divides — a list or table under a caption
  inside an open section is enough; it no longer waits for a `###` the answer already carries.
- Where two kinds claim the same rows, the **more specific shape wins** and the other stands down — a funnel
  at any length is never also a heatmap.

## Module boundaries

| Path | Owner | Notes |
|---|---|---|
| `desktop/` | the desktop lane | the directive, the grid, the token layer, our kinds |
| `python/`, `rules.yaml`, `__init__.py` | the agent lane | the matcher, the emitter, the hook |
| `dashboard/` | the last round | the settings page |
| `SPEC.md`, `README.md`, `AGENTS.md` | the orchestrator | read-only to both lanes |

## The one design constraint that makes the desktop half verifiable

The drawing must be a **pure function**: `renderKind(kind, rows, opts) -> string` producing markup, with
the React component only mounting the result. Why: the production app exposes no CDP port, so the only way
to check appearance is to render the same pure output into a static fixture page and screenshot it in a
browser at chosen widths. A renderer that only exists inside a React tree cannot be verified at all.

## The rule table — `rules.yaml`

Derivation is **data**. Each rule: `id`, `when` (a matcher name), `kind`, `min` (rows required), `group`
(the toggle the settings pane shows). The matcher lives in `python/derive.py`; adding or removing a rule
is a YAML edit, never a code change.

## Verification — the commands the acceptance runs

```
pytest tests/ -q                              # the agent half
node tests/desktop.test.mjs                   # the pure drawing core
python3 scripts/fixture.py > /tmp/all.html    # then screenshot at 1400 / 900 / 500px
```
