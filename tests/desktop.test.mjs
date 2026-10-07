/**
 * hermes-viz — the drawing core's tests.
 *
 * Node only, no dependency: `node tests/desktop.test.mjs`. The core is pure,
 * so these run without a DOM, without React and without the app.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

import { CSS, KINDS, parseSpec, renderKind, renderWidget } from '../desktop/render/core.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, '..')

const PLUGIN_SRC = readFileSync(join(ROOT, 'desktop/plugin.js'), 'utf8')
const CORE_SRC = readFileSync(join(ROOT, 'desktop/render/core.mjs'), 'utf8')

/** The single-line paragraph the model writes, one per kind. */
const SAMPLES = {
  kpi: { k: 'kpi', d: 'Builds=128=+12;Fails=3=-1', t: 'CI', u: '' },
  bars: { k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' },
  line: { k: 'line', d: '3;7;4;9;11', t: 'Latency', u: 'ms' },
  donut: { k: 'donut', d: 'Used=62;Free=38', t: 'Disk', u: '%' },
  steps: { k: 'steps', d: 'Read the archive;Patch the entry;Flash over EC3', t: 'Runbook', u: '' },
  table: { k: 'table', d: 'h=Board|Runs;291e|42;296|17', t: 'Boards', u: '' },
  progress: { k: 'progress', d: 'Flash=75', t: 'Bring-up', u: '' },
  sparkline: { k: 'sparkline', d: '1;1;2;3;5;8;13', t: 'Trend', u: '' },
  section: { k: 'section', d: 'Rolling out 291e', t: 'Deployment', u: '' },
  checklist: { k: 'checklist', d: 'Build=done;Flash=doing;Verify=todo', t: 'Run', u: '' },
  changes: { k: 'changes', d: 'core.mjs=+120=-8;plugin.js=+40=-12', t: 'Diff', u: '' },
  outline: { k: 'outline', d: '1=Intro;1.1=Scope;2=Method', t: 'Contents', u: '' },
  facts: { k: 'facts', d: 'Port=EC3;Chip=C8051F121', t: 'Board', u: '' },
  files: { k: 'files', d: 'src/core.mjs=180 lines;tests/x.mjs=90 lines', t: 'Files', u: '' },
  parts: { k: 'parts', d: 'h=Ref|Part|Qty;U1|C8051F121|1;U2|ESP32|2', t: 'BOM', u: '' },
  settings: { k: 'settings', d: 'Motion=on;Sound=off', t: 'Prefs', u: '' },
  timeline: { k: 'timeline', d: 'Mon=Kickoff=crew brief;Wed=Build', t: 'Schedule', u: '' },
  ranges: { k: 'ranges', d: 'Build=2..9;Flash=5..14', t: 'Windows', u: 'h' },
  metrics: { k: 'metrics', d: 'Coverage=88=-2;Latency=14=+3', t: 'Health', u: '' },
  array: { k: 'array', d: 'a|b|c;d|e|f', t: 'Matrix', u: '' },
  heatmap: { k: 'heatmap', d: 'Mon=40;Tue=90;Wed=12', t: 'Load', u: '' }
}

test('the core knows exactly the kinds we advertise', () => {
  // 8 original + section + the 12 answer-shaped round-2 kinds.
  assert.equal(KINDS.length, 21)
  assert.deepEqual([...KINDS].sort(), Object.keys(SAMPLES).sort())
})

test('every kind renders a widget, not a fallback', () => {
  for (const kind of KINDS) {
    const markup = renderWidget(SAMPLES[kind])

    assert.ok(markup.startsWith('<div class="hv hv-widget"'), `${kind}: widget wrapper`)
    assert.ok(markup.includes(`data-kind="${kind}"`), `${kind}: kind is labelled`)
    assert.ok(!markup.includes('hv-prose'), `${kind}: no fallback prose`)
    assert.ok(markup.includes('hv-grid'), `${kind}: mounts inside the one grid`)
    assert.ok(markup.replace(/<[^>]*>/g, '').trim().length > 0, `${kind}: has visible text`)
  }
})

test('a malformed spec yields prose, never an empty frame', () => {
  const cases = [
    renderWidget(null),
    renderWidget({}),
    renderWidget({ k: 'bogus', d: 'a=1' }),
    renderWidget({ k: 'kpi', d: '' }),
    renderWidget({ k: 'progress', d: ';;;' })
  ]

  for (const markup of cases) {
    assert.ok(markup.includes('hv-prose'), `expected prose fallback in: ${markup}`)
    assert.ok(markup.replace(/<[^>]*>/g, '').trim().length > 0, 'fallback carries text')
  }

  // The original directive text is what the reader sees, escaped.
  const escaped = renderWidget({ k: 'bogus', d: '', source: '::viz{k="bogus"}' })
  assert.ok(escaped.includes('::viz{k=&quot;bogus&quot;}'))
})

test('separators inside model values are stripped, not rendered', () => {
  const spec = parseSpec({ k: 'bars', d: 'A=1;B=2', t: 'x=y;z|w\nv', u: 'a=b' })

  assert.equal(spec.title, 'xyzwv', 'title stripped of ; | = and newline')
  assert.equal(spec.unit, 'ab', 'unit stripped of =')
  assert.equal(spec.rows.length, 2, 'row split on ;')
  assert.equal(spec.rows[0].cells[0].label, 'A')
  assert.equal(spec.rows[0].cells[0].value, '1')

  const markup = renderWidget({ k: 'bars', d: 'A=1;B=2', t: 'x=y;z|w\nv', u: 'a=b' })
  assert.ok(!markup.includes(';'), 'no ; survives into markup')
  assert.ok(!markup.includes('|'), 'no | survives into markup')

  // A value holding its own `=` is split, so the `=` never reaches the reader.
  const withEquals = renderWidget({ k: 'bars', d: 'Load=1=2' })
  assert.ok(withEquals.includes('>1<') || withEquals.includes('>1</span>'))
  assert.equal(parseSpec({ k: 'bars', d: 'Load=1=2' }).rows[0].cells[0].extra, '2')
})

test('no fixed pixel size and no max-height — the content is capped by a measure', () => {
  // The rule this test replaces ("no max-width anywhere") was overridden by the
  // user: on a wide pane the info was flung apart. The widget still never gets a
  // cap of its own — the grid reflows and the pane decides — but its CONTENT is
  // capped by a measure, and tables size by content instead of stretching.
  assert.ok(CSS.includes('--hv-measure: 42rem'), 'the measure is 42rem')
  assert.ok(/max-width:\s*var\(--hv-measure\)/.test(CSS), 'content is capped by the measure')
  assert.ok(!/max-width:\s*[0-9]/.test(CSS), 'no fixed pixel max-width')
  assert.ok(!/max-height/.test(CSS), 'still no max-height anywhere')

  const table = CSS.match(/\.hv-table\s*\{[^}]*\}/)
  assert.ok(table, 'a .hv-table rule exists')
  assert.ok(!/width:\s*100%/.test(table[0]), 'a table is not stretched to fill its cell')

  for (const kind of KINDS) {
    assert.ok(!/max-width:\s*[0-9]/.test(renderWidget(SAMPLES[kind])), `${kind} markup`)
  }
})

