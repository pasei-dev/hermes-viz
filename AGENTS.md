# AGENTS.md — hermes-viz

## The two halves and the one contract

A Hermes plugin with two halves: the **agent half** (`__init__.py`, `python/`, `rules.yaml`) derives
visual specs from a finished answer and injects the `::viz` grammar; the **desktop half**
(`desktop/plugin.js`) parses the directive and draws. They meet at exactly one contract: **`SPEC.md`**.
Both halves are written against it in parallel, so changing it unannounced breaks work you cannot see.
Neither may change `SPEC.md` in passing — if a shape in it does not fit the data, that is a conversation,
not an edit.

## Rules

- **The vendored core is one file in two places.** `plugin.js` carries the pure core
  (`desktop/render/core.mjs`) *verbatim* between `// >>> vendored-core` and `// <<< vendored-core`: the
  runtime loader resolves exactly three bare specifiers (`@hermes/plugin-sdk`, `react`, `react/jsx-runtime`)
  and refuses every other import, so a relative one cannot resolve against the blob: URL a runtime plugin is
  evaluated from. Edit `core.mjs`, then copy the block across; **never hand-edit one side.**
  `node tests/desktop.test.mjs` fails if the two drift.
- **Shapes, not subjects.** The core draws *shapes of data* — a run, a grid, a pair, a series, a decreasing
  run — and a named subject (`nutrition`, `recipe`, `route`, `matches`, `words`) is a skin over one of those
  shapes, never new machinery: pick the shape the data already has and dress its labels. A new kind is the
  last resort, not the first move.
- **The directive is one paragraph, one line, no braces in the attrs.** The app's parser enforces it
  (`lib/transcript-directives.ts`). And it belongs to one surface: the hook emits one, and asks the model
  for one, **only when the platform is `desktop`** — anywhere else it takes a `::viz` back out, because raw
  grammar in front of a reader is the failure the gate avoids.
- **The drawing core is pure.** `renderKind(kind, rows, opts)` returns markup; the React component mounts
  it. No DOM access inside the core. This is what makes the appearance verifiable without a CDP port.
- **Never write a background colour into a widget.** Transparency is the contract; the app's surface
  shows through.
- **Theme by token, never by literal — and only by tokens that EXIST.** The app's tree defines
  `--foreground`, `--color-muted-foreground`, `--dt-primary`, `--dt-border` and `--dt-muted`. The
  `::preview` iframe's set (`--accent`, `--border`, `--card`) does **not** exist here, and a `var()` that
  resolves to nothing drops its declaration silently — the widget then renders uncoloured. A hard-coded hex
  is a bug even when it looks right.
- **No fixed pixel size; the content carries a measure.** `--hv-measure` (42rem) caps what sits *inside* a
  widget, so a two-value sparkline cannot become a slab on a wide pane and a table's columns are sized by
  content. The widget itself is never clamped and the grid always reflows — a wider pane shows more columns.
- **No decorative separator, in a widget or in an answer.** A rule line is chrome the reader skips;
  headings, spacing and the widget's own frame do the separating.
- **Surface themed by the app; data painted by the plugin.** The surface uses only the five app tokens
  above; data uses the six `--hv-*` properties declared once at the top of the CSS, `--hv-1` being
  `--dt-primary`, with categories taking a hue in first-seen order. A literal colour outside that one block
  is a bug, and **colour never carries meaning alone** — every coloured element keeps its label or value
  (the waterfall prints its sign, the heatmap prints its number).
- **Motion is opt-in and the index rides in the markup.** The core writes `--d` per row and `--k` per bar,
  the delay comes from that index, and everything sits inside `@media (prefers-reduced-motion: no-preference)`
  — never a fixed `:nth-child` delay, which cliffs at six.
- **One glyph vocabulary, and no emoji-capable character.** Every mark the core draws is one of the ten in
  `SPEC.md`'s table; `⚠` (U+26A0) and the emoji blocks are banned: a host that substitutes an emoji font
  draws a coloured symbol inside otherwise monochrome text. A test walks the core's glyph constants; a scan
  covers the banned ranges.
- **A hover note is the answer's, never the core's.** `data-hv-row` is the dim, on every row; no renderer
  derives a label, and the one label a widget has is the answer's `n=` — `data-hv-note` on the root, one
  caption slot, revealed by the mount. A list the host already draws is the HOST's: `changes` ships OFF
  (`DEFAULT_RULE_GROUPS_OFF`), rule and renderer kept.
- **`body_style` is on by default and adds exactly two things: a `68ch` measure and `--dt-primary` on
  `h1`–`h3`.** Off, the sheet is byte-identical. It copies none of the app's typography (line-height,
  paragraph gap, heading scale); every selector sits under `.aui-md` written `:where(…)`.
- **A URL or rooted path in a cell is the host's own reference.** `class="ref"` plus the host's `data-ref`
  kind and its glyph; `data-hv-link`/`data-hv-value` declare the click and `VizWidget` performs it
  (`openExternal`, `revealPath`). Only unambiguous shapes qualify; the visible text is never shortened.
- **Derivation lives in `rules.yaml`.** A new pattern is a data row, not a code branch, and a rule's
  `group` is what the settings page lists.
- **The Mermaid palette header is literal by necessity** — an `<img>`-hosted SVG cannot resolve `var()`.
  That is why the palette is a setting rather than a live read.

## The prompt section is part of the change

`FORMAT_GUIDE` is the model's only channel to the drawing core, and **its kind block is composed from
`rules.yaml` against the enabled groups** — a group that is off is absent from the prompt, never annotated
("`changes` is OFF" is a prompt bug, not a note). The rule table derives 33 kinds; the other thirteen the
core draws arrive only through an explicit `::viz`, so a kind the guide does not name is a kind nobody
draws. **A new kind, payload or attr is not finished until the guide names it**, and
`tests/test_format_guide.py` fails when the two lists drift.

The guide is a prompt on every request: its cost is stated in three places that move in the same commit —
the counts in `dashboard/settings.json`, the badge in `dashboard/dist/index.js`, and `README.md`.

## Checks

```bash
python3 tests/run_all.py             # agent half, stdlib only — no pytest needed
python3 -m pytest tests/ -q          # the same functions under pytest
node tests/desktop.test.mjs          # the drawing core + the vendored-core drift check
python3 dashboard/selfcheck.py        # settings page: manifest, API routes, bundle
python3 scripts/fixture.py /tmp/hv.html   # every kind on one page, for screenshots
```

`python3 scripts/fixture.py` with no argument rewrites the tracked `desktop/fixture.html`, so pass a path
unless you mean to commit a new page.

## Python

**3.10 or newer, and it must also run on the newest release** — `python3` anywhere above means an
interpreter in that range. The agent half runs on whatever interpreter the host uses: 3.10 is the floor and
no code here may use a feature younger than that; `str | None` and `dict[str, Any]` are the annotation
style, not `Optional`/`Dict`.

## Versions

`plugin.yaml` and `dashboard/manifest.json` carry **one** version and must agree; the app keys a plugin's
dashboard bundle on it, so a mismatch or a missing bump is how a settings page keeps showing the old page.
**Bump both when the change is verified and about to land — not on every edit in a work session**, and
re-check both numbers against what is actually landing, in the commit that lands it.
`python3 dashboard/selfcheck.py` fails when the two disagree.
