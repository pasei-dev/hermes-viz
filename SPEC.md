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
and a row beginning `h=` is a header. Values must not contain `;`, `|`, `=` or `\` — the emitter strips
them, and that stripping is the emitter's responsibility, not the renderer's.

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

`kpi` `bars` `line` `donut` `steps` `table` `progress` `sparkline`

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
