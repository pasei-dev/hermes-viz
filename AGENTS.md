# AGENTS.md — hermes-viz

## The two halves and the one contract

The **agent half** (`__init__.py`, `python/`, `rules.yaml`) derives visual specs from a finished answer and
injects the `::viz` grammar; the **desktop half** (`desktop/plugin.js`) parses the directive and draws. They
meet at one contract, **`SPEC.md`**, which both halves are written against in parallel — so an unannounced
change breaks work you cannot see; each rule names the `SPEC.md` section carrying its depth.

## Rules

- **The vendored core is one file in two places.** `plugin.js` carries the pure core
  (`desktop/render/core.mjs`) *verbatim* between `// >>> vendored-core` and `// <<< vendored-core`: the runtime
  loader resolves exactly three bare specifiers (`@hermes/plugin-sdk`, `react`, `react/jsx-runtime`) and
  refuses every other import, so a relative one cannot resolve against the blob: URL. Edit `core.mjs`, copy
  the block across, **never hand-edit one side** —
  `node tests/desktop.test.mjs` fails if the two drift.
- **This repo names no other project.** Every comment, doc, prompt and commit message carries this plugin's
  own vocabulary: a name that points at another product is a trail the repo does not carry, and a commit
  message is as public as a file. The scan that holds the line runs with the deployment, not here.
- **Shapes, not subjects** — a named subject (`nutrition`, `recipe`, `route`, `matches`, `words`) is a skin
  over a shape of data, never new machinery, and a new kind is the last resort. (`SPEC.md` → *Shapes, not
  subjects*.)
- **The directive is one paragraph, one line, no braces in the attrs**, and belongs to one surface: the hook
  emits one, and asks the model for one, **only when the platform is `desktop`**. The app's parser enforces
  the shape (`lib/transcript-directives.ts`). A `::viz` that reaches another surface — or one the app and the
  core would refuse — is **demoted to the markdown it would have drawn**, never deleted. (`SPEC.md` → *The
  directive*, *The licence to repair an answer*.)
- **A value may be computed from the widget's own payload.** `sum(A, B)`, `share(A, B)`, `diff(A, B)` name
  the payload's own rows, so a total is arithmetic the halves do, never the model's; `tests/cells.json` is the
  one table both suites read, so a rule that drifts fails there. An unresolvable call stays **visible**
  (`sum(A, B)` prints as written). `is_drawable` in `python/viz_dsl.py` refuses only what is *proved*
  undrawable — an unknown attr such as `x=` is never a reason. (`SPEC.md` → *Computed cells*, *The
  validator*.)
- **The drawing core is pure.** `renderKind(kind, rows, opts)` returns markup; the React component mounts it.
  No DOM access inside the core — that is what makes the appearance verifiable without a CDP port.
- **The core paints no surface; the box does — and the widget sheet draws it.** A widget's markup carries no
  background: the box's material is drawn on the MOUNT, as a translucent wash of the app's own muted token
  (accent-tinted, and inverted by the theme), with the app's stroke token as its line and one hairline of lift.
  Never a literal, never a fill the core owns, and a box carries its own room in the sheet's scale. The RULES
  live in the widget sheet, not in the answer sheet: a frame is part of what a widget is, and drawn with
  `body_style` a reader who turned that sheet off got every widget bare. The answer sheet keeps only the
  host's own surface, the fenced code block. (`SPEC.md` → *Round 17*, *Round 21*.)
- **Theme by token, never by literal — and only by tokens that EXIST**: `--foreground`,
  `--color-muted-foreground`, `--dt-primary`, `--dt-border`, `--dt-muted`, and for type `--dt-font-heading` /
  `--dt-font-mono` / `--dt-font-sans`. The `::preview` iframe's set
  (`--accent`, `--border`, `--card`) does **not** exist here, and a `var()` that resolves to nothing drops
  its declaration silently — the widget renders uncoloured. A hard-coded hex is a bug. (`SPEC.md` → *The
  palette*, *The scale*.)
