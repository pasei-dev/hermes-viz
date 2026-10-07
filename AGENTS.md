# AGENTS.md — hermes-viz

## What this is

A Hermes plugin with two halves that meet at exactly one contract: `SPEC.md`. The agent half derives
visuals from a finished answer; the desktop half renders them. Neither half may change `SPEC.md` in
passing.

## Rules

- **`SPEC.md` is read-only** unless the change is the point of the task. Both halves are written against
  it in parallel, so an unannounced edit there breaks work you cannot see.
- **The directive is one paragraph, one line, no braces in the attrs.** The app's parser enforces it
  (`lib/transcript-directives.ts`), so a design that needs `{` inside `::viz{...}` is not buildable.
- **The drawing core is pure.** `renderKind(kind, rows, opts)` returns markup; the React component mounts
  it. No DOM access inside the core. This is what makes the appearance verifiable without a CDP port.
- **Never write a background colour into a widget.** Transparency is the contract; the app's surface
  shows through.
- **Theme by token, never by literal — and only by tokens that EXIST.** The app's own tree defines
  `--foreground`, `--color-muted-foreground`, `--dt-primary`, `--dt-border` and `--dt-muted`. The
  shorter set a `::preview` iframe injects (`--accent`, `--border`, `--card`, `--muted-foreground`) does
  **not** exist here, and a `var()` that resolves to nothing drops its declaration silently — a styled
  widget then renders as plain text with no bars and no colour. A hard-coded hex is a bug even when it
  looks right; a wrong token name is worse, because it looks like it works.
- **No fixed pixel size; the content carries a measure.** `--hv-measure` (42rem) caps what sits *inside* a
  widget, so a two-value sparkline cannot become a slab on a wide pane, and a table's columns are sized by
  content instead of stretched to fill. The widget itself is never clamped and the grid always reflows — a
  wider pane still shows more columns. This replaced an earlier "no `max-width` anywhere" rule: the user
  overrode it, because text and widgets filling the whole width on a big screen reads badly.
- **Surface themed by the app; data painted by the plugin.** The surface uses only the five app tokens
  above. Data uses the six `--hv-*` properties declared once at the top of the CSS, `--hv-1` being
  `--dt-primary`; categories take a hue in first-seen order, deterministically. A literal colour anywhere
  outside that one block is a bug, and colour never carries meaning alone — every coloured element keeps
  its label or its value.
- **Derivation lives in `rules.yaml`.** A new pattern is a data row, not a code branch.
- **The Mermaid palette header is literal by necessity** — an `<img>`-hosted SVG cannot resolve `var()`.
  That is why the palette is a setting rather than a live read.

## Checks

```bash
pytest tests/ -q                  # agent half
node tests/desktop.test.mjs       # drawing core
python3 scripts/fixture.py        # the page the screenshots come from
```
