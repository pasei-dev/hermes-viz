# SPEC — the contract both halves build against

Read-only for both halves. Change it deliberately, never in passing: it is the only thing keeping the
agent half and the desktop half from drifting apart.

## The directive

`::viz{...}` alone on its own paragraph. The app's parser (`lib/transcript-directives.ts`) allows: one
line, the whole paragraph, <=1200 chars, attrs as `key="value"`, and **no `{` or `}` anywhere inside the
attrs**. Nothing else in the paragraph, ever.

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
::viz{k="table" d="h=Board|Runs;291e|42;223e|17"}
::viz{k="steps" d="Read the archive;Patch the entry;Flash over EC3"}
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

Padding is per widget and per side — 14px/16px at the base, 20px/24px from 48rem up. Nothing may touch the
widget's own edge.

## Kinds, round 2 — the answer-shaped cards

Gap analysis against a 43-kind widget set. Everything structural it has that
Mermaid expresses — `flowchart` `sequence` `state` `class` `er` `gantt` `pie` `journey` `gitgraph`
`timeline` `quadrant` `sankey` `treemap` `radar` `xychart` `mindmap` — **already arrives** through our
Mermaid fence path. What Mermaid cannot express, and we lack, is the answer-shaped card:

| kind | payload | what it draws |
|---|---|---|
| `checklist` | `label=state`, state ∈ `done\|doing\|todo\|blocked` | rows with a state glyph; done struck through |
| `changes` | `path=+adds=-dels` | a diff summary: per-file bars, add/del counts, a total |
| `outline` | `1=Title;1.1=Sub` | a contents list, depth from the dotted prefix |
| `facts` | `label=value` | a definition card: muted label above a strong value |
| `files` | `path=meta` | a file listing with a kind glyph and a muted meta column |
| `parts` | `h=Ref\|Part\|Qty;U1\|C8051F121\|1` | a bill of materials, quantities right-aligned |
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
an optional palette key beside it, and no rule of any kind — so a long answer reads as sections instead of
a wall of text.

The derivation may **insert** a heading where the answer already behaves like one (an all-bold line, or a
run of parallel items) and may group the widgets under it into one board. It **never** rewords, deletes or
reorders the model's own words: structure is added around them, never substituted for them.

## Section levels, and one board per section

`section` gains `l=1|2` (default 1). Level 1 is the answer's own division — heading type above a hairline,
a palette key. Level 2 is a division *within* one: one step down in type, a muted rule, no key. A board may
mix them, and **the hierarchy must be legible from type size alone**, with no colour needed to read it.

**One board per section.** Where the derivation inserts a heading it emits that section band and the widgets
that follow it in the *same* board, so a reader gets heading, then its own data, then the next heading.
Sections never collect at the top of a board ahead of the widgets they head.

**How the level travels.** A standalone section directive carries it as the `l` attr (`l="2"`). Inside a
board it rides as a cell of the entry payload — `section:Board runs;l=2` — where the first non-`l=` cell is
the heading and level 1 omits it entirely. This paragraph exists because round 3 left it open, and the two
lanes duly chose differently (`section:2:Heading` against `;l=2`): an interface with two valid readings is
the SPEC's error, and it fails silently in the app while both suites stay green.

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
- `route` — `d="09:40=Kastrup=Check in;11:10=Gate B=Board"`, stops on one rail with their times.
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