- **The plugin's two voices are the app's own, read by token — and the faces it ships are CHOICES.** A
  widget's title and a section head take `--dt-font-heading` (landing on `--dt-font-sans`), a caption and a
  machine word take `--dt-font-mono`; a widget's values declare nothing and inherit the app's body face. The
  `font_body` / `font_heading` settings may name a family this plugin ships — its bytes ride in the core's
  `FACES` block, written by `scripts/fonts.py` from `desktop/fonts/*.woff2`, licence beside them, and a test
  binds the two — and that face reaches the two voices by declaring the app's OWN tokens, never a family
  inside the widget sheet. `system` declares nothing at all. A stack ends in a generic the platform certainly
  has, names no `ui-*` family (which Chromium does not implement), and the chosen families are injected as an
  `@font-face` tag of their own. (`SPEC.md` → *Round 16*.)
- **A widget answers to the column it was given.** The box is a container, so the drawing inside reflows to
  the room it actually has: the mount is `hv` and a widget root is `kv` (an element can never query itself),
  and the queries are one at-rule PER NAME — a comma-separated list of names is an invalid condition and the
  whole block is dropped in silence. A label column is a floor, never a wall, and a grid track is
  `minmax(0, 1fr)`. The mount scrolls as the last resort, so nothing prints outside the frame at any width.
  (`SPEC.md` → *Round 21*.)
- **No fixed pixel size**: `--hv-measure` (42rem) caps what sits *inside* a widget, centred and never left
  flush, and the body measure (68ch) sits on `.aui-md`, not per element, because `ch` in a heading's larger
  type measures wider. (`SPEC.md` → *Width, padding and measure*.)
- **No decorative separator, in a widget or in an answer** — headings, spacing and the widget's own frame do
  the separating.
- **Surface themed by the app; data painted by the plugin**: six `--hv-*` properties declared once at the
  top of the CSS, `--hv-1` being `--dt-primary`, categories taking a hue in first-seen order. A literal
  colour outside that block is a bug, and **colour never carries meaning alone**. (`SPEC.md` → *The
  palette*, *The scale*.)
- **Motion is opt-in, and the index rides in the markup**: `--d` per row and `--k` per bar, the delay from
  that index, all inside `@media (prefers-reduced-motion: no-preference)` — never a fixed `:nth-child`
  delay, which cliffs at six. (`SPEC.md` → *Motion*.)
- **One glyph vocabulary, and no emoji-capable character.** Every mark is one of the ten in `SPEC.md`'s
  table, and `⚠` (U+26A0) plus the emoji blocks are banned — a host that substitutes an emoji font draws a
  coloured symbol inside otherwise monochrome text. A test walks the core's glyph constants; a scan covers
  the banned ranges.
- **A hover note is the answer's, never the core's**: `data-hv-row` is the dim on every row, a widget's one
  label is the answer's `n=` (`data-hv-note` on the root, one caption slot), and a list the host already
  draws stays the HOST's: `changes` ships OFF (`DEFAULT_RULE_GROUPS_OFF`).
  (`SPEC.md` → *Interaction*, *A changed-files list*.)
- **`body_style` puts the `68ch` measure on the turn's content block, not on the markdown root** — the host
  lays a turn's output out as siblings (the markdown, the boxes between it, the scaffolding beside it), so a
  cap on the markdown held the prose alone and the run of tool work hung off the left of the column it
  belongs to. The column is the turn's, and this sheet sets no face in it: scaffolding keeps the app's own
  face because nothing here names another, and the app's own rhythm between its blocks
  — a run is spaced by the host, never restated here;
  `--dt-primary` on `h1`–`h3` rides with it. Off, the sheet is byte-identical; every selector sits under
  `.aui-md` **or the host's turn content block**, written `:where(…)`. (`SPEC.md` → *Body text*.)
