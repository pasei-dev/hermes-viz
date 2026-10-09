# hermes-viz

**This plugin owns the shape of an answer.** Structure first, prose second: headings for sections, lists
for steps, tables for comparisons, a callout for a warning, and a drawing wherever words carry what a
drawing carries better — so a long answer reads as a few decisions instead of a wall of text, without
losing a word the answer held.

Widgets inside Hermes answers — the numbers, comparisons and steps an answer already contains, drawn in
the app's own React tree so they are transparent, follow the theme live and are sized by the pane rather
than by a constant. A `transform_llm_output` hook reads the finished answer and derives visuals from the
markdown the model already wrote, so the picture costs **zero prompt tokens** by default: the model pays
nothing for the drawing. Structure rides on the app's own Mermaid renderer, retinted to the app's
palette; the answer-shaped widgets Mermaid cannot draw — KPI rows, deltas, steps, tables, progress,
sparklines — are drawn by this plugin. An explicit `::viz{...}` directive in the answer wins wherever it
appears, for the times a rule guesses wrong. The `format_guide` setting is the other half of that claim:
it hands the model the mandate above — the answer's shape, paid for once in the prompt —
so the model composes the structure and the transform then draws it.

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
grouping — one line per group. Thirty groups, 29 of them on, and they are read straight from `rules.yaml`,
so a new rule in a new group appears on the page by itself.

| Group | Draws | What makes it fire |
|---|---|---|
| `structure` | the `### ` headings | a heading, or an all-bold line, the answer already wrote |
| `numbers` | `bars`, `kpi` | a labelled numeric run, or a row of `name=value` pairs |
| `tables` | `bars` | the rows of a numeric markdown table |
| `steps` | `steps` | an ordered list, or a `1.`-style run |
| `checklist` | `checklist` | a `- [x]` / `- [ ]` run |
| `changes` | `changes` (**off**) | a run of `+` / `-` deltas, drawn as the app’s own changed-files card |
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

Across those groups the agent half emits **33 kinds**. The explicit `::viz{...}` directive reaches the
rest: the desktop core draws **40 kinds** in all, and the thirteen no rule derives are there the moment
the model writes the directive itself — `line`, `donut`, `progress`, `sparkline`, `table`, `series`,
`pairs`, `stages`, and the subjects `words`, `recipe`, `route`, `nutrition`, `matches`. `board` composes
several of them in one directive.

Every widget is drawn from **one glyph vocabulary** — ten marks, none of them a character a host could
render as an emoji — and arrives with a per-element **stagger**. Hovering or focusing a row dims its
siblings, and the drawing never labels itself: **the core derives no readout**, because a label the plugin
invents is chrome over a number already on screen. The one label a widget carries is the one the answer
asked for with `n=`, and a widget without one carries no caption slot at all.

**A changed-files list is the app's own card, so the `changes` group ships off.** The app already renders
"N files changed" — each file's name under a type glyph, green `+a` and red `-b`, the full path on hover,
the row the thing you click — and a second rendering of the same data, however faithful, is a copy that
drifts. The kind, the rule and the renderer are all still there (a diff summary is drawn the same way
wherever it appears), but the group is off by default: a fresh install leaves the list to the app. One
switch in the settings page brings the widget back. The same reasoning covers any list the app already
draws.

## The settings

| Setting | Default | What it does |
|---|---|---|
| `palette` | `dark` | `dark` / `light` / `mermaid`. Mermaid renders into an isolated `<img>`, so its colours cannot follow the app live; this says which palette to bake into each derived diagram. |
| `max_widgets` | `3` | Upper bound on derived widgets in one answer, so a long numeric answer cannot become a wall of charts. |
| `rule_groups` | all but `changes` | The comma-separated groups above that may fire. `changes` ships off. |
| `format_guide` | on | Appends the answer-structuring prompt to **every** request. |
| `body_style` | on | Two things the app does not do, under `.aui-md`: a 68ch measure on the block itself — one centred column for prose, headings and widgets, so both sides get the same room — and `--dt-primary` on `h1`–`h3`. It copies none of the app's own typography. |

**A cell that is a URL or an absolute path is a reference you can click.** The core emits the host's own
reference — `class="ref"` with `data-ref="url"` or `file`, the host's 24×24 glyph and the value in an
attribute — so a link opens and a path is revealed by the OS file manager, performed by the one delegated
listener the widget's mount owns. The plugin declares no colour of its own; the host's `[data-ref]` rule
supplies the kind's hue. Only a whole-cell `http(s)://` URL or a rooted path qualifies — a date, a
fraction, `src/main.py` or a bare `/usr` stays text, and a header is never a reference.

