# AGENTS.md — hermes-viz

## The two halves and the one contract

A Hermes plugin with two halves: the **agent half** (`__init__.py`, `python/`, `rules.yaml`) derives
visual specs from a finished answer and injects the `::viz` grammar; the **desktop half**
(`desktop/plugin.js`) parses the directive and draws. They meet at exactly one contract: **`SPEC.md`**.
Both halves are written against it in parallel, so changing it unannounced breaks work you cannot see.
Neither half needs to read the other's code, and neither may change `SPEC.md` in passing — if a shape in
`SPEC.md` does not fit the data, that is a conversation, not an edit.

## Rules

- **`SPEC.md` is the interface, and it is read-only** unless changing it is the point of the task.
- **The vendored core is one file in two places.** `plugin.js` carries the pure core
  (`desktop/render/core.mjs`) *verbatim* between the markers `// >>> vendored-core` and
  `// <<< vendored-core`, because the app's runtime loader resolves exactly three bare specifiers
  (`@hermes/plugin-sdk`, `react`, `react/jsx-runtime`) and refuses every other import — including relative
  ones, which cannot resolve against the blob: URL a runtime plugin is evaluated from. Edit
  `core.mjs`, then copy the block across; **never hand-edit one side.**
  `node tests/desktop.test.mjs` fails if the two copies drift.
- **Shapes, not subjects.** The core draws *shapes of data* — a run, a grid, a pair, a series, a
  decreasing run — and a named subject (`nutrition`, `recipe`, `route`, `matches`, `words`) is a skin over
  one of those shapes, never a new machinery. A new subject therefore needs no new kind: pick the shape
  the data already has and dress its labels. Adding a kind is the last resort, not the first move.
- **The directive is one paragraph, one line, no braces in the attrs.** The app's parser enforces it
  (`lib/transcript-directives.ts`), so a design that needs `{` inside `::viz{...}` is not buildable.
- **The drawing core is pure.** `renderKind(kind, rows, opts)` returns markup; the React component mounts
  it. No DOM access inside the core. This is what makes the appearance verifiable without a CDP port.
- **Never write a background colour into a widget.** Transparency is the contract; the app's surface
  shows through.
- **Theme by token, never by literal — and only by tokens that EXIST.** The app's own tree defines
  `--foreground`, `--color-muted-foreground`, `--dt-primary`, `--dt-border` and `--dt-muted`. The shorter
  set a `::preview` iframe injects (`--accent`, `--border`, `--card`, `--muted-foreground`) does **not**
  exist here, and a `var()` that resolves to nothing drops its declaration silently — a styled widget
  then renders as plain text with no bars and no colour. A hard-coded hex is a bug even when it looks
  right; a wrong token name is worse, because it looks like it works.
- **No fixed pixel size; the content carries a measure.** `--hv-measure` (42rem) caps what sits *inside* a
  widget, so a two-value sparkline cannot become a slab on a wide pane, and a table's columns are sized by
  content instead of stretched to fill. The widget itself is never clamped and the grid always reflows —
  a wider pane still shows more columns. This replaced an earlier "no `max-width` anywhere" rule: the
  user overrode it, because text and widgets filling the whole width on a big screen reads badly.
- **No decorative separator, in a widget or in an answer.** A rule line is chrome the reader has to skip;
  headings, spacing and the widget's own frame do the separating. The same rule is in the format guide,
  so an answer the model structures matches the widgets the transform draws from it.
- **Surface themed by the app; data painted by the plugin.** The surface uses only the five app tokens
  above. Data uses the six `--hv-*` properties declared once at the top of the CSS, `--hv-1` being
  `--dt-primary`; categories take a hue in first-seen order, deterministically. A literal colour anywhere
  outside that one block is a bug, and **colour never carries meaning alone** — every coloured element
  keeps its label or its value (the waterfall prints its sign, the heatmap prints its number).
- **Motion is optional and removed on request.** The staggered rise and the bar grow are decoration; the
  widget is complete without them, and everything is dropped under `prefers-reduced-motion: reduce`.
- **Derivation lives in `rules.yaml`.** A new pattern is a data row, not a code branch, and a rule's
  `group` is what the settings page lists.
- **The Mermaid palette header is literal by necessity** — an `<img>`-hosted SVG cannot resolve `var()`.
  That is why the palette is a setting rather than a live read.

## The prompt section is part of the change

`FORMAT_GUIDE` is the model's only channel to the drawing core. Eight kinds are derived by rules; the other
thirty-three arrive only through an explicit `::viz`, so a kind the guide does not name is a kind nobody
draws. **A change to the core — a new kind, a payload, an attr, the `board` encoding — is not finished until
the guide names it**, and `tests/test_format_guide.py` fails when the two lists drift apart.

The guide is a prompt on every request, so its cost is stated in three places that must move in the same
commit as the text: the character/word/token counts in `dashboard/settings.json`, the badge in
`dashboard/dist/index.js`, and `README.md`.

## Checks

```bash
python3 tests/run_all.py             # agent half, stdlib only — no pytest needed
python3 -m pytest tests/ -q          # the same functions under pytest
node tests/desktop.test.mjs          # the drawing core (54 tests) + the vendored-core drift check
python3 dashboard/selfcheck.py        # settings page: manifest, API routes, bundle
python3 scripts/fixture.py /tmp/hv.html   # one self-contained page of every kind, for screenshots
```

`python3 scripts/fixture.py` with no argument rewrites the tracked `desktop/fixture.html`, so pass a path
unless you mean to commit a new page.

## Python

**3.10 or newer, and it must also run on the newest release** — `python3` anywhere above means an
interpreter in that range. The agent half is imported by whatever interpreter runs the host, so 3.10 is the
floor and no code here may use a feature younger than that; `str | None` and `dict[str, Any]` are the
annotation style, not `Optional`/`Dict`.

## Versions

`plugin.yaml` and `dashboard/manifest.json` carry **one** version and must agree; the app keys a plugin's
dashboard bundle on it, so a mismatch or a missing bump is how a settings page keeps showing the old page
after the code changed. Bump both on **every** feature and every fix — a fix that ships without a bump is
invisible to an instance that has already loaded the bundle. `python3 dashboard/selfcheck.py` fails when
the two disagree.