test('the widget surface paints nothing — only tokens, no literal colour', () => {
  assert.ok(!/\.hv-widget[^{]*\{[^}]*background/.test(CSS), 'the widget itself stays transparent')
})

test('the palette is six hues declared once, and literals live only there', () => {
  const declared = [...CSS.matchAll(/(--hv-[1-6])\s*:/g)].map(m => m[1])
  assert.deepEqual(declared, ['--hv-1', '--hv-2', '--hv-3', '--hv-4', '--hv-5', '--hv-6'], 'six slots, declared once, in order')
  assert.ok(CSS.includes('--hv-1: var(--dt-primary)'), '--hv-1 IS the theme accent')
  assert.ok(!/var\(--dt-primary\)[^;]*--dt-primary/.test(CSS), 'no accidental second accent')

  // Every literal colour in the sheet sits inside those six declarations. The
  // palette block is the ONE place a hex may appear; anywhere else it is a bug.
  const stripped = CSS.replace(/--hv-[1-6]:[^;]+;/g, '')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(stripped), 'no hex outside the palette block')
  assert.ok(!/rgb\(|hsl\(|oklch\(|oklab\(/.test(stripped), 'no colour functions outside the palette block')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(CORE_SRC.replace(/--hv-[1-6]:[^;]+;/g, '')), 'and none in the core source')
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(PLUGIN_SRC.replace(/--hv-[1-6]:[^;]+;/g, '')), 'and none in the plugin source')
})

test('categories take a hue in first-seen order, deterministically', () => {
  const payload = 'A=1;B=2;C=3'
  const first = renderWidget({ k: 'donut', d: payload })

  // Same payload -> same colours, every time.
  assert.equal(first, renderWidget({ k: 'donut', d: payload }))
  assert.ok(first.includes('hv-c0') && first.includes('hv-c1') && first.includes('hv-c2'), 'the first three slots are used')
  assert.ok(!first.includes('hv-c3'), 'a three-category payload stops at slot three')

  // The order of appearance is what assigns the hue, so a reorder repaints.
  assert.notEqual(first, renderWidget({ k: 'donut', d: 'B=2;A=1;C=3' }))

  // Past six categories the ramp wraps, still deterministically.
  const seven = renderWidget({ k: 'donut', d: 'A=1;B=1;C=1;D=1;E=1;F=1;G=1' })
  assert.ok(seven.includes('hv-c0') && seven.includes('hv-c5'), 'all six slots, then a wrap')
})

test('a tiny donut slice is separated from its neighbours, never erased', () => {
  const markup = renderWidget({ k: 'donut', d: 'Big=180;Small=9', t: 'Disk' })
  const arcs = [...markup.matchAll(/stroke-dasharray="([\d.]+) [\d.]+"/g)].map(m => Number(m[1]))
  assert.equal(arcs.length, 2, 'two slices are drawn')
  const [big, small] = [...arcs].sort((a, b) => b - a)
  assert.ok(small > 3, `the small slice keeps a visible arc: ${small}`)
  assert.ok(small < big, 'but it is still the smaller arc')
})

test('plugin.js carries the core verbatim, so the two copies cannot drift', () => {
  const region = source => {
    const begin = '// >>> vendored-core\n'
    const end = '// <<< vendored-core\n'
    const from = source.indexOf(begin)
    const to = source.indexOf(end)
    assert.ok(from >= 0 && to > from, 'both markers present')
    return source.slice(from + begin.length, to)
  }

  assert.equal(region(PLUGIN_SRC), region(CORE_SRC))
  assert.ok(region(CORE_SRC).includes('function renderKind'))
})

test('plugin.js imports only what the runtime loader resolves', () => {
  const specifiers = [...PLUGIN_SRC.matchAll(/\bfrom\s*['"]([^'"]+)['"]/g)].map(m => m[1])
  const allowed = new Set(['@hermes/plugin-sdk', 'react', 'react/jsx-runtime'])

  for (const specifier of specifiers) {
    assert.ok(allowed.has(specifier), `unsupported import: ${specifier}`)
  }

  assert.ok(PLUGIN_SRC.includes('TRANSCRIPT_DIRECTIVE_AREA'))
  assert.ok(PLUGIN_SRC.includes("name: 'viz'"))
})

test('a board lays out its ~-separated entries side by side in one widget', () => {
  const markup = renderWidget({
    k: 'board',
    d: 'bars:Firmware=42;Model A=28;Web=18~kpi:Builds=128=+12;Fails=3=-1~steps:Read the archive',
    t: 'Build board'
  })

  assert.ok(markup.startsWith('<div class="hv hv-widget" data-kind="board">'))
  assert.ok(markup.includes('hv-board'), 'the pane-sizing grid class is present')
  // all three entries draw themselves, one cell each
  assert.ok(markup.includes('hv-bar'))
  assert.ok(markup.includes('hv-kpi-value'))
  assert.ok(markup.includes('hv-step'))
  // one board, not three paragraphs
  assert.equal(markup.split('hv-board').length - 1, 1)
  assert.ok(!markup.includes('<div class="hv-grid"><div class="hv hv-grid hv-board"'), 'a board is not nested inside a second measured grid — otherwise the measure collapses it to one column')
  assert.ok(!markup.includes('hv-prose'))
})

test('the board takes its entries raw, so ~ is the only thing that splits it', () => {
  const markup = renderKind('board', ['bars:A=1;B=2', 'table:h=X|Y;1|2'], {})
  assert.ok(markup.includes('hv-bar') && markup.includes('hv-table'))
  assert.ok(markup.startsWith('<div class="hv hv-grid hv-board">'))
})

test('a bad board cell falls back to prose for that cell only, never an empty frame', () => {
  const markup = renderWidget({ k: 'board', d: 'bars:A=1~bogus:x=1~kpi:C=3' })

  assert.ok(markup.includes('data-kind="board"'), 'the board itself still stands')
  assert.ok(markup.includes('data-reason="unknown-kind"'), 'the bad cell reads as prose')
  assert.ok(markup.includes('hv-bar') && markup.includes('hv-kpi-value'), 'the good cells survive')
  assert.ok(markup.includes('hv-board'))
})

test('a partially written board spec never throws anywhere in the render path', () => {
  const partials = [
    { k: 'board' },
    { k: 'board', d: '' },
    { k: 'board', d: '~' },
    { k: 'board', d: '~tail' },
    { k: 'board', d: 'bars' },
    { k: 'board', d: 'bars:A=1~kpi:' },
    { k: 'board', d: 'bars:A=1~' },
    { k: 'board', d: 'bars:A=1~:payload' },
    { k: 'board', d: 'bars' + 'x'.repeat(4000) }
  ]

  for (const attrs of partials) {
    const markup = renderWidget(attrs)
    assert.equal(typeof markup, 'string')
    assert.ok(markup.trim().length > 0, 'never an empty frame')
    assert.ok(markup.startsWith('<div class="hv hv-widget"'))
  }
  // an entry with no rows and one with no colon both read as prose, not a blank
  assert.ok(renderWidget({ k: 'board', d: 'bars:A=1~kpi:' }).includes('hv-prose'))
  assert.ok(renderWidget({ k: 'board', d: 'bars:A=1~:payload' }).includes('hv-prose'))
})

test('~ is stripped from model values like the other separators', () => {
  const spec = parseSpec({ k: 'bars', d: 'A=1~2' })
  assert.equal(spec.rows[0].cells[0].label, 'A')
  assert.equal(spec.rows[0].cells[0].value, '12', 'the tilde never survives into the value')
  const markup = renderWidget({ k: 'bars', d: 'A=1', t: 'x~y' })
  assert.ok(!markup.includes('~'))
})

test('the board grid asks for a wider column than the plain grid', () => {
  const board = CSS.match(/\.hv-board\s*{[^}]*}/)
  assert.ok(board, 'a .hv-board rule exists')
  assert.ok(board[0].includes('repeat(auto-fit, minmax('))
  assert.ok(!/max-width:\s*[0-9]/.test(board[0]))
})

test('every theme token the CSS uses is one the app defines or the palette declares', () => {
  // Read off the live renderer. The app's own tree defines exactly these five; the shorter set a
  // `::preview` iframe injects (`--accent`, `--border`, `--card`, `--muted-foreground`) does not
  // exist here. A `var()` naming anything else resolves to nothing and drops its declaration
  // silently — which is how a fully styled widget rendered as plain text, no bars, no colour.
  const APP_TOKENS = new Set([
    '--foreground',
    '--color-muted-foreground',
    '--dt-primary',
    '--dt-border',
    '--dt-muted'
  ])
  // `--hv-*` is ours: it must be declared in this sheet before it can be used.
  const declared = new Set([...CSS.matchAll(/(--hv-[a-z0-9-]+)\s*:/g)].map(m => m[1]))
  const used = [...CSS.matchAll(/var\((--[a-z0-9-]+)/g)].map(m => m[1])
  assert.ok(used.length > 0, 'the CSS uses theme tokens at all')
  assert.ok([...used].some(token => token.startsWith('--hv-')), 'and uses the palette')

  const unknown = [...new Set(used)].filter(token => !APP_TOKENS.has(token) && !declared.has(token))
  assert.deepEqual(unknown, [], 'tokens that resolve to nothing: ' + unknown.join(', '))
})

test('a series is a series: bare numbers plot a varying line, not a flat one', () => {
  const line = renderWidget({ k: 'line', d: '3;7;4;9;11;8;14', t: 'Latency' })
  const points = line.match(/hv-line-path" points="([^"]+)"/)[1].split(' ')
  const ys = [...new Set(points.map(point => point.split(',')[1]))]
  assert.ok(ys.length > 2, `line y-values: ${ys.join(', ')}`)
  assert.ok(line.includes('hv-line-y'), 'the line labels its scale on a real axis')
  assert.ok(line.includes('>14<'), 'the high value reaches the reader')
  assert.ok(line.includes('hv-line-area'), 'the series carries an area, not a bare stroke')

  const spark = renderWidget({ k: 'sparkline', d: '1;1;2;3;5;8;13;21', t: 'Trend' })
  const sparkYs = [
    ...new Set(spark.match(/hv-spark-path" points="([^"]+)"/)[1].split(' ').map(point => point.split(',')[1]))
  ]
  assert.ok(sparkYs.length > 2, `sparkline y-values: ${sparkYs.join(', ')}`)
})

test('bars and ranges carry a real axis with ticks and labels', () => {
  const markup = renderWidget({ k: 'bars', d: 'Firmware=42;Model A=28;Web=18', t: 'Share', u: '%' })
  const ticks = [...markup.matchAll(/class="hv-tick[^"]*">(\d+)/g)].map(m => m[1])
  assert.ok(ticks.length >= 5, `a labelled scale, at least 0..100 in steps: ${ticks.join(', ')}`)
  assert.deepEqual(ticks, ['0', '25', '50', '75', '100'], 'four even ticks, 0 at the lo end')

  const ranges = renderWidget({ k: 'ranges', d: 'A=2..9;B=5..14', t: 'Windows', u: 'h' })
  assert.ok(ranges.includes('hv-range-span'), 'the span is drawn')
  assert.ok(ranges.includes('hv-axis'), 'the range chart shares one scale')
  assert.ok(ranges.includes('hv-axis-hi">14'), 'the shared cap is the widest upper bound')
})

test('every plotted element carries its own hover detail, and reads without it', () => {
  const bars = renderWidget({ k: 'bars', d: 'A=42;B=28', t: 'S', u: '%' })
  assert.ok(bars.includes('title="A: 42%"'), 'a bar row names its value on hover')
  assert.ok(bars.includes('hv-row-value">42'), 'and prints it in the row')

  const line = renderWidget({ k: 'line', d: '3;7;9', t: 'L' })
  assert.ok(line.includes('hv-line-point'), 'each point gets a marker')
  assert.ok(/<title>#1: 3<\/title>/.test(line), 'and its marker carries the detail')

  const heat = renderWidget({ k: 'heatmap', d: 'Mon=40;Tue=90', t: 'Load' })
  assert.ok(heat.includes('title="Tue: 90"'), 'a heat cell names its value')
  assert.ok(/hv-heat-value">90</.test(heat), 'and prints it inside the cell')
})

test('a section draws a header band and a lead line, with no caption above it', () => {
  const markup = renderWidget({ k: 'section', t: 'Deployment', d: 'Rolling out 291e' })
  assert.ok(markup.includes('hv-section-band'), 'the band exists')
  assert.ok(markup.includes('hv-section-title">Deployment'), 'the heading is in the band')
  assert.ok(markup.includes('hv-section-lead">Rolling out 291e'), 'the lead line follows')
  assert.ok(!markup.includes('hv-title'), 'no duplicate caption above the band')

  assert.ok(renderWidget({ k: 'section' }).includes('hv-prose'), 'an empty section is prose, not a bare rule')
})

test('a legend appears when a chart has more than one series, and never for one', () => {
  assert.ok(renderWidget({ k: 'donut', d: 'A=1;B=2' }).includes('hv-legend'), 'two slices -> a legend')
  assert.ok(!renderWidget({ k: 'sparkline', d: '1;2;3' }).includes('hv-legend'), 'one series -> no legend')
})

test('motion is removed wholesale under prefers-reduced-motion', () => {
  const reduce = CSS.match(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\n\}/)
  assert.ok(reduce, 'a reduced-motion block exists')
  assert.ok(/animation: none !important/.test(reduce[0]), 'every animation is switched off')
  // ...and the ordinary path animates only compositor properties.
  const animated = [...CSS.matchAll(/animation: hv-(rise|grow)/g)]
  assert.ok(animated.length > 0, 'the default path animates')
  for (const [decl] of CSS.matchAll(/animation: hv-\w+ [^;]+;/g)) {
    assert.ok(!/width|height|top|left|margin|padding/.test(decl), `non-composited animation: ${decl}`)
  }
})