- **The app's chrome and the type are this plugin's, each behind its own setting — and a theme carries
  colouring only.** Every UI change lives here: the four chrome settings — `chrome_composer`,
  `chrome_surfaces`, `chrome_panes` (on by default) and `column_width` (px, 0 = off) — and the two face
  settings rewrite the app's own surfaces and type, which a theme does not. Each sheet is its OWN `<style>`
  tag, so a switch that is off is **absent** from the document rather than neutralising what the plugin
  installed. Each chrome sheet may reach only the roots its switch names, and `tests/desktop.test.mjs` holds
  the table: a new surface is a row there first. Where the app has a TOKEN for the thing being changed, the
  token moves and never the property it feeds; every colour is a token or a wash `color-mix`ed from one; glass
  writes its own `@supports` fallback; and nothing the app already does is restated. No `!important`: the
  plugin's sheet is unlayered and the app's values are in `@layer base`, so the cascade already hands it the
  win. (`SPEC.md` → *The chrome*.)
- **A backtick inside a sheet closes it.** Every stylesheet is a template literal, so one backtick written
  into a CSS comment ends the literal and the rest of the sheet is *evaluated as JavaScript* — a selector
  becomes `data - tree - group` and the module dies at load with `ReferenceError: data is not defined`,
  taking the directive, the sheets and the settings page down together. `node --check` is happy (the result
  is still valid syntax) and every string test passes, so the gates are two: `sheetOf()` refuses a backtick
  in any sheet, and `tests/desktop.test.mjs` **imports** the module against stubbed specifiers, which is the
  gate the app itself applies. Name CSS selectors bare in those comments.
- **A URL or rooted path in a cell is the host's own reference** — `class="ref"` plus the host's `data-ref`
  kind and its glyph; `data-hv-link`/`data-hv-value` declare the click and `VizWidget` performs it
  (`openExternal`, `revealPath`). A cell is a reference when it is marked or unambiguous; the visible text
  is never shortened.
  **A scheme in a payload is written protocol-relative** (`https://x/y` → `//x/y`): the host autolinks a bare
  `http(s)://` wherever it finds one, and one autolink splits the paragraph the directive stands in, so the
  app refuses the card and the reader loses the whole drawing — the agent half writes the mark and the core
  reads it, putting the scheme back in the click's own value and never guessing a cell's shape.
  (`SPEC.md` → *References*.)
- **Derivation lives in `rules.yaml`**: a new pattern is a data row, not a code branch; a rule's `group` is
  what the settings page lists.
- **The Mermaid palette header is literal by necessity** — an `<img>`-hosted SVG cannot resolve `var()`;
  that is why the palette is a setting rather than a live read.

## The prompt section is part of the change

`FORMAT_GUIDE` is the model's only channel to the drawing core, and **its kind block is composed from
`rules.yaml` against the enabled groups** — a group that is off is absent from the prompt, never annotated
("`changes` is OFF" is a prompt bug, not a note). The rule table derives 33 kinds; the other eighteen arrive
only through an explicit `::viz`, so a kind the guide does not name is a kind nobody draws. **A new kind,
payload or attr is not finished until the guide names it**, and `tests/test_format_guide.py` fails when the
two lists drift. The guide is a prompt on every request, and its cost is written down once, in `README.md`.

## Checks

```bash
python3 tests/run_all.py             # agent half, stdlib only — no pytest needed
python3 -m pytest tests/ -q          # the same functions under pytest
node tests/desktop.test.mjs          # the drawing core + the vendored-core drift check
python3 dashboard/selfcheck.py        # settings page: manifest, API routes, bundle
python3 scripts/fixture.py /tmp/hv.html   # every kind on one page; with no argument it rewrites the tracked desktop/fixture.html
```

## Python

**3.10 or newer, and it must also run on the newest release**: `python3` above means an interpreter in that
range. 3.10 is the floor, and `str | None` / `dict[str, Any]` are the annotation style, not
`Optional`/`Dict`.

## Versions

`plugin.yaml` and `dashboard/manifest.json` carry **one** version and must agree: the app keys a plugin's
dashboard bundle on it, so a mismatch or a missing bump keeps the old page showing.
**Bump both when the change is verified and about to land — not on every edit in a work session** — and
re-check both numbers against what lands, in the commit that lands it. `python3 dashboard/selfcheck.py`
fails when the two disagree.
