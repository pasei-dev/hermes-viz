# The interactive-preview escape hatch

A worked example of the two ways to get an *operable* widget into an answer, using one dataset
throughout: how many flash runs three targets have taken.

| target | runs |
|---|---|
| C8051F121 | 42 |
| 291e panel | 18 |
| 223e surface | 7 |

**Reach for the first door.** The second costs a file, JS you maintain, and a sandbox you do not
control.

## Door 1 — a kind the core draws (`::viz`), which is the whole point of it

Since round 13, adjust-and-send is a *kind*, not a file:

    ::viz{k="facts" x="step" d="C8051F121=42;291e panel=18;223e surface=7" t="Flash runs"}

`x="step"` belongs to the shapes that carry a value per row (`facts`, `kpi`, `records`, `metrics`,
`files`). The core draws a minus and a plus on each row and one send control at the foot; the mount
performs the arithmetic and the send. A control click never sends — it moves the row by ±1, never
below 0, and the mount re-renders. The send carries **the delta, never the whole state**:
`Flash runs C8051F121 +2, 291e panel +1`, and it is disabled until something has moved. A computed
cell (`sum(A, B)`) recomputes over the stepped rows, so a total the model wrote follows the reader's
hand.

Three properties come free here that door 2 has to build: the widget has **no JavaScript**, it
cannot exceed the answer's own payload (nothing a reader types is executed anywhere), and a
non-desktop surface simply gets the markdown it would have had.

## Door 2 — `::preview{file="…"}` when no kind fits

`flash-mix.html` is this same interaction written by hand, kept as the reference for what the escape
hatch can and cannot do. It is rendered in-chat by

    ::preview{file="flash-mix.html"}

which is the app's own directive, not this plugin's. The facts that matter, read off the app source
(`~/.hermes/hermes-agent/apps/desktop/src`):

- **`file` is required and must be `.html`/`.htm`/`.xhtml`** (`components/assistant-ui/inline-preview-directive.tsx:339-357`);
  anything else falls to the artifact path. A relative path resolves against **the session's own
  cwd** (`lib/local-preview.ts:226-266`).
- The frame is `sandbox="allow-scripts"` with **no `allow-same-origin`** (`:1-70`), so the page runs
  JS on an opaque origin — no app cookies, no storage, no bridge. The document arrives via `srcdoc`
  from a bridge file read, capped at 512 KB with *silent* truncation (`electron/main.ts:1744`).
- **Three things are injected**: `window.hermes.send(prompt)` plus a capture-phase click handler on
  `[data-hermes-send]` (`:72-137`); the theme prelude, which defines `--foreground`,
  `--muted-foreground`, `--accent`, `--border`, `--card`, the app font, zero margins and a
  transparent background **first**, so the page's own styles win (`:250-261`); and the host's
  measurer — token-gated, so a page calling `parent.postMessage` on its own cannot resize the frame
  (`:263-330`).
- The intent is gated: only the mount's own message type and token are accepted,
  `MAX_INTENT_LENGTH = 500` (over-length is **rejected, never truncated**), a 1 s throttle, and every
  outcome is acked — `throttled`, `too_long`, `undelivered`, `invalid` (`:140-186`). Treat the ack as
  part of the interaction: the example keeps its delta on `throttled` and re-disables on success.
- The send is `requestComposerSubmit(prompt, { target: 'active', displayKind: 'hidden' })`
  (`:444-451`) — the only hidden-turn call site in the desktop tree, and the reason the reader's
  click arrives as the reader's own message with no bubble rendered.
- **A `::` directive on another surface is source text.** Neither the web UI
  (`web/src/components/Markdown.tsx:169-176`) nor the TUI parses directives at all.

### Which door runs what

| door | desktop | anywhere else |
|---|---|---|
| `::viz` | drawn by this plugin's core, no JS | the markdown it held |
| `::preview{file=…}` | inline frame, JS **live** | source text |
| ` ```svg ` fence | inline after DOMPurify's svg profile — scripts, handlers and `foreignObject` stripped | source text |
| ` ```html ` fence | promoted to an artifact card, not inline (`lib/artifact-detect.ts`) | source text |
| `<script>` in prose | escaped to entities, runs nowhere | escaped |

`flash-mix-fence.md` holds the ` ```svg ` version of the same numbers — the exact bytes a
non-desktop surface would receive — and `flash-mix.svg` the standalone document. The fence language
table is hardcoded in the app (`embeds/registry.tsx:13-15`: exactly `listing`, `mermaid`, `svg`), so a
plugin cannot add one; that is why the SVG exists as a file the example can point at rather than as a
language this plugin invents.

## Reproducing the example's behaviour without the app

The widget's state machine is testable with the app checkout's own jsdom:

```sh
cd examples/interactive-preview && node -e "
const { JSDOM } = require('/Users/nejrup/.hermes/hermes-agent/node_modules/jsdom');
const fs = require('fs');
const dom = new JSDOM(fs.readFileSync('flash-mix.html','utf8'), { runScripts: 'dangerously' });
const doc = dom.window.document;
const dump = () => [...doc.querySelectorAll('.row')].map(r => {
  const v = r.querySelector('.val'); const d = v.querySelector('.delta');
  return r.querySelector('.name').textContent + '=' + v.childNodes[0].textContent + (d ? d.textContent : '');
}).join('  ');
console.log('load:', dump(), '| total', doc.getElementById('total').textContent, '| disabled', doc.getElementById('send').disabled);
const ctl = [...doc.querySelectorAll('.ctl')]; ctl[0].click(); ctl[0].click(); ctl[1].click();
console.log('after:', dump(), '| total', doc.getElementById('total').textContent, '| disabled', doc.getElementById('send').disabled);
let sent=null,n=0; dom.window.hermes={send:p=>{sent=p;n++;return Promise.resolve({ok:true});}};
doc.getElementById('send').click();
setTimeout(()=>{console.log('intent:',sent);console.log('count:',n);process.exit(0);},30);
"
```

Expected: the three rows load at 42/18/7 with the send disabled; two clicks on the first row and one
on the second give `C8051F121=44 +2  291e panel=19 +1  223e surface=7`, total 70, send enabled; the
intent is `Logged C8051F121 +2, 291e panel +1 flash runs since the last chart. Update the mix.` and
is sent **once**.
