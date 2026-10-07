# hermes-viz

Widgets inside Hermes answers — the numbers, comparisons and steps an answer already contains, drawn in
the app's own React tree so they are transparent, follow the theme live and are sized by the pane rather
than by a constant. A `transform_llm_output` hook reads the finished answer and derives visuals from the
markdown the model already wrote, so the picture costs **zero prompt tokens** by default: the model pays
nothing for the drawing. Structure rides on the app's own Mermaid renderer, retinted to the app's
palette; the answer-shaped widgets Mermaid cannot draw — KPI rows, deltas, steps, tables, progress,
sparklines — are drawn by this plugin. An explicit `::viz{...}` directive in the answer wins wherever it
appears, for the times a rule guesses wrong.

The contract both halves build against is `SPEC.md`.

## Install

```bash
hermes plugins install <owner>/hermes-viz --ref <40-char sha> --enable
```

**Then turn on the desktop half.** `hermes plugins install` enables the *agent* half only. A unified
package's desktop half ships disabled — the app's loader caps it (`runtime-loader.ts`:
`defaultEnabled: marker ? false : undefined`) and the plugin cannot override that from its own code. Open
**Capabilities → Plugins → hermes-viz** and switch **Desktop** on, or the widgets render nothing while
the plugin looks perfectly installed with an `Agent + Desktop` badge and a green agent switch.

The desktop half is also materialized by the app rather than the CLI: opening that Plugins page, or
`window.hermesDesktop.reconcileDesktopPlugins()` from the renderer, copies `desktop/` into
`<hermes home>/desktop-plugins/hermes-viz/`.

## What it draws

The settings page groups every rule by the **rule group** it belongs to, and the table below is that same
grouping — one line per group. Twenty-six groups ship on, and they are read straight from `rules.yaml`,
so a new rule in a new group appears on the page by itself.

| Group | Draws | What makes it fire |
|---|---|---|
| `structure` | section bands | a heading, or an all-bold line, the answer already wrote |
| `numbers` | `bars`, `kpi` | a labelled numeric run, or a row of `name=value` pairs |
| `tables` | `bars` | the rows of a numeric markdown table |
| `steps` | `steps` | an ordered list, or a `1.`-style run |
| `checklist` | `checklist` | a `- [x]` / `- [ ]` run |
| `changes` | `changes` | a run of `+` / `-` deltas |
| `outline` | `outline` | a nested list |
| `facts` | `facts` | a `key: value` run |
| `files` | `files` | path + line-count lines |
| `parts` | `parts` (BOM) | component / count rows |
| `settings` | `settings` (flags) | `key=on` / `key=off` rows |
| `timeline` | `timeline` | a dated-event run |
| `ranges` | `ranges` (spans) | `start — end` rows |
| `metrics` | `metrics` (deltas) | metric rows with a before and an after |
| `array` | `array` (grid) | a raw matrix |
| `heatmap` | `heatmap` (ramp) | a long numeric run |
| `wireframe` | `wireframe` | block / type rows |
| `candlestick` | `candlestick` | OHLC rows |
| `flow` | Mermaid `flowchart` | an `A -> B` run |
| `mermaid` | Mermaid `state`, `sequence`, `gantt`, `pie`, `timeline` | text that is already Mermaid-shaped |
| `bracket` | `bracket` | round pairings |
| `gloss` | `gloss` | `term: meaning` lines |
| `forms` | `forms` | a paradigm table |
| `funnel` | `funnel` | strictly decreasing, stage-named counts |
| `scatter` | `scatter` | `x=y` numeric pairs |
| `waterfall` | `waterfall` | signed contribution rows |

Across those groups the agent half emits **29 kinds**. The explicit `::viz{...}` directive reaches the
rest: the desktop core draws **34 kinds** in all, so `line`, `donut`, `progress`, `sparkline`, `table`
and `board` (several widgets in one directive) are there when the model writes the directive itself.
Five more — `words`, `recipe`, `route`, `nutrition`, `matches` — are drawable the same way; no rule emits
them yet, so nothing derives them automatically.