**`body_style` is the half of the answer a widget cannot reach.** The prose between the drawings is the
app's DOM, so the plugin styles it there: every selector sits under `.aui-md`, the app's own transcript
root, and is written `:where(...)` — one class of weight, so the app's own utilities still win a tie. It
sets one measure on the block (68ch, centred: prose, headings and the widgets between them share one
column, so a wide window gives more margin instead of longer lines) and the accent on headings.
Turn it off and the injected stylesheet is byte-identical to the base one.

**Every rule group ships on except `changes`.** A fresh install derives from all the others; `rule_groups` in
`dashboard/settings.json` lists them, and `structure` was never optional, because structuring the answer
is the point of the plugin.

**`format_guide` costs real tokens, and it is where the plugin's claim on the answer's shape lives.** On,
it appends 4530 characters (~779 words, roughly **1119 tokens**) to every desktop turn — headings for
sections, bold for key terms, lists for steps, tables for comparisons, callouts for notes and warnings,
math, no decorative separators, "when something can be shown, show it — in the section it belongs to",
one drawing per idea with several in an explanation, which KIND to choose for which shape of data (a
table is a matrix, never a two-column label/value list), how to say less (the first line is the answer,
one idea per line, a widget instead of the prose beside it, no closing offer), a closing "before you
answer" check, and the `::viz` grammar — every kind the **live** groups can draw, with its payload, so the
ones no rule derives stay reachable.

**A group that is off is not in the prompt.** The kind block is composed from `rules.yaml` against the
enabled groups, so turning a group off takes its kinds out of the guide entirely — the model is never
told about a kind it may not write, and there is no "this is off" line spending tokens on a disabled
feature. The sentence is built, not written: a test walks both directions.
It is the answer-structuring mandate this plugin hands its model. Off, nothing at
all reaches the prompt — byte for byte, the prompt is the same as a plugin that never registered a
section.

**The settings page shows that cost live.** The API recomposes the guide for the groups as they stand on
every read and every write, so switching a group moves the number in the same round trip, and switching the
guide off reads `0 tokens`.

## Turning a group off

**Capabilities → Plugins → hermes-viz** lists one checkbox per group, each with its rule count. Unchecking
one writes the remaining list back to `rule_groups`.

What stops firing is exactly the rules in that group: their kinds are never emitted again, so those
widgets never appear — turn off `heatmap` and no ramp is drawn; turn off `structure` and no heading is
added. Nothing else changes: the other groups keep matching, the answer's own markdown is never
reworded either way, and an explicit `::viz{...}` still draws, because the directive belongs to the
desktop half and never consults the rule table. Unchecking one of two groups that claim the same rows is
also how you settle an overlap — see below.

## Where it is honest about limits

- **Only the desktop app draws.** A `::viz` directive is grammar for one surface; the CLI, the TUI, a
  chat gateway, the dashboard and an API client do not parse it, so on every one of them the answer is
  left exactly as the model wrote it — no headings inserted, no widgets, no raw `::viz{...}` text in front
  of a reader. The format guide is withheld there too, for the same reason: a session that cannot draw is
  not asked to write a directive. An unknown platform is treated as one that cannot draw. A `::viz` the
  model wrote anyway — a resumed desktop session carries them in its own history — is taken back out of the
  answer on its way to one of those surfaces.
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
- **`body_style` is on, and nothing here can verify it.** It styles the app's transcript root (`.aui-md`)
  through the app's own custom properties, and whether those two rules land in the running app is not
  observable from this repo — so the setting's own description says it is unverified, and turning it off
  leaves the injected stylesheet byte-identical.

## Layout

```
plugin.yaml          manifest: hooks, the settings, the rule-group list
__init__.py          the agent half's entry: registers the transform hook and the format guide
rules.yaml           derivation as data — matcher -> widget, one group per row
python/              the matcher, the spec builder, the Mermaid emitter
desktop/plugin.js    the desktop half: the ::viz directive and the 40 kinds we draw
desktop/render/core.mjs  the pure drawing core, vendored verbatim into plugin.js
dashboard/           the settings page (dist/index.js) and its API (plugin_api.py)
scripts/fixture.py   the one-file visual-evidence page for every kind
tests/               run_all.py + pytest for the agent half, node for the drawing core
```
