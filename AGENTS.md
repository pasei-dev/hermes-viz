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
- **No `max-width`, no `max-height`.** The grid reflows; the pane decides.
- **Derivation lives in `rules.yaml`.** A new pattern is a data row, not a code branch.
- **The Mermaid palette header is literal by necessity** — an `<img>`-hosted SVG cannot resolve `var()`.
  That is why the palette is a setting rather than a live read.

## Checks

```bash
pytest tests/ -q                  # agent half
node tests/desktop.test.mjs       # drawing core
python3 scripts/fixture.py        # the page the screenshots come from
```
