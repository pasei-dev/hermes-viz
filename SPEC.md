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

**And a directive already written is taken back out.** A model writes one without being asked: a session
resumed from the desktop app carries directives in its own history, and a model imitates what it can see.
On a surface that cannot draw, that is the same line of raw grammar — so the hook removes every `::viz`
from an answer bound for one, and returns the answer untouched when it finds none. A directive that owned
its paragraph takes its line with it; one written mid-sentence leaves the sentence, with the gap closed. A
fenced code block is left alone, because a reader being *shown* the grammar is not a reader being shown a
widget, and only `::viz` is touched — `::preview{...}` and the app's other directives belong to the app.

| attr | required | meaning |
|---|---|---|
| `k` | yes | the kind, `[a-z][a-z0-9-]*` |
| `d` | yes | the data, in the encoding below |
| `t` | no | title |
| `u` | no | unit suffix for the values |
| `p` | no | palette for a Mermaid kind: `dark` \| `light` \| `mermaid` (default: the plugin setting) |

## The data encoding

Brace-free, newline-free, one attribute value. **Rows split on `;`, cells on `|`, key from value on `=`**,
and a row beginning `h=` is a header. `~` separates the widget entries inside a `board` (below). Values
must not contain `;`, `|`, `=`, `~` or `\` — the emitter strips them, and that stripping is the emitter's
responsibility, not the renderer's.

```
::viz{k="bars" d="Firmware=42;DSP=28;Web=18" u="%"}
::viz{k="kpi" d="Builds=128=+12;Fails=3=-1"}
::viz{k="table" d="h=Board|Runs;Alpha|42;Delta|17"}
::viz{k="steps" d="Read the archive;Patch the entry;Flash the board"}
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
`### Builds` — was drawn twice. The rule is now one line: **a heading the answer renders is never also
drawn as a widget.** The layer inserts a `### ` marker where the answer behaves like a heading but is not
one, and that marker *is* the section's heading; `section` remains for an explicit `::viz`, where the
model asked for a band itself.

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

**How the level travels.** In the derived path the level is the marker the layer inserts: a division
within a section is a `###` under the `##` that opened it. For an explicit directive it rides as the `l`
attr (`l="2"`), or inside a board as a cell of the entry payload — `section:Board runs;l=2` — where the
first non-`l=` cell is the heading and level 1 omits it entirely. This paragraph exists because round 3
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