## The settings

| Setting | Default | What it does |
|---|---|---|
| `palette` | `dark` | `dark` / `light` / `mermaid`. Mermaid renders into an isolated `<img>`, so its colours cannot follow the app live; this says which palette to bake into each derived diagram. |
| `max_widgets` | `3` | Upper bound on derived widgets in one answer, so a long numeric answer cannot become a wall of charts. |
| `rule_groups` | all 26 on | The comma-separated groups above that may fire. |
| `format_guide` | on | Appends a compact formatting prompt to **every** request. |

**Every rule group ships on.** A fresh install derives from all of them; `rule_groups` in `plugin.yaml`
lists them, and `structure` was never optional, because structuring the answer is the point of the
plugin.

**`format_guide` costs real tokens.** On, it appends 1939 characters (~272 words, roughly **480 tokens**)
to every single turn: headings for sections, lists for steps, tables for comparisons, no decorative
separators, "when something can be shown, show it — in the section it belongs to", and the `::viz`
grammar — every kind the drawing core has, with its payload, so the ones no rule derives stay reachable.
Off, nothing at all reaches the prompt — byte for byte, the prompt is the same as a plugin that never
registered a section.

## Turning a group off

**Capabilities → Plugins → hermes-viz** lists one checkbox per group, each with its rule count. Unchecking
one writes the remaining list back to `rule_groups`.

What stops firing is exactly the rules in that group: their kinds are never emitted again, so those
widgets never appear — turn off `heatmap` and no ramp is drawn; turn off `structure` and no section bands
are added. Nothing else changes: the other groups keep matching, the answer's own markdown is never
reworded either way, and an explicit `::viz{...}` still draws, because the directive belongs to the
desktop half and never consults the rule table. Unchecking one of two groups that claim the same rows is
also how you settle an overlap — see below.

## Where it is honest about limits

- **A long funnel is also a heatmap.** A strictly decreasing stage run of six or more rows matches both
  `funnel-stages` and `heatmap-ramp`, and only `bars` ever stands down (in `_stand_down_bars`). With both
  groups on, the same rows are emitted twice — probed: a six-stage signup funnel comes back as
  `['heatmap', 'funnel']`. Uncheck one of those two groups to pick the winner.
- **Unfamiliar subject data draws as a shape, not as a subject.** The matchers read the *shape* of the
  text, so a nutrition table or a recipe still comes out as `bars`, `table` or `steps` — a generic
  drawing that is right about the data and says nothing about the subject. Only the named subjects
  (`nutrition`, `recipe`, `route`, `matches`, `words`) get their own treatment, and today those are
  reachable through `::viz`, not derived.
- **The transform annotates structure; it does not compose.** It can only draw from what the answer
  already contains, in the order it was written — it cannot decide that a paragraph deserves a chart.
  `format_guide` is the lever that composes: it asks the model for structure, and the transform then
  draws it.
- **The Mermaid palette is a setting, not a live read**, because an `<img>`-hosted SVG cannot resolve
  `var()`. Change the app theme and the derived diagrams keep the palette you chose.

## Layout

```
plugin.yaml          manifest: hooks, the settings, the rule-group list
__init__.py          the agent half's entry: registers the transform hook and the format guide
rules.yaml           derivation as data — matcher -> widget, one group per row
python/              the matcher, the spec builder, the Mermaid emitter
desktop/plugin.js    the desktop half: the ::viz directive and the 34 kinds we draw
desktop/render/core.mjs  the pure drawing core, vendored verbatim into plugin.js
dashboard/           the settings page (dist/index.js) and its API (plugin_api.py)
scripts/fixture.py   the one-file visual-evidence page for every kind
tests/               run_all.py + pytest for the agent half, node for the drawing core
```
