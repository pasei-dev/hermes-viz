# hermes-viz

Widgets inside Hermes answers — built from the numbers, comparisons and steps an answer already
contains, themed to the app, and sized by the pane rather than by a constant.

Two doors, and they are the whole design:

- **Zero model tokens.** A `transform_llm_output` hook reads the finished answer and derives visuals from
  the markdown the model already wrote. The model pays nothing for the picture.
- **An explicit override.** `::viz{...}` in the answer wins wherever it appears, for the times a rule
  guesses wrong.

Structure arrives as Mermaid fences — the app already renders them, all 20+ kinds, and a per-diagram init
block retints them to the app's palette. The answer-shaped widgets Mermaid cannot draw (KPI rows, deltas,
steps, tables, progress, sparklines) are drawn here, in the app's React tree, so they are transparent,
follow the theme live, and are never clamped.

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

## Layout

```
plugin.yaml          manifest: hooks, the palette setting, the rule-group toggles
__init__.py          the agent half's entry: registers the transform hook
rules.yaml           derivation as data — matcher -> widget
python/              the matcher, the spec builder, the Mermaid emitter
desktop/plugin.js    the desktop half: the ::viz directive and the kinds we draw
dashboard/           the settings page
tests/               pytest for the agent half, node for the drawing core
```
