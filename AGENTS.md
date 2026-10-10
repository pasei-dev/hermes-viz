# AGENTS.md — hermes-viz

## The two halves and the one contract

The **agent half** (`__init__.py`, `python/`, `rules.yaml`) derives visual specs from a finished answer and
injects the `::viz` grammar; the **desktop half** (`desktop/plugin.js`) parses the directive and draws. They
meet at one contract, **`SPEC.md`**, which both halves are written against in parallel — so an unannounced
change breaks work you cannot see. Depth for a rule sits in the `SPEC.md` section it names.

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
- **Never write a background colour into a widget.** Transparency is the contract.
- **Theme by token, never by literal — and only by tokens that EXIST**: `--foreground`,
  `--color-muted-foreground`, `--dt-primary`, `--dt-border`, `--dt-muted`. The `::preview` iframe's set
  (`--accent`, `--border`, `--card`) does **not** exist here, and a `var()` that resolves to nothing drops
  its declaration silently — the widget renders uncoloured. A hard-coded hex is a bug even when it looks
  right. (`SPEC.md` → *The palette*, *The scale*.)
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
  draws stays the HOST's — `changes` ships OFF (`DEFAULT_RULE_GROUPS_OFF`), rule and renderer kept.
  (`SPEC.md` → *Interaction*, *A changed-files list*.)
- **`body_style` adds exactly two things in its default state: a `68ch` measure and `--dt-primary` on
  `h1`–`h3`** — off, the sheet is byte-identical; it copies none of the app's typography, and every selector
  sits under `.aui-md` written `:where(…)`. (`SPEC.md` → *Body text*.)
- **A URL or rooted path in a cell is the host's own reference** — `class="ref"` plus the host's `data-ref`
  kind and its glyph; `data-hv-link`/`data-hv-value` declare the click and `VizWidget` performs it
  (`openExternal`, `revealPath`). Only unambiguous shapes qualify; the visible text is never shortened.
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
python3 scripts/fixture.py /tmp/hv.html   # every kind on one page, for screenshots
```

`python3 scripts/fixture.py` with no argument rewrites the tracked `desktop/fixture.html`, so pass a path
unless you mean to commit a new page.

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
